import pytest

from mock import Mock

import struct

import numpy as np

from network_tester.results import Results, to_csv

from network_tester.experiment import Experiment

from network_tester.errors import NT_ERR

from network_tester.counters import Counters

from rig.place_and_route.routing_tree import RoutingTree
from rig.routing_table import Routes


@pytest.fixture
def example_experiment():
    """The experiment used in example_results."""
    return Experiment(Mock())


@pytest.fixture
def example_vertices(example_experiment):
    """The set of vertices used in example_results."""
    v0 = example_experiment.new_vertex("v0")
    v1 = example_experiment.new_vertex(1)
    v2 = example_experiment.new_vertex(2)
    v3 = example_experiment.new_vertex(3)
    v4 = example_experiment.new_vertex(4)
    return (v0, v1, v2, v3, v4)


@pytest.fixture
def example_nets(example_experiment, example_vertices):
    """The set of nets used in example_results."""
    v0, v1, v2, v3, v4 = example_vertices
    n0 = example_experiment.new_net(v0, [v2, v3], name="n0")
    n1 = example_experiment.new_net(v0, v1, name=1)
    n2 = example_experiment.new_net(v2, v2, name=2)
    return (n0, n1, n2)


@pytest.fixture
def example_groups(example_experiment):
    """The set of groups used in example_results."""
    with example_experiment.new_group(name="g0") as g0:
        g0.add_label("foobar", "foo")
        g0.add_label("only_group0", 1234)

        example_experiment.duration = 1.0
        example_experiment.record_interval = 0.0  # Just one recording

    with example_experiment.new_group(name=1) as g1:
        g1.add_label("foobar", "bar")
        g1.add_label("only_group1", 4321)

        example_experiment.duration = 0.2
        example_experiment.record_interval = 0.1

    return (g0, g1)


@pytest.fixture
def example_results(example_experiment, example_vertices, example_nets,
                    example_groups):
    """This fixture produces a Results object with a particular artificial set
    of results.
        +-------+
        | v4    |
        |       |
        |       |
        +-------+
         (0, 1)


        +-------+  n0    +-------+
        |  v0---+---+----+->v2-+n|
        |  |n1  |    \   |   ^-+2|
        |  v1   |     ----->v3   |
        +-------+        +-------+
         (0, 0)           (1, 0)

    In this system there are five vertices, v0-v4. Vertices 0-3 are nominally
    those inserted as part of the experiment. Vertex 4 is a vertex inserted for
    the purpose of recording router registers on chip (0, 1). This gives
    examples of both router-only vertices and dual-purpose vertices.

    Vertices 0, 2 and 4 record the external_p2p, local_p2p and reinjected
    counters on their local router. All vertices record packets send and
    packets received by any nets at that vertex.

    The vertices are named by their number, except for v0 which is named "v0".

    There are three nets, n0-n2.
    * Net 0 is sourced by vertex 0 and is sunk by v2 and v3 giving an example
      of a multicast net.
    * Net 1 is also sourced by vertex 0 and is sunk by v1 which gives a unicast
      net and also shows multiple nets sourced at a single vertex.
    * Net 2 is sourced and sunk by vertex 2 giving an example of a cyclic net
      and also a vertex with multiple sunk nets.
    Vertices 1 and 3 give examples of vertices with no sourced nets. Vertices 0
    and 4 give an example of vertices with no sunk nets.

    The nets are named by their number, except for n0 which is named "n0".

    There are two experimental groups, group 0 and group 1.
    * Group 0 lasts 1 second and has one recorded sample. It has two labelled
      values: foobar = "foo" and only_group0 = 1234. It has the name "g0"
      (a string).
    * Group 1 lasts 0.2 seconds and has two recorded samples, one at 0.1
      seconds and the other at 0.2 seconds. It has two labelled values: foobar
      = "bar" and only_group1 = 4321. It has the name 1 (an integer). Just to
      make the two distinguishable, every counter will be one count higher in
      the second sample for group one.

    In all examples, the traffic through each net will be:
    * Net 0: 20 packets per second.
    * Net 1: 30 packets per second.
    * Net 2: 40 packets per second.

    Further, the router counters on each chip will increment as follows:
    * (0, 0) local_p2p 10 packets per second.
    * (0, 0) external_p2p 20 packets per second.
    * (0, 0) reinjected 70 packets per second.
    * (1, 0) local_p2p 30 packets per second.
    * (1, 0) external_p2p 40 packets per second.
    * (1, 0) reinjected 80 packets per second.
    * (0, 1) local_p2p 50 packets per second.
    * (0, 1) external_p2p 60 packets per second.
    * (0, 1) reinjected 90 packets per second.
    """
    v0, v1, v2, v3, v4 = example_vertices
    n0, n1, n2 = example_nets

    # The last router-recording-only vertex is not listed in the vertex list
    vertices = [v0, v1, v2, v3]

    router_recording_vertices = set([v0, v2, v4])
    placements = {v0: (0, 0),
                  v1: (0, 0),
                  v2: (1, 0),
                  v3: (1, 0),
                  v4: (0, 1)}
    routes = {
        n0: RoutingTree((0, 0),
                        set([(Routes.east,
                              RoutingTree((1, 0),
                                          set([(Routes.core_1, v2),
                                               (Routes.core_2, v3)])))])),
        n1: RoutingTree((0, 0),
                        set([(Routes.core_2, v1)])),
        n2: RoutingTree((1, 0),
                        set([(Routes.core_1, v2)])),
    }
    vertices_records = {v0: [((0, 0), Counters.local_p2p),
                             ((0, 0), Counters.external_p2p),
                             ((0, 0), Counters.reinjected),
                             (n0, Counters.sent),
                             (n1, Counters.sent)],
                        v1: [(n1, Counters.received)],
                        v2: [((1, 0), Counters.local_p2p),
                             ((1, 0), Counters.external_p2p),
                             ((1, 0), Counters.reinjected),
                             (n2, Counters.sent),
                             (n0, Counters.received),
                             (n2, Counters.received)],
                        v3: [(n0, Counters.received)],
                        v4: [((0, 1), Counters.local_p2p),
                             ((0, 1), Counters.external_p2p),
                             ((0, 1), Counters.reinjected)]}

    def pack(*args):
        """Pack a series of result values."""
        return struct.pack("<I{}I".format(len(args)),
                           0x00000000,  # No errors
                           *args)

    vertices_result_data = {
        #         lp2p,ep2p,rein,n0src,n1src
        v0: pack(10, 20, 70, 20, 30,  # g0s0
                 1, 2, 7, 2, 3,  # g1s0
                 2, 3, 8, 3, 4),  # g1s1
        #         n1snk
        v1: pack(30,  # g0s0
                 3,  # g1s0
                 4),  # g1s1
        #         lp2p,ep2p,rein,n2src,n0snk,n2snk
        v2: pack(30, 40, 80, 40, 20, 40,  # g0s0
                 3, 4, 8, 4, 2, 4,  # g1s0
                 4, 5, 9, 5, 3, 5),  # g1s1
        #         n0snk
        v3: pack(20,  # g0s0
                 2,  # g1s0
                 3),  # g1s1
        #         lp2p,ep2p,rein
        v4: pack(50, 60, 90,  # g0s0
                 5, 6, 9,  # g1s0
                 6, 7, 10),  # g1s1
    }

    r = Results(example_experiment, vertices, example_nets, vertices_records,
                router_recording_vertices, placements, routes,
                vertices_result_data, example_groups)

    return r


@pytest.mark.parametrize("num_vertices,num_nets_per_vertex", [
    # Absolutely nothing
    (0, 0),
    # Nothing to record with various numbers of
    # nets/vertices doesn't do anything
    (1, 0),
    (1, 1),
    (2, 2),
])
def test_empty(num_vertices, num_nets_per_vertex):
    """Test that we can produce a Result object for various scenarios where no
    results will exist."""
    experiment = Experiment(Mock())

    vertices = [experiment.new_vertex() for _ in range(num_vertices)]
    nets = [experiment.new_net(v, v)
            for v in vertices
            for _ in range(num_nets_per_vertex)]
    router_recording_vertices = set()
    placements = {v: (0, 0) for v in vertices}
    routes = {n: RoutingTree((0, 0),
                             set([(Routes.core(vertices.index(n.sinks[0])),
                                   n.sinks[0])]))
              for n in nets}
    vertices_result_data = {v: b"\0\0\0\0" for v in vertices}
    groups = {}
    vertices_records = {v: [] for v in vertices}

    r = Results(experiment, vertices, nets, vertices_records,
                router_recording_vertices, placements, routes,
                vertices_result_data, groups)

    assert r.errors == set()

    assert len(r.totals()) == 0
    assert len(r.vertex_totals()) == 0
    assert len(r.net_totals()) == 0
    assert len(r.net_counters()) == 0
    assert len(r.router_counters()) == 0


@pytest.mark.parametrize("vertices_result_data,expected_errors", [
    # No errors
    ([], set()),
    ([b"\0\0\0\0"], set()),
    ([b"\0\0\0\0", b"\0\0\0\0"], set()),
    # Non-overlapping errors should get merged
    ([b"\x01\0\0\0"], set([NT_ERR.STILL_RUNNING])),
    ([b"\x01\0\0\0", b"\x02\0\0\0"],
     set([NT_ERR.STILL_RUNNING, NT_ERR.MALLOC])),
    # Overlapping errors should also get merged
    ([b"\x01\0\0\0", b"\x01\0\0\0"],
     set([NT_ERR.STILL_RUNNING])),
])
def test_errors(vertices_result_data, expected_errors):
    """Test that we can produce a Result object for various scenarios where no
    results will exist."""
    experiment = Experiment(Mock())

    vertices_result_data = {experiment.new_vertex(): d
                            for d in vertices_result_data}
    vertices = list(vertices_result_data)
    nets = []
    router_recording_vertices = set()
    placements = {}
    routes = {}
    groups = {}
    vertices_records = {v: [] for v in vertices}

    r = Results(experiment, vertices, nets, vertices_records,
                router_recording_vertices, placements, routes,
                vertices_result_data, groups)

    assert r.errors == expected_errors

    if expected_errors:
        assert "error" in repr(r)
    else:
        assert "error" not in repr(r)


def test_num_samples(example_results):
    """Make sure the total sample count is correct."""
    assert example_results._num_samples == 3


def test_recorded(example_results):
    """Make sure full set of recorded counters is correct."""
    assert example_results._recorded == [Counters.local_p2p,
                                         Counters.external_p2p,
                                         Counters.reinjected,
                                         Counters.sent,
                                         Counters.received]


def test_vertices_results(example_results, example_vertices):
    """Make sure the results are unpacked correctly."""
    v0, v1, v2, v3, v4 = example_vertices
    model_vertices_results = {
        #             lp2p,ep2p,rein,n0src,n1src
        v0: np.array([[10, 20, 70, 20, 30],  # g0s0
                      [1, 2, 7, 2, 3],  # g1s0
                      [2, 3, 8, 3, 4]],  # g1s1
                     dtype=np.uint),
        #             n1snk
        v1: np.array([[30],  # g0s0
                      [3],  # g1s0
                      [4]],  # g1s1
                     dtype=np.uint),
        #             lp2p,ep2p,rein,n2src,n0snk,n2snk
        v2: np.array([[30, 40, 80, 40, 20, 40],  # g0s0
                      [3, 4, 8, 4, 2, 4],  # g1s0
                      [4, 5, 9, 5, 3, 5]],  # g1s1
                     dtype=np.uint),
        #             n0snk
        v3: np.array([[20],  # g0s0
                      [2],  # g1s0
                      [3]],  # g1s1
                     dtype=np.uint),
        #             lp2p,ep2p,rein
        v4: np.array([[50, 60, 90],  # g0s0
                      [5, 6, 9],  # g1s0
                      [6, 7, 10]],  # g1s1
                     dtype=np.uint),
    }
    for vertex in example_vertices:
        assert (example_results._vertices_results[vertex] ==
                model_vertices_results[vertex]).all()


def test_make_result_array(example_results, example_groups):
    """Make sure the common set of columns are correct."""
    g0, g1 = example_groups

    # Just the basic columns
    a = example_results._make_result_array([])
    assert a.dtype.names == ("foobar",
                             "only_group0",
                             "only_group1",
                             "group",
                             "time")
    assert (a["foobar"] == np.array(["foo", "bar", "bar"], dtype=object)).all()
    assert (a["only_group0"] == np.array([1234, None, None],
                                         dtype=object)).all()
    assert (a["only_group1"] == np.array([None, 4321, 4321],
                                         dtype=object)).all()
    assert (a["group"] == np.array([g0, g1, g1], dtype=object)).all()
    assert (a["time"] == np.array([1.0, 0.1, 0.2], dtype=np.double)).all()

    # Adding additional columns should work
    a = example_results._make_result_array(["magic", ("moose", np.double)])
    assert a.dtype.names == ("foobar",
                             "only_group0",
                             "only_group1",
                             "group",
                             "time",
                             "magic",
                             "moose")
    assert (a["magic"] == np.array([0, 0, 0], dtype=np.uint)).all()
    assert (a["moose"] == np.array([0.0, 0.0, 0.0], dtype=np.double)).all()

    # Having multiple rows per sample should work too
    a = example_results._make_result_array(["magic", ("moose", np.double)],
                                           rows_per_sample=2)
    assert a.dtype.names == ("foobar",
                             "only_group0",
                             "only_group1",
                             "group",
                             "time",
                             "magic",
                             "moose")
    assert (a["foobar"] == np.array(["foo", "foo", "bar", "bar", "bar", "bar"],
                                    dtype=object)).all()
    assert (a["only_group0"] == np.array([1234, 1234, None, None, None, None],
                                         dtype=object)).all()
    assert (a["only_group1"] == np.array([None, None, 4321, 4321, 4321, 4321],
                                         dtype=object)).all()
    assert (a["group"] == np.array([g0, g0, g1, g1, g1, g1],
                                   dtype=object)).all()
    assert (a["time"] == np.array([1.0, 1.0, 0.1, 0.1, 0.2, 0.2],
                                  dtype=np.double)).all()
    assert (a["magic"] == np.array([0, 0, 0, 0, 0, 0],
                                   dtype=np.uint)).all()
    assert (a["moose"] == np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                                   dtype=np.double)).all()


def test_totals(example_results, example_groups):
    """Make sure the overall totals work."""
    g0, g1 = example_groups
    totals = example_results.totals()

    assert totals.dtype.names == ("foobar",
                                  "only_group0",
                                  "only_group1",
                                  "group",
                                  "time",
                                  "local_p2p",
                                  "external_p2p",
                                  "reinjected",
                                  "sent",
                                  "received",
                                  "ideal_received")
    assert (totals == np.array([("foo", 1234, None, g0,
                                 1.0, 90, 120, 240, 90, 110, 110),
                                ("bar", None, 4321, g1,
                                 0.1, 9, 12, 24, 9, 11, 11),
                                ("bar", None, 4321, g1,
                                 0.2, 12, 15, 27, 12, 15, 15)],
                               dtype=totals.dtype)).all()


def test_vertex_totals(example_results, example_groups, example_vertices):
    """Make sure the per-vertex totals work."""
    g0, g1 = example_groups
    # Note that the router-recording-only-vertex should be omitted
    v0, v1, v2, v3 = example_vertices[:4]
    totals = example_results.vertex_totals()

    assert totals.dtype.names == ("foobar",
                                  "only_group0",
                                  "only_group1",
                                  "group",
                                  "time",
                                  "vertex",
                                  "sent",
                                  "received",
                                  "ideal_received")
    assert (totals == np.array([("foo", 1234, None, g0, 1.0, v0, 50, 0, 0),
                                ("foo", 1234, None, g0, 1.0, v1, 0, 30, 30),
                                ("foo", 1234, None, g0, 1.0, v2, 40, 60, 60),
                                ("foo", 1234, None, g0, 1.0, v3, 0, 20, 20),
                                ("bar", None, 4321, g1, 0.1, v0, 5, 0, 0),
                                ("bar", None, 4321, g1, 0.1, v1, 0, 3, 3),
                                ("bar", None, 4321, g1, 0.1, v2, 4, 6, 6),
                                ("bar", None, 4321, g1, 0.1, v3, 0, 2, 2),
                                ("bar", None, 4321, g1, 0.2, v0, 7, 0, 0),
                                ("bar", None, 4321, g1, 0.2, v1, 0, 4, 4),
                                ("bar", None, 4321, g1, 0.2, v2, 5, 8, 8),
                                ("bar", None, 4321, g1, 0.2, v3, 0, 3, 3)],
                               dtype=totals.dtype)).all()


def test_net_totals(example_results, example_groups, example_nets):
    """Make sure the per-net totals work."""
    g0, g1 = example_groups
    n0, n1, n2 = example_nets
    totals = example_results.net_totals()

    assert totals.dtype.names == ("foobar",
                                  "only_group0",
                                  "only_group1",
                                  "group",
                                  "time",
                                  "net",
                                  "fan_out",
                                  "sent",
                                  "received")
    assert (totals == np.array([("foo", 1234, None, g0, 1.0, n0, 2, 20, 40),
                                ("foo", 1234, None, g0, 1.0, n1, 1, 30, 30),
                                ("foo", 1234, None, g0, 1.0, n2, 1, 40, 40),
                                ("bar", None, 4321, g1, 0.1, n0, 2, 2, 4),
                                ("bar", None, 4321, g1, 0.1, n1, 1, 3, 3),
                                ("bar", None, 4321, g1, 0.1, n2, 1, 4, 4),
                                ("bar", None, 4321, g1, 0.2, n0, 2, 3, 6),
                                ("bar", None, 4321, g1, 0.2, n1, 1, 4, 4),
                                ("bar", None, 4321, g1, 0.2, n2, 1, 5, 5)],
                               dtype=totals.dtype)).all()


def test_net_counters(example_results, example_groups, example_vertices,
                      example_nets):
    """Make sure the all sources/sinks counters work."""
    g0, g1 = example_groups
    # Note that the router-recording-only-vertex should be omitted
    v0, v1, v2, v3 = example_vertices[:4]
    n0, n1, n2 = example_nets
    counts = example_results.net_counters()

    assert counts.dtype.names == ("foobar",
                                  "only_group0",
                                  "only_group1",
                                  "group",
                                  "time",
                                  "net",
                                  "fan_out",
                                  "source_vertex",
                                  "sink_vertex",
                                  "num_hops",
                                  "sent",
                                  "received")
    assert (counts == np.array(
        [("foo", 1234, None, g0, 1.0, n0, 2, v0, v2, 1, 20, 20),
         ("foo", 1234, None, g0, 1.0, n0, 2, v0, v3, 1, 20, 20),
         ("foo", 1234, None, g0, 1.0, n1, 1, v0, v1, 0, 30, 30),
         ("foo", 1234, None, g0, 1.0, n2, 1, v2, v2, 0, 40, 40),
         ("bar", None, 4321, g1, 0.1, n0, 2, v0, v2, 1, 2, 2),
         ("bar", None, 4321, g1, 0.1, n0, 2, v0, v3, 1, 2, 2),
         ("bar", None, 4321, g1, 0.1, n1, 1, v0, v1, 0, 3, 3),
         ("bar", None, 4321, g1, 0.1, n2, 1, v2, v2, 0, 4, 4),
         ("bar", None, 4321, g1, 0.2, n0, 2, v0, v2, 1, 3, 3),
         ("bar", None, 4321, g1, 0.2, n0, 2, v0, v3, 1, 3, 3),
         ("bar", None, 4321, g1, 0.2, n1, 1, v0, v1, 0, 4, 4),
         ("bar", None, 4321, g1, 0.2, n2, 1, v2, v2, 0, 5, 5)],
        dtype=counts.dtype)).all()


def test_router_counters(example_results, example_groups):
    """Make sure the all router counters work."""
    g0, g1 = example_groups
    counts = example_results.router_counters()

    assert counts.dtype.names == ("foobar",
                                  "only_group0",
                                  "only_group1",
                                  "group",
                                  "time",
                                  "x",
                                  "y",
                                  "local_p2p",
                                  "external_p2p",
                                  "reinjected")
    assert (counts == np.array(
        [("foo", 1234, None, g0, 1.0, 0, 0, 10, 20, 70),
         ("foo", 1234, None, g0, 1.0, 1, 0, 30, 40, 80),
         ("foo", 1234, None, g0, 1.0, 0, 1, 50, 60, 90),
         ("bar", None, 4321, g1, 0.1, 0, 0, 1, 2, 7),
         ("bar", None, 4321, g1, 0.1, 1, 0, 3, 4, 8),
         ("bar", None, 4321, g1, 0.1, 0, 1, 5, 6, 9),
         ("bar", None, 4321, g1, 0.2, 0, 0, 2, 3, 8),
         ("bar", None, 4321, g1, 0.2, 1, 0, 4, 5, 9),
         ("bar", None, 4321, g1, 0.2, 0, 1, 6, 7, 10)],
        dtype=counts.dtype)).all()


def test_to_csv():
    """Make sure the CSV conversion utility actually works..."""
    dt = np.dtype([("a", np.uint), ("b", np.double), ("c", object)])

    e = Experiment(Mock())
    g0 = e.new_group("g0")
    g1 = e.new_group(1)
    v0 = e.new_vertex("v0")
    v1 = e.new_vertex(1)
    n0 = e.new_net(v0, v0, name="n0")
    n1 = e.new_net(v1, v1, name=1)

    # Empty dataset
    assert to_csv(np.zeros((0,), dtype=dt)) == "a,b,c"
    assert to_csv(np.zeros((0,), dtype=dt), False) == ""

    # Standard data types should be handled correctly
    a = np.zeros((2,), dtype=dt)
    assert to_csv(a) == ("a,b,c\n"
                         "0,0.0,0\n"
                         "0,0.0,0")
    assert to_csv(a, False) == ("0,0.0,0\n"
                                "0,0.0,0")

    # Nones should be printed specially
    a["c"][0] = None
    assert to_csv(a) == ("a,b,c\n"
                         "0,0.0,NA\n"
                         "0,0.0,0")

    # Groups, Nets and Vertices should be printed specially
    a = np.zeros((6,), dtype=dt)
    a["c"][0] = g0
    a["c"][1] = g1
    a["c"][2] = v0
    a["c"][3] = v1
    a["c"][4] = n0
    a["c"][5] = n1
    assert to_csv(a) == ("a,b,c\n"
                         "0,0.0,g0\n"
                         "0,0.0,1\n"
                         "0,0.0,v0\n"
                         "0,0.0,1\n"
                         "0,0.0,n0\n"
                         "0,0.0,1")
