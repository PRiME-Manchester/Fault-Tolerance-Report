Network Tester Command Format
=============================

The network test program loaded on to each core is fed a simple command
sequence from the host which it will execute to determine what to do. The
sequence is made up of instructions which start with a 32-bit integer
indicating what operation to carry out. Each instruction type may then be
followed by a certain number of values.

All values are little endian and all instructions must be 32-bit word aligned.

All commands have a number in the range 0-255 which is specified in the 8 least
significant bits of the first word of each command. All other bits of this word
should be ignored unless otherwise specified.

Upon reading an unrecognised instruction number, the interpreter should halt
and report an error.

System commands
---------------

### 0x00: `NT_CMD_EXIT`

    +------------------+
    | 0x00             |
    +------------------+
          1 word

Terminate immediately and stop executing instructions.

### 0x01: `NT_CMD_SLEEP`

    +------------------+------------------+
    | 0x01             | usec             |
    +------------------+------------------+
          1 word             1 word

Sit idle (and don't execute any further instructions for usec microseconds.

### 0x02: `NT_CMD_BARRIER`

    +------------------+
    | 0x02             |
    +------------------+
          1 word

Block idle waiting for a SYNC0 or SYNC1 barrier. Calls to this will alternate
between the two SYNC types, starting with SYNC0.

### 0x03: `NT_CMD_SEED`

    +------------------+------------------+
    | 0x03             | seed             |
    +------------------+------------------+
          1 word             1 word

Seed the random number generator with the specified seed.

### 0x04: `NT_CMD_TIMESTEP`

    +------------------+------------------+
    | 0x04             | timestep_ns      |
    +------------------+------------------+
          1 word             1 word

How many nanoseconds should a timestep last? All further timing parameters will
be in terms of this unit.

### 0x05: `NT_CMD_RUN`

    +------------------+------------------+
    | 0x05             | steps            |
    +------------------+------------------+
          1 word             1 word

Run the traffic generator for the specified number of timesteps.

### 0x06: `NT_CMD_NUM`

    +------------------+-------------------+
    | 0x06             | num_src_snk       |
    +------------------+-------------------+
          1 word             1 word

Specify the number of traffic sources and sinks this traffic generator should
impelement. `num_src_snk` has the number of sources in bits 7:0 and the number
of sinks in bits 15:8.

### 0x07: `NT_CMD_ROUTER_TIMEOUT`

    +------------------+-------------------+
    | 0x07             | rtr_ctrl          |
    +------------------+-------------------+
          1 word             1 word

Configure the SpiNNaker router timeout. The top 16 bits of `rtr_ctrl` will be
written to the router control register.

### 0x08: `NT_CMD_ROUTER_TIMEOUT_RESTORE`

    +------------------+
    | 0x08             |
    +------------------+
          1 word

Restore the router timeout value just before the last call to
`NT_CMD_ROUTER_TIMEOUT`. If `NT_CMD_ROUTER_TIMEOUT` has not yet been called,
the result is undefined.

### 0x09: `NT_CMD_REINJECTION_ENABLE`

    +------------------+
    | 0x09             |
    +------------------+
          1 word

Enable packet reinjection. This command simply enables the router packet
dropped interrupt on the local router, it expects that another application on
that chip will handle the interrupt to facilitate packet reinjection.

### 0x0A: `NT_CMD_REINJECTION_DISABLE`

    +------------------+
    | 0x0A             |
    +------------------+
          1 word

Disable packet reinjection. This command simply disables the router packet
dropped interrupt on the local router. The packet reinjector application on
this chip is then free to drain its packet buffer at its leisure.


Result recording commands
-------------------------

### 0x10: `NT_CMD_RECORD`

    +------------------+-------------------+
    | 0x10             | to_record         |
    +------------------+-------------------+
          1 word              1 word

Enable or disable the recording of particular values during a run.

`to_record` is a bitmap with the following bits:

* `cnt[15:0]` each bit corresponds with a SpiNNaker router diagnostic counter
* `cnt[16]` Number of packets reinjected
* `cnt[17]` Number of reinjector queue overflows
* `cnt[18]` Number of times the router reported more than one packet being
            dropped before the reinjector could pick it up.
* `cnt[24]` number of sent packets
* `cnt[25]` number of blocked packets (e.g. not sent due to back-pressure)
* `cnt[28]` number of received MC packets

### 0x11: `NT_CMD_RECORD_INTERVAL`

    +------------------+------------------+
    | 0x11             | interval_steps   |
    +------------------+------------------+
          1 word             1 word

While the simulation is running, how frequently should results be recorded?
`interval_usec` gives the interval between samples in timesteps. The first
snapshot will be made at the moment the run begins.

A value of 0 will result in a value being recorded at the start and end of the
run only.



Packet generation commands
--------------------------

### 0x20: `NT_CMD_PROBABILITY`

    +------------------+------------------+
    | 0x21 | src<<8    | probability      |
    +------------------+------------------+
          1 word             1 word

The probability of a packet being generated each timestep for each traffic
source where the source number is specified in bits 15:8 of the command.

The probability of transmission is calculated as `probability`/(1<<32).
Special case: If probability is set to 0xFFFFFFFF then the probability of
transmission is set to one.

### 0x21-0x23: `NT_CMD_BURST_PERIOD`, `NT_CMD_BURST_DUTY`, `NT_CMD_BURST_PHASE`

    +------------------+------------------+
    | 0x22 | src<<8    | period_steps     |
    +------------------+------------------+
    +------------------+------------------+
    | 0x23 | src<<8    | duty_steps       |
    +------------------+------------------+
    +------------------+------------------+
    | 0x24 | src<<8    | phase_steps      |
    +------------------+------------------+
          1 word             1 word

To enable the simulation of bursting traffic, traffic generation can be
controlled with a particular duty cycle like so:

                                   period_steps
                        |------------------------------|
                              duty_steps
                             |-------|
                       phase_steps   |
                        |----|
                        .                              .
    send packets        .    +-------+                 .
                        .    |       |                 .
                        .    |       |                 .
      no packets  ...---.----+       +-----------------.---...
                        .                              .
                        .                              .

Special case: a `period_steps` of 0 disables this feature.

### 0x24: `NT_CMD_SOURCE_KEY`

    +------------------+------------------+
    | 0x25 | src<<8    | key              |
    +------------------+------------------+
          1 word             1 word

Sets the top 24 bits of the MC packet key to use for generated packets for the
source indicated by bits 15:8 of the command word.

The bottom 8 bits of the key supplied are ignored. The lower 8 bits are sent
with incrementing values to allow for (most) packet mis-orderings to be
detected at the receiver.

### 0x25: `NT_CMD_PAYLOAD`

    +------------------+
    | 0x26 | src<<8    |
    +------------------+
          1 word

Enables the sending of MC packets with payloads for generated packets for the
source indicated by bits 15:8 of the command word.

### 0x26: `NT_CMD_NO_PAYLOAD`

    +------------------+
    | 0x27 | src<<8    |
    +------------------+
          1 word

Disables the sending of MC packets with payloads for generated packets for the
source indicated by bits 15:8 of the command word.


Packet consumption commands
---------------------------

### 0x30: `NT_CMD_CONSUME`

    +------------------+
    | 0x30             |
    +------------------+
          1 word

Enable the consumption of packets from the network. Note that this also enables
the consumption of packets when not in `NT_CMD_CONSUME` though packets arriving
during these times will not be recorded.

### 0x31: `NT_CMD_NO_CONSUME`

    +------------------+
    | 0x31             |
    +------------------+
          1 word

Disable the consumption of packets from the network. Note that this also
prevents the consumption of packets when not in `NT_CMD_CONSUME`.

Note that it is strongly advised that after a period of non-consumption,
consumption be re-enabled and a short sleep performed to drain the network
before exiting or syncing.


### 0x32: `NT_CMD_SINK_KEY`

    +------------------+------------------+
    | 0x32 | snk<<8    | key              |
    +------------------+------------------+
          1 word             1 word

Sets the top 24 bits of the MC packet key expected for the sink number
indicated by bits 15:8 of the command.

The bottom 8 bits of the key supplied are ignored.


Result Format
-------------

The results of an experiment will be loaded starting at the same address the
commands were loaded from.

The first 32-bit word is a bit field indicating what errors ocurred during the
execution of the above commands. If this word is zero, nothing went wrong,
otherwise the bits which are set indicate what went wrong:

* Bit 0: `NT_ERR_STILL_RUNNING`: Not all commands have been executed yet.
* Bit 1: `NT_ERR_MALLOC`: Failed to allocate sufficient memory.
* Bit 2: `NT_ERR_DMA`: A DMA transfer failed.
* Bit 3: `NT_ERR_UNKNOWN_COMMAND`: An unknown command was encountered.
* Bit 4: `NT_ERR_BAD_ARGUMENTS`: A command was supplied with bad arguments.
* Bit 5: `NT_ERR_DEADLINE_MISSED`: A realtime deadline was missed.

