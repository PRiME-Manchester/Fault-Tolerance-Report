from network_tester.counters import Counters


def test_counters_classes():
    # Make sure each of the counter types is identified correctly
    router_counters = set([Counters.local_multicast,
                           Counters.external_multicast,
                           Counters.local_p2p,
                           Counters.external_p2p,
                           Counters.local_nearest_neighbour,
                           Counters.external_nearest_neighbour,
                           Counters.local_fixed_route,
                           Counters.external_fixed_route,
                           Counters.dropped_multicast,
                           Counters.dropped_p2p,
                           Counters.dropped_nearest_neighbour,
                           Counters.dropped_fixed_route,
                           Counters.counter12,
                           Counters.counter13,
                           Counters.counter14,
                           Counters.counter15])
    reinjector_counters = set([Counters.reinjected,
                               Counters.reinject_overflow,
                               Counters.reinject_missed])
    source_counters = set([Counters.sent, Counters.blocked])
    sink_counters = set([Counters.received])

    for counter in Counters:
        if counter in router_counters:
            assert counter.router_counter
            assert not counter.reinjector_counter
            assert not counter.source_counter
            assert not counter.sink_counter
        elif counter in reinjector_counters:
            assert not counter.router_counter
            assert counter.reinjector_counter
            assert not counter.source_counter
            assert not counter.sink_counter
        elif counter in source_counters:
            assert not counter.router_counter
            assert not counter.reinjector_counter
            assert counter.source_counter
            assert not counter.sink_counter
        elif counter in sink_counters:
            assert not counter.router_counter
            assert not counter.reinjector_counter
            assert not counter.source_counter
            assert counter.sink_counter
        else:  # pragma: no cover
            assert False


def test_ordering():
    # Order of iteration *must* be the same as the order of the definition bits
    # since the order is used to indicate which result is which in the results.
    assert sorted(Counters, key=int) == list(int(c) for c in Counters)
