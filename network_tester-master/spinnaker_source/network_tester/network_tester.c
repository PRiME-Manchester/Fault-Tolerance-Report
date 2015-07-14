/**
 * SpiNNaker network_tester kernel.
 */

#include <string.h>
#include <stdbool.h>

#include "sark.h"
#include "spin1_api.h"

#include "network_tester.h"


#define MS_TO_TICKS(ms) ((ms) * ((uint32_t)sv->cpu_clk) * 1000u)
#define US_TO_TICKS(us) ((us) * ((uint32_t)sv->cpu_clk))
#define NS_TO_TICKS(ns) (((ns) * ((uint32_t)sv->cpu_clk)) / 1000u)

// A (sticky) set of flags which are set to NT_ERR_* if something has gone
// wrong. This flag's value should be reported back to the host as the first
// word of the result data.
static uint32_t error_occurred = 0;

// A bit field which indicates what set of fields is to be recorded.
// Bits 15:0 enable logging of each router diagnostic counter.
// Bit 16 enables logging number of sent packets
// Bit 17 enables logging number of blocked packets due to back pressure
// Bit 24 enables logging number of received packets
static uint32_t to_record;

#define RECORD_SENT_BIT (1u << 24)
#define RECORD_BLOCKED_BIT (1u << 25)
#define RECORD_RECEIVED_BIT (1u << 28)

// The maximum number of values which can be recorded simultaneously (used to
// set the size of the buffer where results are stored)
#define MAX_RECORDABLE_VALUES 19

// The interval at which values will be recorded.
static int32_t record_interval_steps;

// The packet generation timestep
static int32_t timestep_ticks;

// SDRAM location where sufficient storage has been allocated to store all results
static uint32_t *sdram_block;

// SDRAM location where the next results should be stored
static uint32_t *sdram_next_results;

// Details of the set of sources and sinks.
static size_t num_sources;
static size_t num_sinks;
static source_t *sources;
static sink_t *sinks;

// This buffer is used to store the last raw counter values recorded. These are
// used to calculate the change in counter values between this recording and
// the next recording. The results are packed consecutively from index zero
// onwards. This buffer is guaranteed to be at least large enough to store all
// router registers and all source and sink counters. It is resized by the
// set_num_sources and set_num_sinks calls.
static uint32_t *last_recorded;

// This buffer holds the results currently being copied into SDRAM by DMA.
static uint32_t *recorded_value_buffer;

// The value of the router timeout register just before the previous call to
// `NT_CMD_ROUTER_TIMEOUT`.
static uint old_router_timeout;

// Pointer to the reinjector counters. If the reinjector is not running, the
// value of these counters is undefined.
reinjector_counters_t *reinjector_counters;

// The number of recording counters which exist for each router, source and
// sink.
#define NUM_ROUTER_COUNTERS 16
#define NUM_REINJECTOR_COUNTERS (sizeof(reinjector_counters_t) / sizeof(uint))
#define NUM_SOURCE_COUNTERS 3
#define NUM_SINK_COUNTERS 1

// Given a number of sinks and a number of sources, gives the maximum number of
// result counters which may exist.
#define MAX_NUM_RESULTS(num_sources, num_sinks) ( \
	NUM_ROUTER_COUNTERS + \
	NUM_REINJECTOR_COUNTERS + \
	(NUM_SOURCE_COUNTERS * (num_sources)) + \
	(NUM_SINK_COUNTERS * (num_sinks)) \
)


// XXX: Will be included as part of next version of SCAMP/SARK
// Get a pointer to a tagged allocation. If the "app_id" parameter is zero
// uses the core's app_id.
void *sark_tag_ptr (uint tag, uint app_id)
{
	if (app_id == 0)
		app_id = sark_vec->app_id;
	
	return (void *) sv->alloc_tag[(app_id << 8) + tag];
}


/**
 * Change the number of sources.
 */
void set_num_sources(size_t new_num_sources) {
	// Allocate a new array of sources
	source_t *new_sources = sark_alloc(new_num_sources, sizeof(source_t));
	if (!new_sources && new_num_sources != 0) {
		ERROR("Could not allocate space for %d sources.\n", new_num_sources);
		error_occurred |= NT_ERR_MALLOC;
		return;
	}
	
	// Allocate new result arrays
	uint32_t *new_last_recorded = sark_alloc(
		MAX_NUM_RESULTS(new_num_sources, num_sinks), sizeof(uint32_t));
	if (!new_last_recorded) {
		ERROR("Could not allocate space for %d sources.\n", new_num_sources);
		error_occurred |= NT_ERR_MALLOC;
		sark_free(new_sources);
		return;
	}
	uint32_t *new_recorded_value_buffer = sark_alloc(
		MAX_NUM_RESULTS(new_num_sources, num_sinks), sizeof(uint32_t));
	if (!new_recorded_value_buffer) {
		ERROR("Could not allocate space for %d sources.\n", new_num_sources);
		error_occurred |= NT_ERR_MALLOC;
		sark_free(new_sources);
		sark_free(new_last_recorded);
		return;
	}
	
	// Set default values
	for (int i = 0; i < new_num_sources; i++) {
		new_sources[i].key = 0x00000000;
		new_sources[i].burst_period_steps = 0; // Not bursty
		new_sources[i].burst_duty_steps = 0; // No ticks on
		new_sources[i].burst_phase_steps = 0; // Default: all aligned
		new_sources[i].probability = 0x00000000; // 0%
		new_sources[i].payload = false;
		new_sources[i].sent_count = 0;
		new_sources[i].blocked_count = 0;
	}
	
	// Copy-across all previous sources which remain
	spin1_memcpy(new_sources, sources,
	             MIN(new_num_sources, num_sources) * sizeof(source_t));
	
	if (num_sources > 0)
		sark_free(sources);
	sources = new_sources;
	num_sources = new_num_sources;
	
	sark_free(last_recorded);
	last_recorded = new_last_recorded;
	sark_free(recorded_value_buffer);
	recorded_value_buffer = new_recorded_value_buffer;
}


/**
 * Change the number of sinks.
 */
void set_num_sinks(size_t new_num_sinks) {
	// Allocate a new array of sinks
	sink_t *new_sinks = sark_alloc(new_num_sinks, sizeof(sink_t));
	if (!new_sinks && new_num_sinks != 0) {
		ERROR("Could not allocate space for %d sinks.\n", new_num_sinks);
		error_occurred |= NT_ERR_MALLOC;
		return;
	}
	
	// Allocate new result arrays
	uint32_t *new_last_recorded = sark_alloc(
		MAX_NUM_RESULTS(num_sources, new_num_sinks), sizeof(uint32_t));
	if (!new_last_recorded) {
		ERROR("Could not allocate space for %d sinks.\n", new_num_sinks);
		error_occurred |= NT_ERR_MALLOC;
		sark_free(new_sinks);
		return;
	}
	uint32_t *new_recorded_value_buffer = sark_alloc(
		MAX_NUM_RESULTS(num_sources, new_num_sinks), sizeof(uint32_t));
	if (!new_recorded_value_buffer) {
		ERROR("Could not allocate space for %d sinks.\n", new_num_sinks);
		error_occurred |= NT_ERR_MALLOC;
		sark_free(new_sinks);
		sark_free(new_last_recorded);
		return;
	}
	
	// Set default values
	for (int i = 0; i < new_num_sinks; i++) {
		new_sinks[i].key = 0x00000000;
		new_sinks[i].arrived_count = 0;
	}
	
	// Copy-across all previous sinks which remain
	spin1_memcpy(new_sinks, sinks,
	             MIN(new_num_sinks, num_sinks) * sizeof(sink_t));
	
	if (num_sinks > 0)
		sark_free(sinks);
	sinks = new_sinks;
	num_sinks = new_num_sinks;
	
	sark_free(last_recorded);
	last_recorded = new_last_recorded;
	sark_free(recorded_value_buffer);
	recorded_value_buffer = new_recorded_value_buffer;
}


/**
 * Callback on MC packet arrival. Simply counts the packet.
 */
void on_mc_packet(uint key, uint payload)
{
	uint32_t count = key & 0xFF;
	key &= ~0xFF;
	
	for (int i = 0; i < num_sinks; i++)
		if (sinks[i].key == key)
			sinks[i].arrived_count++;
}


/**
 * Record a single snapshot of the network's activity.
 *
 * If first is 0, no data will be stored in SDRAM but the current counter
 * values will be sampled. Note that this function must be called with first ==
 * true at the start of each run, otherwise the recorded values will be
 * invalid.
 */
void record(bool first)
{
	int num_results = 0;
	
	#define APPEND_RESULT(value) do { \
			/* Record the change in counter value */ \
			recorded_value_buffer[num_results] = (value) - last_recorded[num_results]; \
			/* Remember the current value to allow changes to be detected */ \
			last_recorded[num_results] = (value); \
			num_results++; \
	} while (0)
	
	// Record router counters.
	for (int counter = 0; counter < NUM_ROUTER_COUNTERS; counter++) {
		if (to_record & (1u << counter)) {
			uint32_t value = (((uint32_t *)RTR_BASE) + RTR_DGC0)[counter];
			APPEND_RESULT(value);
		}
	}
	
	// Record reinjector counters.
	for (int counter = 0; counter < NUM_REINJECTOR_COUNTERS; counter++) {
		if (to_record & (1u << (counter + 16))) {
			uint32_t value = ((uint32_t *)reinjector_counters)[counter];
			APPEND_RESULT(value);
		}
	}
	
	// Record source/sink counters
	if (to_record & RECORD_SENT_BIT)
		for (int source = 0; source < num_sources; source++)
			APPEND_RESULT(sources[source].sent_count);
	if (to_record & RECORD_BLOCKED_BIT)
		for (int source = 0; source < num_sources; source++)
			APPEND_RESULT(sources[source].blocked_count);
	if (to_record & RECORD_RECEIVED_BIT)
		for (int sink = 0; sink < num_sinks; sink++)
			APPEND_RESULT(sinks[sink].arrived_count);
	
	if (!first && num_results > 0) {
		// DMA the results into SDRAM
		if (!spin1_dma_transfer(DMA_WRITE, sdram_next_results, recorded_value_buffer, DMA_WRITE,
		                        num_results * sizeof(uint32_t))) {
			ERROR("DMA transfer of %d bytes failed.\n", num_results * sizeof(uint32_t));
			error_occurred |= NT_ERR_DMA;
		}
		
		// Advance the SDRAM pointer to the next free space
		sdram_next_results += num_results;
	}
	
	#undef APPEND_RESULT
}


/**
 * Run the traffic generator for the specified number of samples.
 *
 * Returns error code if a timing deadline was missed or false otherwise.
 */
uint32_t run(uint32_t time_left_steps)
{
	// The number of timing deadlines missed
	uint32_t deadlines_missed = 0;
	uint32_t num_steps = time_left_steps;
	
	// Tick 0 should occur immediately
	int32_t next_timestep_ticks = (int32_t)tc2[TC_COUNT];
	
	// This value counts down until the next recording should be made.
	uint32_t record_elapsed_steps = 0;
	
	// Take an initial sample of any counters being recorded
	record(true);
	
	// Generate traffic in a busy loop to maximise timing accuracy
	while (time_left_steps != 0) {
		// Wait until a timestep has ellapsed. (Note that tc2 is a down-counter).
		int32_t time_ticks = (int32_t)tc2[TC_COUNT];
		if (time_ticks - next_timestep_ticks > 0)
			continue;
		next_timestep_ticks -= (uint32_t)timestep_ticks;
		if (time_ticks - next_timestep_ticks <= 0)
			deadlines_missed++;
		time_left_steps--;
		
		for (int i = 0; i < num_sources; i++) {
			// Only generate packets when in the correct phase if bursting (or all the
			// time if not).
			bool burst;
			if (sources[i].burst_period_steps != 0) {
				burst = sources[i].burst_phase_steps < sources[i].burst_duty_steps;
				
				if (++sources[i].burst_phase_steps >= sources[i].burst_period_steps)
					sources[i].burst_phase_steps = 0;
			} else {
				burst = true;
			}
			
			// Generate packets for each packet source
			if (burst) {
				bool generate = (sources[i].probability == 0xFFFFFFFFu)
				              || (sark_rand() < sources[i].probability);
				
				if (generate) {
					bool sent = spin1_send_mc_packet(sources[i].key, 0xDEADBEEF,
					                                 sources[i].payload);
					if (sent)
						sources[i].sent_count++;
					else
						sources[i].blocked_count++;
				}
			}
		}
		
		// If the recording interval has elapsed, record the state of the network.
		if (record_interval_steps > 0
		    && ++record_elapsed_steps >= record_interval_steps) {
			record_elapsed_steps = 0;
			record(false);
		}
	}
	
	// If only recording a single sample for the whole run (record_interval_steps
	// == 0), take a final recording now.
	if (record_interval_steps == 0)
		record(false);
	
	uint32_t errors = (deadlines_missed ? NT_ERR_DEADLINE_MISSED : 0) |
	                  (deadlines_missed > (num_steps / 2)
	                   ? NT_ERR_MOST_DEADLINES_MISSED
	                   : 0);
	error_occurred |= errors;
	return errors;
}


/**
 * The main interpreter loop which interprets commands until a NT_CMD_EXIT is
 * encountered at which point the application is stopped and the function
 * returns.
 */
void interpreter_main(uint commands_ptr, uint arg1)
{
	uint32_t *commands = (uint32_t *)commands_ptr;
	
	INFO("Starting main loop with first command at 0x%08x\n",
	          commands);
	
	while (1) {
		// Extract the command identifier
		int command = ((*commands) >> 0) & 0xFF;
		
		// Extract the sink/source number (if present)
		int num = ((*commands) >> 8) & 0xFF;
		
		DEBUG("Executing command 0x%02x at 0x%08x...\n", command, commands);
		
		commands++;
		
		switch (command) {
			default:
				error_occurred |= NT_ERR_UNKNOWN_COMMAND;
				ERROR("Unrecognised command '0x%02x' at 0x%08x\n", *commands, commands);
				// Fall through to NT_CMD_EXIT
			
			case NT_CMD_EXIT:
				sdram_block[0] = error_occurred;
				INFO("network_tester exiting with %s errors\n",
				     error_occurred ? "some" : "no");
				spin1_exit((int)error_occurred);
				return;
			
			case NT_CMD_SLEEP:
				spin1_delay_us(*(commands++));
				break;
			
			case NT_CMD_BARRIER:
				event_wait();
				break;
			
			case NT_CMD_SEED:
				sark_srand(*(commands++));
				break;
			
			case NT_CMD_TIMESTEP:
				timestep_ticks = (int32_t)NS_TO_TICKS(*(commands++));
				break;
			
			case NT_CMD_RUN:
				if (run(*(commands++))) {
					ERROR("Timing deadline(s) missed during run\n");
				}
				break;
			
			case NT_CMD_NUM:
				set_num_sources((*commands) & 0xFF);
				set_num_sinks(((*commands) >> 8) & 0xFF);
				commands++;
				break;
			
			case NT_CMD_ROUTER_TIMEOUT:
				old_router_timeout = rtr[RTR_CONTROL];
				rtr[RTR_CONTROL] = ( (rtr[RTR_CONTROL] & ~0xFFFF0000)
				                   | ((*commands) & 0xFFFF0000));
				commands++;
				break;
			
			case NT_CMD_ROUTER_TIMEOUT_RESTORE:
				rtr[RTR_CONTROL] = ( (rtr[RTR_CONTROL] & ~0xFFFF0000)
				                   | (old_router_timeout & 0xFFFF0000));
				break;
			
			case NT_CMD_REINJECTION_ENABLE:
			    rtr[RTR_CONTROL] = rtr[RTR_CONTROL] | RTR_DENABLE_MASK;
			    break;
			
			case NT_CMD_REINJECTION_DISABLE:
			    rtr[RTR_CONTROL] = rtr[RTR_CONTROL] & ~RTR_DENABLE_MASK;
			    break;
			
			case NT_CMD_RECORD:
				to_record = *(commands++);
				break;
			
			case NT_CMD_RECORD_INTERVAL:
				record_interval_steps = *(commands++);
				break;
			
			case NT_CMD_PROBABILITY:
				if (num < num_sources) {
					sources[num].probability = *(commands++);
				} else {
					commands++;
					ERROR("Source %d does not exist.\n", num);
					error_occurred |= NT_ERR_BAD_ARGUMENTS;
				}
				break;
			
			case NT_CMD_BURST_PERIOD:
				sources[num].burst_period_steps = *(commands++);
				break;
			
			case NT_CMD_BURST_DUTY:
				sources[num].burst_duty_steps = *(commands++);
				break;
			
			case NT_CMD_BURST_PHASE:
				sources[num].burst_phase_steps = *(commands++);
				break;
			
			case NT_CMD_SOURCE_KEY:
				if (num < num_sources) {
					DEBUG("Source key %d = 0x%08x\n", num, *commands);
					sources[num].key = *(commands++);
				} else {
					commands++;
					ERROR("Source %d does not exist.\n", num);
					error_occurred |= NT_ERR_BAD_ARGUMENTS;
				}
				break;
			
			case NT_CMD_PAYLOAD:
				if (num < num_sources) {
					sources[num].payload = true;
				} else {
					ERROR("Source %d does not exist.\n", num);
					error_occurred |= NT_ERR_BAD_ARGUMENTS;
				}
				break;
			
			case NT_CMD_NO_PAYLOAD:
				if (num < num_sources) {
					sources[num].payload = false;
				} else {
					ERROR("Source %d does not exist.\n", num);
					error_occurred |= NT_ERR_BAD_ARGUMENTS;
				}
				break;
			
			case NT_CMD_CONSUME:
				// Enables the interrupt on packet arrival
				vic[VIC_ENABLE] = 1 << CC_RDY_INT;
				break;
			
			case NT_CMD_NO_CONSUME:
				// Disables the interrupt on packet arrival causing the packets to
				// back-up in the network.
				vic[VIC_DISABLE] = 1 << CC_RDY_INT;
				break;
			
			case NT_CMD_SINK_KEY:
				if (num < num_sinks) {
					DEBUG("Sink key %d = 0x%08x\n", num, *commands);
					sinks[num].key = *(commands++);
				} else {
					commands++;
					ERROR("Sink %d does not exist.\n", num);
					error_occurred |= NT_ERR_BAD_ARGUMENTS;
				}
				break;
		}
	}
}

void c_main(void)
{
	// Work out CPU position
	uint32_t xy = spin1_get_chip_id();
	uint32_t x = (xy >> 8) | 0xFF;
	uint32_t y = (xy >> 0) | 0xFF;
	uint32_t p = spin1_get_core_id();
	INFO("Starting network_tester on chip %d %d core %d.\n", x, y, p);
	
	// Set default parameters
	to_record = 0x00000000; // Nothing
	record_interval_steps = 0;
	timestep_ticks = US_TO_TICKS(100);
	
	// Initially have no sources/sinks
	num_sources = 0;
	num_sinks = 0;
	
	// Accept MC packets
	spin1_callback_on(MC_PACKET_RECEIVED, on_mc_packet, -1);
	spin1_callback_on(MCPL_PACKET_RECEIVED, on_mc_packet, -1);
	
	// Allocate space for storing results (this may be reallocated later)
	last_recorded = sark_alloc(
		MAX_NUM_RESULTS(num_sources, num_sinks), sizeof(uint32_t));
	if (!last_recorded) {
		ERROR("Could not allocate space last_recorded.\n");
		return;
	}
	recorded_value_buffer = sark_alloc(
		MAX_NUM_RESULTS(num_sources, num_sinks), sizeof(uint32_t));
	if (!recorded_value_buffer) {
		ERROR("Could not allocate space for recorded_value_buffer.\n");
		return;
	}
	
	// Get a pointer to the diagnostic counters used by the packet reinjector
	reinjector_counters = (reinjector_counters_t *)sark_tag_ptr(0xFF, 0);
	INFO("Reinjector counters are at address 0x%08x\n",
	     (uint)reinjector_counters);
	
	// Load the commands loaded into SDRAM by the host. The commands are prefixed
	// with a 32-bit integer giving the number of bytes worth of commands.
	sdram_block = (uint32_t *)sark_tag_ptr(p, 0);
	sdram_next_results = sdram_block + 1;
	uint32_t commands_length = sdram_block[0];
	uint32_t *commands = sark_alloc(commands_length, 1);
	if (commands == NULL) {
		ERROR("Failed to alloc %d bytes.\n", commands_length);
		return;
	}
	DEBUG("SDRAM (apparently) contains %d bytes of commands at 0x%08x...\n",
	      commands_length, sdram_block + 1);
	spin1_memcpy(commands, sdram_block + 1, commands_length);
	INFO("Copied %d bytes of commands from SDRAM...\n", commands_length);
	
	// While the experiment set the error result so that if results are read back
	// prematurely, the error code comes back bad.
	sdram_block[0] = NT_ERR_STILL_RUNNING;
	
	// Start the command interpreter as soon as the API starts
	spin1_schedule_callback(interpreter_main, (uint)commands, 0, 1);
	
	// Start timer 2 running at the CPU clock frequency, this is used for timing
	// packet generation.
	tc2[TC_CONTROL] = ( 1 << 7  // E: Enable the timer
	                  | 0 << 6  // M: Mode = Free-running
	                  | 0 << 5  // I: Interrupt disabled
	                  | 0 << 2  // Pre: Divide clock by 1
	                  | 1 << 1  // S: 32-bit mode
	                  | 0 << 0  // O: Wrapping mode, not one-shot
	                  );
	
	uchar old_soft_wdog;
	if (leadAp) {
		// Disable the software watchdog. This ensures that the traffic model
		// does not get watch-dogged by the monitor when heavy incoming traffic
		// load prevents it acknowledging the watchdog requests.
		INFO("Disabling soft_wdog\n");
		uchar old_soft_wdog = sv->soft_wdog;
		sv->soft_wdog = 0;
	}
	
	INFO("spin1_start\n");
	spin1_start(SYNC_NOWAIT);
	
	if (leadAp) {
		INFO("Restoring soft_wdog\n");
		sv->soft_wdog = old_soft_wdog;
	}
}
