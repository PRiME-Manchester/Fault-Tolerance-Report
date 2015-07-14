"""Tests which run against actual SpiNNaker hardware.

These tests partly act as integration tests but also serve as tests of the
SpiNNaker application itself.
"""

import pytest

import numpy as np

from network_tester.experiment import Experiment

from network_tester.errors import NetworkTesterError


@pytest.fixture
def experiment(spinnaker_ip):
    return Experiment(spinnaker_ip)


def test_router_recording(experiment):
    """In this experiment, no traffic nodes are present but all router counters
    are recorded."""

    experiment.timestep = 1e-5  # 10us
    experiment.record_interval = 1e-3  # 1000us
    experiment.duration = 0.1  # 100,000us

    experiment.record_local_multicast = True
    experiment.record_external_multicast = True
    experiment.record_local_p2p = True
    experiment.record_external_p2p = True
    experiment.record_local_nearest_neighbour = True
    experiment.record_external_nearest_neighbour = True
    experiment.record_local_fixed_route = True
    experiment.record_external_fixed_route = True
    experiment.record_dropped_multicast = True
    experiment.record_dropped_p2p = True
    experiment.record_dropped_nearest_neighbour = True
    experiment.record_dropped_fixed_route = True
    experiment.record_counter12 = True
    experiment.record_counter13 = True
    experiment.record_counter14 = True
    experiment.record_counter15 = True

    experiment.new_group()

    results = experiment.run()

    router_counters = results.router_counters()

    # There should be more than one chip worth of counters
    chip_coordinates = set()
    for result in router_counters:
        chip_coordinates.add((result["x"], result["y"]))
    assert len(chip_coordinates) > 1
    assert len(router_counters) == len(chip_coordinates) * 100

    # Only nearest neighbour packets should be sent during the run (due to
    # SARK)
    assert np.sum(router_counters["local_multicast"]) == 0
    assert np.sum(router_counters["external_multicast"]) == 0
    assert np.sum(router_counters["local_p2p"]) == 0
    assert np.sum(router_counters["external_p2p"]) == 0
    assert np.sum(router_counters["local_nearest_neighbour"]) > 0
    assert np.sum(router_counters["external_nearest_neighbour"]) > 0
    assert np.sum(router_counters["local_fixed_route"]) == 0
    assert np.sum(router_counters["external_fixed_route"]) == 0
    assert np.sum(router_counters["dropped_multicast"]) == 0
    assert np.sum(router_counters["dropped_p2p"]) == 0
    assert np.sum(router_counters["dropped_fixed_route"]) == 0


def test_transmission(experiment):
    """In this experiment we check that the traffic generators all run at the
    rate expected."""

    experiment.timestep = 1e-4  # 100us
    experiment.record_interval = 1e-3  # 1000us
    experiment.duration = 1e-2  # 10000us

    experiment.record_sent = True

    experiment.probability = 1.0

    # No bursting for this pair
    v0 = experiment.new_vertex()
    v1 = experiment.new_vertex()
    n0 = experiment.new_net(v0, [v0, v1])

    # Bursting 40% of the time, twice during the run
    v2 = experiment.new_vertex()
    v3 = experiment.new_vertex()
    n1 = experiment.new_net(v2, [v2, v3])
    n1.burst_period = 5e-3  # 5000us
    n1.burst_duty = 0.4
    n1.burst_phase = 0.0

    # As above but phase-offset by 40%
    v4 = experiment.new_vertex()
    v5 = experiment.new_vertex()
    n2 = experiment.new_net(v4, [v4, v5])
    n2.burst_period = 5e-3  # 5000us
    n2.burst_duty = 0.4
    n2.burst_phase = 0.4

    # 0% probability
    v6 = experiment.new_vertex()
    v7 = experiment.new_vertex()
    n3 = experiment.new_net(v6, [v6, v7])
    n3.probability = 0.0

    # 50% probability
    v8 = experiment.new_vertex()
    v9 = experiment.new_vertex()
    n4 = experiment.new_net(v8, [v8, v9])
    n4.probability = 0.5

    experiment.new_group()
    results = experiment.run()

    net_totals = results.net_totals()

    # Packets should be sent every cycle
    assert (net_totals[net_totals["net"] == n0]["sent"] ==
            [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]).all()

    # Check duty-cycle is correct
    n1_sent = net_totals[net_totals["net"] == n1]["sent"]
    counts, bins = np.histogram(n1_sent, [0, 5, 11])
    assert (counts == [6, 4]).all()

    n2_sent = net_totals[net_totals["net"] == n2]["sent"]

    # Check the phase is adjusted
    assert (n2_sent == np.roll(n1_sent, -2)).all()

    # No packets should be sent
    assert (net_totals[net_totals["net"] == n3]["sent"] ==
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]).all()

    # Approximately 50% of packets should be sent
    assert 20 < np.sum(net_totals[net_totals["net"] == n4]["sent"]) < 80


def test_recipt(experiment):
    """In this experiment we simply check that multple arriving streams can be
    differentiated."""

    experiment.timestep = 1e-4  # 100us
    experiment.record_interval = 0
    experiment.duration = 1e-2  # 10000us

    experiment.record_received = True

    target = experiment.new_vertex()
    source0 = experiment.new_vertex()
    source1 = experiment.new_vertex()

    net0 = experiment.new_net(source0, target)
    net1 = experiment.new_net(source1, target)

    net0.probability = 0.25
    net1.probability = 0.75

    experiment.new_group()
    results = experiment.run()

    net_totals = results.net_totals()

    # Approximately the right number of packets should arrive for each counter
    assert 10 < np.sum(net_totals[net_totals["net"] == net0]["received"]) < 40
    assert 60 < np.sum(net_totals[net_totals["net"] == net1]["received"]) < 90


def test_consume(experiment):
    """In this experiment we check that toggling packet consumption causes
    packets to be dropped."""

    experiment.timestep = 1e-5  # 10us
    experiment.record_interval = 0
    experiment.duration = 1e-3  # 1000us

    experiment.record_received = True
    experiment.record_dropped_multicast = True

    target = experiment.new_vertex()
    source = experiment.new_vertex()
    net = experiment.new_net(source, target)
    net.probability = 1.0

    # The first group doesn't accept packets
    with experiment.new_group() as group_noconsume:
        experiment.consume_packets = False

    # The second group does (thus making sure the network gets flushed)
    with experiment.new_group() as group_consume:
        experiment.consume_packets = True

    results = experiment.run()

    totals = results.totals()
    totals_noconsume = totals[totals["group"] == group_noconsume]
    totals_consume = totals[totals["group"] == group_consume]

    # During the non-consuming phase, some packets must be dropped
    assert totals_noconsume["dropped_multicast"] > 0
    assert totals_noconsume["received"] == 0

    # During the consuming phase all packets should get through
    assert totals_consume["dropped_multicast"] == 0
    assert totals_consume["received"] >= 95


def test_impossible_deadline(experiment):
    """In this experiment we give a timestep less than a clock-cycle and make
    sure we get a deadline missed notification. We should, however, still have
    the right number of timesteps executed."""

    experiment.timestep = 1e-9  # 1ns
    experiment.warmup = 0
    experiment.duration = 1e-8  # 10ns
    experiment.cooldown = 0

    experiment.record_sent = True

    target = experiment.new_vertex()
    source = experiment.new_vertex()
    net = experiment.new_net(source, target)
    net.probability = 1.0

    experiment.new_group()

    # Should suffer from deadline issues.
    with pytest.raises(NetworkTesterError) as exc_info:
        experiment.run()
    assert "deadline" in str(exc_info.value).lower()

    # All packets should still have been sent
    assert exc_info.value.results.totals()["sent"] == 10
