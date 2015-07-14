/**
 * SpiNNaker network_tester.
 */

#ifndef NETWORK_TESTER_H
#define NETWORK_TESTER_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifndef MIN
#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#endif

#ifndef MAX
#define MAX(a, b) (((a) < (b)) ? (b) : (a))
#endif

// The bit in the router control register which enables interrupts on packet
// dropping. This is used to indirectly enable/disable the packet reinjector.
#define RTR_DENABLE_BIT 2
#define RTR_DENABLE_MASK (1 << RTR_DENABLE_BIT)

// Debug/info printing macros
#if false
#define DEBUG(...) io_printf(IO_BUF, "DEBUG: " __VA_ARGS__)
#else
#define DEBUG(...)
#endif

#define INFO(...) io_printf(IO_BUF, "INFO: " __VA_ARGS__)

#define ERROR(...) io_printf(IO_BUF, "ERROR: " __VA_ARGS__)

// Command codes
#define NT_CMD_EXIT 0x00
#define NT_CMD_SLEEP 0x01
#define NT_CMD_BARRIER 0x02
#define NT_CMD_SEED 0x03
#define NT_CMD_TIMESTEP 0x04
#define NT_CMD_RUN 0x05
#define NT_CMD_NUM 0x06
#define NT_CMD_ROUTER_TIMEOUT 0x07
#define NT_CMD_ROUTER_TIMEOUT_RESTORE 0x08
#define NT_CMD_REINJECTION_ENABLE 0x09
#define NT_CMD_REINJECTION_DISABLE 0x0A

#define NT_CMD_RECORD 0x10
#define NT_CMD_RECORD_INTERVAL 0x11

#define NT_CMD_PROBABILITY 0x20
#define NT_CMD_BURST_PERIOD 0x21
#define NT_CMD_BURST_DUTY 0x22
#define NT_CMD_BURST_PHASE 0x23
#define NT_CMD_SOURCE_KEY 0x24
#define NT_CMD_PAYLOAD 0x25
#define NT_CMD_NO_PAYLOAD 0x26

#define NT_CMD_CONSUME 0x30
#define NT_CMD_NO_CONSUME 0x31
#define NT_CMD_SINK_KEY 0x32

// Error status bits
#define NT_ERR_STILL_RUNNING (1 << 0)
#define NT_ERR_MALLOC (1 << 1)
#define NT_ERR_DMA (1 << 2)
#define NT_ERR_UNKNOWN_COMMAND (1 << 3)
#define NT_ERR_BAD_ARGUMENTS (1 << 4)
#define NT_ERR_DEADLINE_MISSED (1 << 5)
#define NT_ERR_MOST_DEADLINES_MISSED (1 << 6)


/**
 * A struct which defines a traffic source and its state.
 */
typedef struct {
	// The top 24 bits of this value are used as the key of the MC packets which
	// will be generated.
	uint32_t key;
	
	// Bursting traffic generation. See diagram in command format spec.
	uint32_t burst_period_steps;
	uint32_t burst_duty_steps;
	uint32_t burst_phase_steps;
	
	// Probability of a packet being injection each timestep. Probability is scaled
	// by (1<<32) with 0xFFFFFFFF being special-cased as "1".
	uint32_t probability;
	
	// Should generated packets include payloads?
	bool payload;
	
	// Count of packets which have been sent by this core
	uint32_t sent_count;
	
	// Count of packets which were attempted to be sent but which were blocked by
	// back-pressure from the network.
	uint32_t blocked_count;
} source_t;

/**
 * A struct which defines a traffic sink and its state.
 */
typedef struct {
	// The top 24 bits of this value are used as the key of the MC packets which
	// will be received.
	uint32_t key;
	
	// Count of packets which have arrived at this core
	uint32_t arrived_count;
} sink_t;

/**
 * The struct used by the packet reinjector for its status counters.
 */
typedef struct {
	// Number of packets reinjected
	uint32_t reinjected;
	// Number of packet queue overflows
	uint32_t reinject_overflow;
	// Number of times at least one packet wasn't removed from the router in
	// time.
	uint32_t reinject_missed;
} reinjector_counters_t;

#endif
