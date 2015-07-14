"""Definition of the set of counters in the experiment."""

from enum import IntEnum


class Counters(IntEnum):
    """The list of recordable values.

    Each counter's numerical value is equal to the corresponding bit in the
    NT_CMD_RECORD command.
    """

    # Router counters
    local_multicast = 1 << 0
    external_multicast = 1 << 1
    local_p2p = 1 << 2
    external_p2p = 1 << 3
    local_nearest_neighbour = 1 << 4
    external_nearest_neighbour = 1 << 5
    local_fixed_route = 1 << 6
    external_fixed_route = 1 << 7
    dropped_multicast = 1 << 8
    dropped_p2p = 1 << 9
    dropped_nearest_neighbour = 1 << 10
    dropped_fixed_route = 1 << 11
    counter12 = 1 << 12
    counter13 = 1 << 13
    counter14 = 1 << 14
    counter15 = 1 << 15

    # Reinjector counters
    reinjected = 1 << 16
    reinject_overflow = 1 << 17
    reinject_missed = 1 << 18

    # Source counters
    sent = 1 << 24
    blocked = 1 << 25

    # Sink counters
    received = 1 << 28

    @property
    def router_counter(self):
        """True if a router counter."""
        return self <= (1 << 15)

    @property
    def reinjector_counter(self):
        """True if a reinjector counter."""
        return (1 << 16) <= self <= (1 << 23)

    @property
    def source_counter(self):
        """True if a source counter."""
        return (1 << 24) <= self <= (1 << 27)

    @property
    def sink_counter(self):
        """True if a sink counter."""
        return (1 << 28) <= self <= (1 << 31)
