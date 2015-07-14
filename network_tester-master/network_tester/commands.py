"""Command stream construction for the network tester application to be run on
SpiNNaker."""

import struct

import random

from enum import IntEnum


class NT_CMD(IntEnum):
    """Network Tester command IDs."""

    EXIT = 0x00
    SLEEP = 0x01
    BARRIER = 0x02
    SEED = 0x03
    TIMESTEP = 0x04
    RUN = 0x05
    NUM = 0x06
    ROUTER_TIMEOUT = 0x07
    ROUTER_TIMEOUT_RESTORE = 0x08
    REINJECTION_ENABLE = 0x09
    REINJECTION_DISABLE = 0x0A

    RECORD = 0x10
    RECORD_INTERVAL = 0x11

    PROBABILITY = 0x20
    BURST_PERIOD = 0x21
    BURST_DUTY = 0x22
    BURST_PHASE = 0x23
    SOURCE_KEY = 0x24
    PAYLOAD = 0x25
    NO_PAYLOAD = 0x26

    CONSUME = 0x30
    NO_CONSUME = 0x31
    SINK_KEY = 0x32


class Commands(object):
    """A series of commands for a network tester application running on
    SpiNNaker."""

    def __init__(self):
        # The sequence of encoded commands to be executed, stored as a list of
        # 32-bit integers.
        self._commands = []

        self._exited = False

        # Was the seed last set using a randomly generated seed?
        self._seeded = False

        # What is the current timestep in seconds
        self._current_timestep = None

        # The current recording interval in seconds (if 0, record only at start
        # and end).
        self._current_record_interval = 0.0

        # The current number of sources and sinks
        self._num_sources = None
        self._num_sinks = None

        # What is currently being recorded?
        self._currently_recorded = 0

        # The current burst parameters, one for each source
        self._current_burst_period = None
        self._current_burst_duty = None
        self._current_burst_phase = None

        # Is packet reinjection enabled?
        self._reinject = False

        # A list of probabilities, one for each source.
        self._probability = None

        # A list of keys, one for each source
        self._source_key = None

        # A list of keys, one for each sink
        self._sink_key = None

        # A list of bools indicating whether a payload should be included with
        # generated packets, one for each source
        self._payload = None

        # A bool indicating whether packets should be consumed or not
        self._consume = True

    @property
    def size(self):
        """Get the size in bytes of the packed set of commands"""
        assert self._exited
        # One 32-bit word per command entry plus a 32-bit prefix giving the
        # length of the sequence of commands.
        return (len(self._commands) + 1) * 4

    def pack(self, format="<"):
        """Return the commands as a packed set of bytes."""
        assert self._exited
        return struct.pack("{}{}I".format(format, len(self._commands) + 1),
                           (len(self._commands) * 4),
                           *self._commands)

    def exit(self):
        """Terminate the network tester application."""
        assert not self._exited
        self._commands.append(NT_CMD.EXIT)
        self._exited = True

    def sleep(self, duration):
        """Sleep for the specified number of seconds."""
        assert not self._exited
        # Convert to usec
        duration = int(duration * 1e6)
        self._commands.extend([NT_CMD.SLEEP, duration])

    def barrier(self):
        """Wait for a sync barrier."""
        assert not self._exited
        self._commands.append(NT_CMD.BARRIER)

    def seed(self, seed=None):
        """Set the random number generator's seed.

        If the seed is None, the random number generator will be fed a Unique
        randomly generated seed unless the generator was last seeded with a
        randomly generated seed in which case the random number generator is
        not reseeded.

        If a non-null seed is provided, this seed is used.
        """
        assert not self._exited

        if seed is None:
            if not self._seeded:
                seed = random.getrandbits(32)
                self._seeded = True
        else:
            self._seeded = False

        if seed is not None:
            self._commands.extend([NT_CMD.SEED, seed])

    def timestep(self, timestep):
        """Set the timestep in seconds."""
        assert not self._exited

        # Don't bother setting the time step if not changed
        if timestep == self._current_timestep:
            return

        self._current_timestep = timestep

        # Convert to ns
        timestep = int(timestep * 1e9)
        self._commands.extend([NT_CMD.TIMESTEP, timestep])

        # Recalculate all values dependent on the time-step if required.
        record_interval = self._current_record_interval
        if record_interval != 0.0:
            self._current_record_interval = None
            self.record_interval(record_interval)

        burst_periods = self._current_burst_period
        if burst_periods is not None:
            for source_num, burst_period in enumerate(burst_periods):
                if burst_period != 0.0:
                    self._current_burst_period[source_num] = -1
                    self.burst(source_num,
                               burst_period,
                               self._current_burst_duty[source_num],
                               self._current_burst_phase[source_num])

    def run(self, duration):
        """Run the generator for a given number of seconds."""
        assert not self._exited
        # Convert to timesteps (round to soften the blow of floating point
        # precision issues)
        duration = int(round(duration / self._current_timestep))
        self._commands.extend([NT_CMD.RUN, duration])

    def num(self, num_sources, num_sinks):
        """Specify the number of sources and sinks.

        May only be done once. This is an artificial constraint to simplify
        result collection.
        """
        assert not self._exited

        assert self._num_sources is None
        assert self._num_sinks is None

        self._num_sources = num_sources
        self._num_sinks = num_sinks

        self._current_burst_period = [0.0] * num_sources
        self._current_burst_duty = [0.0] * num_sources
        self._current_burst_phase = [0.0] * num_sources
        self._probability = [0.0] * num_sources
        self._source_key = [0] * num_sources
        self._payload = [False] * num_sources

        self._sink_key = [0] * num_sinks

        self._commands.extend([NT_CMD.NUM, num_sources | (num_sinks << 8)])

    def router_timeout(self, wait1, wait2=0):
        """Set the router timeouts to use on the current chip.

        Parameters
        ----------
        wait1 : int
            The number of router clock cycles (typically at 133 MHz) to wait
            before attempting emergency routing. If emergency routing is
            disabled (wait2 == 0), the packet will be dropped after this delay.
        wait2 : int
            The number of router clock cycles to wait while trying to emergency
            route a packet. If set to 0, emergency routing is disabled.

        Raises
        ------
        ValueError
            These timeouts may only fall on certain values which can be encoded
            in the router control register. If a value passed cannot be encoded
            a ValueError is thrown.
        """
        assert not self._exited

        wait1 = wait_time_encode(wait1)
        wait2 = wait_time_encode(wait2)

        self._commands.extend([NT_CMD.ROUTER_TIMEOUT,
                               (wait2 << 24) | (wait1 << 16)])

    def router_timeout_restore(self):
        """Restore the router timeout to its value before the last call to
        :py:meth:`.router_timeout`. If :py:meth:`.router_timeout` has not been
        called, this command will produce undefined results.
        """
        assert not self._exited

        self._commands.append(NT_CMD.ROUTER_TIMEOUT_RESTORE)

    def reinject(self, enable):
        """Enable or disable dropped packet reinjection.
        """
        assert not self._exited

        if enable != self._reinject:
            if enable:
                self._commands.append(NT_CMD.REINJECTION_ENABLE)
            else:
                self._commands.append(NT_CMD.REINJECTION_DISABLE)

            self._reinject = enable

    def record(self, *counters):
        """Set the set of counters to record.

        Any counter in :py:class:`.Counters` may be specified. If a counter is
        not specified, it is assumed to be disabled.
        """
        assert not self._exited

        recorded = 0
        for counter in counters:
            recorded |= counter

        # Only set the recording set if it changes
        if recorded != self._currently_recorded:
            self._currently_recorded = recorded
            self._commands.extend([NT_CMD.RECORD, recorded])

    def record_interval(self, interval):
        """Set the interval between recording values in seconds. If 0, record
        only the counters at the end of the run.

        Any counter name in :py:class:`.Counters` may be specified. If a
        counter is not specified, it is assumed to be disabled.
        """
        assert not self._exited

        # Don't add the command if not required
        if self._current_record_interval != interval:
            self._current_record_interval = interval

            # Convert to ticks
            interval = int(round(interval / self._current_timestep))
            self._commands.extend([NT_CMD.RECORD_INTERVAL, interval])

    def probability(self, source_num, probability):
        """Set the generation probability of a particular source."""
        assert not self._exited
        assert source_num < self._num_sources

        # Only output if changed
        if self._probability[source_num] != probability:
            self._probability[source_num] = probability
            # Convert to value between 0 and 0xFFFFFFFF
            if probability == 1.0:
                probability = 0xFFFFFFFF
            else:
                probability = int(round(probability * (1 << 32)))
            self._commands.extend([NT_CMD.PROBABILITY | (source_num << 8),
                                   probability])

    def burst(self, source_num, period, duty, phase=0.0):
        """Set the bursting behaviour of the generator.

        Parameters
        ----------
        source_num : int
            The number of the traffic generator whose burst behaviour will be
            changed.
        period : float
            The number of seconds the bursting cycle period lasts.
        duty : float
            The proportion of the duty cycle to generate packets.
        phase : float or None
            The proportion of the way through the duty cycle the burst
            generator should start at. If None, this is set randomly.
        """
        assert not self._exited

        # Don't add the commands only when required
        if self._current_burst_period[source_num] != period:
            self._current_burst_period[source_num] = period

            # Force recomputation of these values
            self._current_burst_duty[source_num] = -1
            self._current_burst_phase[source_num] = -1

            # Convert to ticks
            period_ = int(round(period / self._current_timestep))
            self._commands.extend([NT_CMD.BURST_PERIOD | (source_num << 8),
                                   period_])

        # No other options are relevant when the period is set to 0 (i.e.
        # disabled)
        if period == 0:
            return

        if self._current_burst_duty[source_num] != duty:
            self._current_burst_duty[source_num] = duty

            # Convert to ticks
            duty = int(round((period * duty) / self._current_timestep))
            self._commands.extend([NT_CMD.BURST_DUTY | (source_num << 8),
                                   duty])

        if self._current_burst_phase[source_num] != phase:
            # Generate a random phase if requested (setting the current value
            # such that it will always be replaced)
            if phase is None:
                phase = random.random()
                self._current_burst_phase[source_num] = -1
            else:
                self._current_burst_phase[source_num] = phase

            # Convert to ticks
            phase = int(round((period * phase) / self._current_timestep))
            self._commands.extend([NT_CMD.BURST_PHASE | (source_num << 8),
                                   phase])

    def source_key(self, source_num, key):
        """Set the top 24-bits of the key for a traffic source."""
        assert not self._exited
        assert source_num < self._num_sources

        # Only output if changed
        key &= ~0xFF
        if self._source_key[source_num] != key:
            self._source_key[source_num] = key
            self._commands.extend([NT_CMD.SOURCE_KEY | (source_num << 8), key])

    def payload(self, source_num, payload):
        """Set the top 24-bits of the key for a traffic source."""
        assert not self._exited
        assert source_num < self._num_sources

        # Only output if changed
        if self._payload[source_num] != payload:
            self._payload[source_num] = payload
            self._commands.append((NT_CMD.PAYLOAD if payload else
                                   NT_CMD.NO_PAYLOAD) | (source_num << 8))

    def consume(self, consume):
        """Select whether packets are consumed or left in the network."""
        assert not self._exited

        # Only output if changed
        if self._consume != consume:
            self._consume = consume
            self._commands.append(NT_CMD.CONSUME if consume else
                                  NT_CMD.NO_CONSUME)

    def sink_key(self, sink_num, key):
        """Set the top 24-bits of the key for a traffic source."""
        assert not self._exited
        assert sink_num < self._num_sinks

        # Only output if changed
        key &= ~0xFF
        if self._sink_key[sink_num] != key:
            self._sink_key[sink_num] = key
            self._commands.extend([NT_CMD.SINK_KEY | (sink_num << 8), key])


def wait_time_decode(encoded_wait):
    """Decode a SpiNNaker router control register wait time value."""
    # Taken from the datasheet
    m = (encoded_wait >> 0) & 0xF
    e = (encoded_wait >> 4) & 0xF

    if e <= 4:
        return (m + 16 - (1 << (4 - e))) * (1 << e)
    else:
        return (m + 16) * (1 << e)


def wait_time_encode(wait):
    """Encode a given time into the format used by SpiNNaker router control
    registers.

    Raises
    ------
    ValueError
        If the supplied wait time cannot be represented exactly.
    """
    nearest = wait_time_decode(0)
    for encoded_wait in range(1 << 8):
        actual_wait = wait_time_decode(encoded_wait)
        if wait == actual_wait:
            return encoded_wait
        if abs(actual_wait - wait) < abs(nearest - wait):
            nearest = actual_wait

    raise ValueError("{} cannot be represented as a valid router wait time. "
                     "{} is the nearest supported value.".format(
                         wait, nearest))
