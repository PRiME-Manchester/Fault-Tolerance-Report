import pytest

import struct

from mock import Mock

from rig.machine import Machine

from network_tester.experiment import Experiment, Vertex, Net, Group

from network_tester.commands import NT_CMD

from network_tester.counters import Counters

from network_tester.errors import NetworkTesterError

from network_tester.results import Results


def test_hostname_or_machine_controler(monkeypatch):
    # If a hostname is passed in, a new MC should be made
    from network_tester import experiment
    mock_mc = Mock()
    monkeypatch.setattr(experiment, "MachineController", mock_mc)
    Experiment("localhost")
    mock_mc.assert_called_once_with("localhost")
    mock_mc.reset_mock()

    # If an MC is passed in, that should be used
    Experiment(mock_mc)
    assert not mock_mc.called


def test_new_functions():
    # Make sure the e.new_* functions all work as expected
    e = Experiment(Mock())

    # Types should be appropriate
    vertex0 = e.new_vertex()
    assert isinstance(vertex0, Vertex)
    net0 = e.new_net(vertex0, vertex0)
    assert isinstance(net0, Net)
    group0 = e.new_group()
    assert isinstance(group0, Group)

    # Everything should be given unique names
    vertex1 = e.new_vertex()
    net1 = e.new_net(vertex1, vertex1)
    group1 = e.new_group()
    assert vertex0.name != vertex1.name
    assert net0.name != net1.name
    assert group0.name != group1.name

    # Custom names should be allowed
    vertex_foo = e.new_vertex(name="foo")
    net_bar = e.new_net(vertex_foo, vertex_foo, name="bar")
    group_baz = e.new_group(name="baz")
    assert vertex_foo.name == "foo"
    assert net_bar.name == "bar"
    assert group_baz.name == "baz"

    # The objects should all give their name/type in their repr string
    assert repr(vertex0) == "<Vertex 0>"
    assert repr(net0) == "<Net 0>"
    assert repr(group0) == "<Group 0>"

    assert repr(vertex1) == "<Vertex 1>"
    assert repr(net1) == "<Net 1>"
    assert repr(group1) == "<Group 1>"

    assert repr(vertex_foo) == "<Vertex 'foo'>"
    assert repr(net_bar) == "<Net 'bar'>"
    assert repr(group_baz) == "<Group 'baz'>"


def test_option_getters_setters():
    """Make sure the internal option get/set API works."""
    e = Experiment(Mock())

    group0 = e.new_group()
    vertex0 = e.new_vertex()
    vertex1 = e.new_vertex()
    net0 = e.new_net(vertex0, vertex1)
    net1 = e.new_net(vertex1, vertex0)

    # Make sure the getters setters use specific values with the correct
    # priority.

    # Should get global (default) value
    assert e._get_option_value("timestep") == 0.001
    assert e._get_option_value("timestep", group=group0) == 0.001
    assert e._get_option_value("timestep", vert_or_net=vertex0) == 0.001
    assert e._get_option_value("timestep", vert_or_net=net0) == 0.001
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex0) == 0.001
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net0) == 0.001

    # Should be able to change the default value
    e._set_option_value("timestep", 0.1)
    assert e._get_option_value("timestep") == 0.1
    assert e._get_option_value("timestep", group=group0) == 0.1
    assert e._get_option_value("timestep", vert_or_net=vertex0) == 0.1
    assert e._get_option_value("timestep", vert_or_net=net0) == 0.1
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex0) == 0.1
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net0) == 0.1

    # Should be able to change the value for a particular vertex
    e._set_option_value("timestep", 0.5, vert_or_net=vertex0)
    assert e._get_option_value("timestep") == 0.1
    assert e._get_option_value("timestep", group=group0) == 0.1
    assert e._get_option_value("timestep", vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep", vert_or_net=net0) == 0.5
    assert e._get_option_value("timestep", vert_or_net=net1) == 0.1
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net0) == 0.5
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net1) == 0.1

    # Should be able to change the value for a particular net
    e._set_option_value("timestep", 0.6, vert_or_net=net0)
    assert e._get_option_value("timestep") == 0.1
    assert e._get_option_value("timestep", group=group0) == 0.1
    assert e._get_option_value("timestep", vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep", vert_or_net=net0) == 0.6
    assert e._get_option_value("timestep", vert_or_net=net1) == 0.1
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net0) == 0.6
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net1) == 0.1

    # Should be able to change the value for a particular group (vertex/net
    # values should override still)
    e._set_option_value("timestep", 1.0, group=group0)
    assert e._get_option_value("timestep") == 0.1
    assert e._get_option_value("timestep", group=group0) == 1.0
    assert e._get_option_value("timestep", vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep", vert_or_net=net0) == 0.6
    assert e._get_option_value("timestep", vert_or_net=net1) == 0.1
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net0) == 0.6
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net1) == 1.0

    # Should be able to change the value for a particular vertex-group pair and
    # the net value should still take priority
    e._set_option_value("timestep", 10.0, group=group0, vert_or_net=vertex0)
    assert e._get_option_value("timestep") == 0.1
    assert e._get_option_value("timestep", group=group0) == 1.0
    assert e._get_option_value("timestep", vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep", vert_or_net=net0) == 0.6
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex0) == 10.0
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net0) == 0.6

    # Should be able to change the value for a particular vertex-group pair and
    # implicitly set a net value which has not been overridden.
    e._set_option_value("timestep", 20.0, group=group0, vert_or_net=vertex1)
    assert e._get_option_value("timestep") == 0.1
    assert e._get_option_value("timestep", group=group0) == 1.0
    assert e._get_option_value("timestep", vert_or_net=vertex1) == 0.1
    assert e._get_option_value("timestep", vert_or_net=net1) == 0.1
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex1) == 20.0
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net1) == 20.0

    # Should be able to change the value for a particular net-group pair and
    # it should take priority over anything else in that group.
    e._set_option_value("timestep", 30.0, group=group0, vert_or_net=net0)
    assert e._get_option_value("timestep") == 0.1
    assert e._get_option_value("timestep", group=group0) == 1.0
    assert e._get_option_value("timestep", vert_or_net=vertex0) == 0.5
    assert e._get_option_value("timestep", vert_or_net=net0) == 0.6
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=vertex0) == 10.0
    assert e._get_option_value("timestep",
                               group=group0,
                               vert_or_net=net0) == 30.0

    # Should be able to get values which don't support exceptions
    assert e._get_option_value("record_sent") is False
    assert e._get_option_value("record_sent", group=group0) is False
    assert e._get_option_value("record_sent", vert_or_net=vertex0) is False
    assert e._get_option_value("record_sent",
                               group=group0,
                               vert_or_net=vertex0) is False

    # Should be able to set values which don't support exceptions
    e._set_option_value("record_sent", True)
    assert e._get_option_value("record_sent") is True
    assert e._get_option_value("record_sent", group=group0) is True
    assert e._get_option_value("record_sent", vert_or_net=vertex0) is True
    assert e._get_option_value("record_sent",
                               group=group0,
                               vert_or_net=vertex0) is True

    # Shouldn't be able to set exceptions to options which don't support them
    with pytest.raises(ValueError):
        e._set_option_value("record_sent", False, group=group0)
    with pytest.raises(ValueError):
        e._set_option_value("record_sent", False, vert_or_net=vertex0)
    with pytest.raises(ValueError):
        e._set_option_value("record_sent",
                            False,
                            group=group0,
                            vert_or_net=vertex0)


def test_option_descriptors():
    """Make sure the option descriptors work."""
    e = Experiment(Mock())

    # Defualts should work
    assert e.seed is None
    assert e.probability == 1.0

    # Should be able to set
    e.probability = 0.1
    assert e.probability == 0.1

    # Should be able to set exceptions for groups
    with e.new_group():
        assert e.probability == 0.1
        e.probability = 1.0
        assert e.probability == 1.0

    assert e.probability == 0.1

    # Should be able to set non-exception-supporting options globally
    assert e.record_sent is False
    e.record_sent = True
    assert e.record_sent is True

    # Should be able to set exceptions for vertices
    vertex0 = e.new_vertex()
    assert vertex0.probability == 0.1
    vertex0.probability = 0.5
    assert vertex0.probability == 0.5
    assert e.probability == 0.1

    # Should be able to set exceptions for nets
    net0 = e.new_net(vertex0, vertex0)
    assert net0.probability == 0.5
    net0.probability = 0.6
    assert net0.probability == 0.6
    assert vertex0.probability == 0.5
    assert e.probability == 0.1

    # Should be able to set exceptions in groups for vertices and nets
    with e.new_group():
        assert e.probability == 0.1
        assert vertex0.probability == 0.5
        assert net0.probability == 0.6

        # Group probability shouldn't override vertex/net probability
        e.probability = 1.0
        assert e.probability == 1.0
        assert vertex0.probability == 0.5
        assert net0.probability == 0.6

        # Group+vertex probability should take precidence (but not over nets)
        vertex0.probability = 10.0
        assert e.probability == 1.0
        assert vertex0.probability == 10.0
        assert net0.probability == 0.6

        # Group+net probability should take overall precidence
        net0.probability = 20.0
        assert e.probability == 1.0
        assert vertex0.probability == 10.0
        assert net0.probability == 20.0

        # Should be able to get non-exception supporting options
        assert e.record_sent is True

        # Shouldn't be able to set non-exception-supporting options
        with pytest.raises(ValueError):
            e.record_sent = False

    # ...but only within the group
    assert e.probability == 0.1
    assert vertex0.probability == 0.5
    assert net0.probability == 0.6


def test_group_num_samples():
    e = Experiment(Mock())

    # When the recording interval is zero, only one sample per group should be
    # made, regardless of group duration.
    with e.new_group() as group:
        e.record_interval = 0.0
        e.duration = 0.0
        assert group.num_samples == 1

    with e.new_group() as group:
        e.record_interval = 0.0
        e.duration = 10.0
        assert group.num_samples == 1

    # When the recording interval set longer than the group, no recordings
    # should be made.
    with e.new_group() as group:
        e.record_interval = 2.0
        e.duration = 1.0
        assert group.num_samples == 0

    # When the recording interval is equal to the group, duration, one
    # recording should be made.
    with e.new_group() as group:
        e.record_interval = 1.0
        e.duration = 1.0
        assert group.num_samples == 1

    # When the recording interval is a fraction of the group duration, the
    # appropriate number of recordings should be made.
    with e.new_group() as group:
        e.record_interval = 0.1
        e.duration = 1.0
        assert group.num_samples == 10


def test_non_nestable_groups():
    # Experimental groups must not be allowed to nest
    e = Experiment(Mock())

    with e.new_group() as group0:
        assert e._cur_group is group0

        with pytest.raises(Exception):
            with e.new_group():
                pass  # pragma: no cover

        # Group should not have been changed
        assert e._cur_group is group0


def test_group_labels():
    # Make sure groups can have labels added
    e = Experiment(Mock())
    group0 = e.new_group()
    group0.add_label("group", 123)
    group0.add_label("colour", "green")

    assert group0.labels == {
        "group": 123,
        "colour": "green",
    }


def test_new_net():
    # Make sure nets are created and the arguments are those supported by Rig's
    # net construct.
    e = Experiment(Mock())

    vertices = [e.new_vertex() for _ in range(10)]

    # Arguments should be passed through
    net = e.new_net(vertices[0], vertices[1:])
    assert isinstance(net, Net)
    assert net.source == vertices[0]
    assert net.sinks == vertices[1:]
    assert net.weight == 1.0

    # As should kwargs
    net = e.new_net(source=vertices[0], sinks=vertices[9], weight=123)
    assert isinstance(net, Net)
    assert net.source == vertices[0]
    assert net.sinks == [vertices[9]]
    assert net.weight == 123


def test_machine(monkeypatch):
    # Make sure lazy-loading of the machine works
    mock_machine = Mock()
    mock_mc = Mock()
    mock_mc.get_machine.return_value = mock_machine
    e = Experiment(mock_mc)

    # First time the machine should be fetched
    assert not mock_mc.get_machine.called
    assert e.machine is mock_machine
    assert mock_mc.get_machine.called
    mock_mc.get_machine.reset_mock()

    # Next time it shouldn't
    assert e.machine is mock_machine
    assert not mock_mc.get_machine.called

    # It shouldn't if set manually either...
    mock_machine2 = Mock()
    e.machine = mock_machine2
    assert e.machine is mock_machine2
    assert not mock_mc.get_machine.called

    # It should if reset manually
    e.machine = None
    assert e.machine is mock_machine
    assert mock_mc.get_machine.called


@pytest.mark.parametrize("router_register", [
    c.name for c in Counters if c.router_counter])
def test_any_router_registers_used(router_register):
    # Should return true if any router register is set to be recorded
    e = Experiment(Mock())

    # Should not be true by default
    assert not e._any_router_registers_used()

    # Should be true when any register enabled
    setattr(e, "record_{}".format(router_register), True)
    assert e._any_router_registers_used()

    # But not when disabled again
    setattr(e, "record_{}".format(router_register), False)
    assert not e._any_router_registers_used()

    # Should be true if reinjection is used
    e.reinject_packets = True
    assert e._any_router_registers_used()
    e.reinject_packets = False
    assert not e._any_router_registers_used()

    # Should be true when a timeout is set
    e.router_timeout = 16
    assert e._any_router_registers_used()
    e.router_timeout = (16, 16)
    assert e._any_router_registers_used()
    e.router_timeout = None
    assert not e._any_router_registers_used()
    with e.new_group():
        e.router_timeout = 16
    assert e._any_router_registers_used()


@pytest.mark.parametrize("reinjection_register", [
    c.name for c in Counters if c.reinjector_counter])
def test_reinjection_used(reinjection_register):
    # Should return true if any router register is set to be recorded
    e = Experiment(Mock())

    # Should not be true by default
    assert not e._reinjection_used()

    # Should be true when any register enabled
    setattr(e, "record_{}".format(reinjection_register), True)
    assert e._reinjection_used()

    # But not when disabled again
    setattr(e, "record_{}".format(reinjection_register), False)
    assert not e._reinjection_used()

    # Should be true when reinjection is enabled at any point
    e.reinject_packets = True
    assert e._reinjection_used()
    e.reinject_packets = False
    assert not e._reinjection_used()
    with e.new_group():
        e.reinject_packets = True
    assert e._reinjection_used()


@pytest.mark.parametrize("record_reinjected", [True, False])
def test_place_and_route(record_reinjected):
    mock_mc = Mock()
    mock_place = Mock()
    mock_allocate = Mock()
    mock_route = Mock()

    e = Experiment(mock_mc)
    e.record_reinjected = record_reinjected

    # Initially should call all functions
    e.place_and_route(place=mock_place,
                      allocate=mock_allocate,
                      route=mock_route)
    assert mock_place.called
    assert mock_allocate.called
    assert mock_route.called

    # Check constraints
    constraints = mock_place.mock_calls[0][2]["constraints"]
    if record_reinjected:
        assert len(constraints) == 2
    else:
        assert len(constraints) == 1

    mock_place.reset_mock()
    mock_allocate.reset_mock()
    mock_route.reset_mock()

    # Called again, nothing should be called
    e.place_and_route(place=mock_place,
                      allocate=mock_allocate,
                      route=mock_route)
    assert not mock_place.called
    assert not mock_allocate.called
    assert not mock_route.called

    # Setting the placements should cause others to run
    e.placements = None
    e.place_and_route(place=mock_place,
                      allocate=mock_allocate,
                      route=mock_route)
    assert mock_place.called
    assert mock_allocate.called
    assert mock_route.called
    mock_place.reset_mock()
    mock_allocate.reset_mock()
    mock_route.reset_mock()

    # Setting the allocations should cause allocation and routing
    e.allocations = None
    e.place_and_route(place=mock_place,
                      allocate=mock_allocate,
                      route=mock_route)
    assert not mock_place.called
    assert mock_allocate.called
    assert mock_route.called
    mock_allocate.reset_mock()
    mock_route.reset_mock()

    # Setting the routes should just cause routing to run
    e.routes = None
    e.place_and_route(place=mock_place,
                      allocate=mock_allocate,
                      route=mock_route)
    assert not mock_place.called
    assert not mock_allocate.called
    assert mock_route.called
    mock_route.reset_mock()

    # Creating a vertex should reset everything
    vertex = e.new_vertex()
    e.place_and_route(place=mock_place,
                      allocate=mock_allocate,
                      route=mock_route)
    assert mock_place.called
    assert mock_allocate.called
    assert mock_route.called
    mock_place.reset_mock()
    mock_allocate.reset_mock()
    mock_route.reset_mock()

    # Creating a net should reset the routes
    e.new_net(vertex, vertex)
    e.place_and_route(place=mock_place,
                      allocate=mock_allocate,
                      route=mock_route)
    assert not mock_place.called
    assert not mock_allocate.called
    assert mock_route.called
    mock_route.reset_mock()


@pytest.mark.parametrize("router_access_vertex", [True, False])
def test_construct_vertex_commands(router_access_vertex):
    # XXX: This test is *very* far from being complete. In particular, though
    # the problem supplied is realistic, the output is not checked thouroughly
    # enough.
    e = Experiment(Mock())

    # A simple example network as follows:
    #       n0
    #  v0 ---+--> v1
    #   |    '--> v2
    #   +-------> v3
    #      n1
    # We'll pretend all of them are on the same chip and vertex0 is the one
    # designated as the router-value recording vertex.

    vertex0 = e.new_vertex()
    vertex1 = e.new_vertex()
    vertex2 = e.new_vertex()
    vertex3 = e.new_vertex()

    vertices = [vertex0, vertex1, vertex2, vertex3]

    net0 = e.new_net(vertex0, [vertex1, vertex2])
    net1 = e.new_net(vertex0, vertex3)

    # Seed randomly
    e.seed = None

    e.timestep = 1e-6
    e.warmup = 0.001
    e.duration = 1.0
    e.cooldown = 0.001
    e.flush_time = 0.01

    e.record_sent = True

    e.reinject_packets = True

    # By default, nothing should send and everything should consume
    e.probability = 0.0
    e.consume = True
    e.router_timeout = 240

    # In group0, everything consumes and n0 sends 100% packets and n1 sends 50%
    # packets.
    with e.new_group():
        net0.probability = 1.0
        net1.probability = 0.5

    # In group1, nothing consumes and n0 and n1 send 100%
    with e.new_group():
        net0.probability = 1.0
        net1.probability = 1.0
        e.consume = False
        e.router_timeout = 0

    # In group2, we have a timeout with emergency routing enabled
    with e.new_group():
        e.router_timeout = (16, 16)

    net_keys = {net0: 0xAA00, net1: 0xBB00}

    vertices_source_nets = {
        vertex0: [net0, net1],
        vertex1: [],
        vertex2: [],
        vertex3: [],
    }
    vertices_sink_nets = {
        vertex0: [],
        vertex1: [net0],
        vertex2: [net0],
        vertex3: [net1],
    }

    vertex_commands = {
        vertex: e._construct_vertex_commands(
            vertex=vertex,
            source_nets=vertices_source_nets[vertex],
            sink_nets=vertices_sink_nets[vertex],
            net_keys=net_keys,
            records=[Counters.sent],
            router_access_vertex=router_access_vertex).pack()
        for vertex in vertices
    }

    # Make sure all vertices have the right number of sources/sinks set
    for vertex in vertices:
        commands = vertex_commands[vertex]
        num_sources = len(vertices_source_nets[vertex])
        num_sinks = len(vertices_sink_nets[vertex])
        ref_cmd = struct.pack("<II", NT_CMD.NUM,
                              (num_sources | num_sinks << 8))
        assert ref_cmd in commands

    # Make sure all vertices have the right set of sources and sinks
    for vertex in vertices:
        commands = vertex_commands[vertex]
        sources = vertices_source_nets[vertex]
        sinks = vertices_sink_nets[vertex]

        for source_num, source_net in enumerate(sources):
            ref_cmd = struct.pack("<II", NT_CMD.SOURCE_KEY | (source_num << 8),
                                  net_keys[source_net])
            assert ref_cmd in commands

        for sink_num, sink_net in enumerate(sinks):
            ref_cmd = struct.pack("<II", NT_CMD.SINK_KEY | (sink_num << 8),
                                  net_keys[sink_net])
            assert ref_cmd in commands

    # Make sure all vertices have the right set of timing values
    for vertex in vertices:
        commands = vertex_commands[vertex]

        ref_cmd = struct.pack("<II", NT_CMD.TIMESTEP, 1000)
        assert ref_cmd in commands

    # Make sure all vertices have the right timeout set
    for vertex in vertices:
        commands = vertex_commands[vertex]

        ref_cmd0 = struct.pack("<I", NT_CMD.ROUTER_TIMEOUT)
        ref_cmd1 = struct.pack("<I", NT_CMD.ROUTER_TIMEOUT_RESTORE)
        if router_access_vertex:
            assert ref_cmd0 in commands
            assert ref_cmd1 in commands
        else:
            assert ref_cmd0 not in commands
            assert ref_cmd1 not in commands

    # Make sure all vertices packet reinjection enabled if requested
    for vertex in vertices:
        commands = vertex_commands[vertex]

        ref_cmd0 = struct.pack("<I", NT_CMD.REINJECTION_ENABLE)
        ref_cmd1 = struct.pack("<I", NT_CMD.REINJECTION_DISABLE)
        if router_access_vertex:
            assert ref_cmd0 in commands
            assert ref_cmd1 in commands
        else:
            assert ref_cmd0 not in commands
            assert ref_cmd1 not in commands


def test_add_router_recording_vertices():
    # Make sure this internal utility adds extra vertices only when required.
    mock_mc = Mock()
    e = Experiment(mock_mc)

    machine = Machine(2, 2)
    mock_mc.get_machine.return_value = machine

    vertex0 = e.new_vertex()
    vertex1 = e.new_vertex()
    e.placements = {vertex0: (0, 0),
                    vertex1: (0, 0)}
    e.record_sent = True
    e.record_blocked = True
    e.record_received = True
    e.place_and_route()

    # If only recording vertex-specific values, no extra vertices should
    # appear.
    (vertices, router_recording_vertices,
     placements, allocations, routes) = \
        e._add_router_recording_vertices()
    assert vertices == [vertex0, vertex1]
    assert router_recording_vertices == set()
    assert placements == {vertex0: (0, 0), vertex1: (0, 0)}

    # If recording any router registers, a vertex must be allocated on every
    # chip, creating new ones when required.
    e.record_external_multicast = True
    (vertices, router_recording_vertices,
     placements, allocations, routes) =\
        e._add_router_recording_vertices()

    # Should have three extra vertices, one for each unused chip.
    assert len(vertices) == 5

    # The original vertices should still be there
    assert vertex0 in vertices
    assert vertex1 in vertices

    # There should be a router recording vertex on each chip
    assert sorted(placements[v] for v in router_recording_vertices) == \
        sorted(machine)

    # The vertex used on (0, 0) should be one we put there, not a new vertex
    assert (vertex0 in router_recording_vertices) ^ \
        (vertex1 in router_recording_vertices)


def test_get_vertex_record_lookup():
    # Make sure this internal utility produces appropriate results.
    e = Experiment(Mock())

    # Two vertices, one will eventually record router values, the other will
    # not.
    vertex0 = e.new_vertex()
    vertex1 = e.new_vertex()
    vertices = [vertex0, vertex1]
    placements = {vertex0: (0, 0), vertex1: (0, 0)}

    # Two nets, one connected loop-back, one connected to the other vertex.
    net0 = e.new_net(vertex0, vertex0)
    net1 = e.new_net(vertex0, vertex1)
    vertices_source_nets = {vertex0: [net0, net1], vertex1: []}
    vertices_sink_nets = {vertex0: [net0], vertex1: [net1]}

    # If nothing is being recorded, the sets should be empty.
    vertices_records = e._get_vertex_record_lookup(
        vertices, set(), placements, vertices_source_nets, vertices_sink_nets)
    assert vertices_records == {
        vertex0: [],
        vertex1: [],
    }

    # If only vertex counters are being used, they should be included
    e.record_sent = True
    e.record_received = True
    vertices_records = e._get_vertex_record_lookup(
        vertices, set(), placements, vertices_source_nets, vertices_sink_nets)
    assert vertices_records == {
        vertex0: [(net0, Counters.sent), (net1, Counters.sent),
                  (net0, Counters.received)],
        vertex1: [(net1, Counters.received)],
    }

    # If any routing table entries are present, they should be added to
    # anything in the router_recording_vertices lookup.
    router_recording_vertices = set([vertex0])
    e.record_external_multicast = True
    vertices_records = e._get_vertex_record_lookup(
        vertices,
        router_recording_vertices,
        placements,
        vertices_source_nets,
        vertices_sink_nets)
    assert vertices_records == {
        vertex0: [((0, 0), Counters.external_multicast),
                  (net0, Counters.sent), (net1, Counters.sent),
                  (net0, Counters.received)],
        vertex1: [(net1, Counters.received)],
    }


@pytest.mark.parametrize("auto_create_group", [True, False])
@pytest.mark.parametrize("samples_per_group",
                         [[],  # No groups
                          [1],
                          [1, 100]])
@pytest.mark.parametrize("num_vertices", [0, 1, 2])
@pytest.mark.parametrize("num_nets_per_vertex", [0, 1, 2])
@pytest.mark.parametrize("error,error_code", [(False, b"\0\0\0\0"),
                                              (True, b"\x20\0\0\0")])
@pytest.mark.parametrize("record", [True, False])
@pytest.mark.parametrize("reinject_packets", [True, False])
def test_run(auto_create_group, samples_per_group, num_vertices,
             num_nets_per_vertex, error, error_code, record, reinject_packets):
    """Make sure that the run command carries out an experiment as would be
    expected."""
    machine = Machine(3, 1)

    mock_mc = Mock()
    mock_mc.get_machine.return_value = machine

    mock_application_ctx = Mock()
    mock_application_ctx.__enter__ = Mock()
    mock_application_ctx.__exit__ = Mock()
    mock_mc.application.return_value = mock_application_ctx

    mock_mc.get_machine.return_value = machine

    if reinject_packets:
        # If reinjecting, a core is added to every chip
        mock_mc.wait_for_cores_to_reach_state.return_value = len(list(machine))
    else:
        # If not reinjecting, only the vertices are given cores
        mock_mc.wait_for_cores_to_reach_state.return_value = num_vertices

    def mock_sdram_file_read(size):
        return error_code + b"\0"*(size - 4)
    mock_sdram_file = Mock()
    mock_sdram_file.read.side_effect = mock_sdram_file_read

    mock_mc.sdram_alloc_as_filelike.return_value = mock_sdram_file

    e = Experiment(mock_mc)
    e.timestep = 1e-6
    e.warmup = 0.01
    e.duration = 0.01
    e.cooldown = 0.01
    e.flush_time = 0.01

    # Record the result of _construct_vertex_commands to allow checking of
    # memory allocation sizes
    construct_vertex_commands = e._construct_vertex_commands
    vertices_commands = {}

    def wrapped_construct_vertex_commands(vertex, *args, **kwargs):
        commands = construct_vertex_commands(vertex=vertex, *args, **kwargs)
        vertices_commands[vertex] = commands
        return commands
    e._construct_vertex_commands = Mock(
        side_effect=wrapped_construct_vertex_commands)

    if record:
        e.record_sent = True

    e.reinject_packets = reinject_packets

    # Create example vertices
    vertices = [e.new_vertex() for _ in range(num_vertices)]
    for v in vertices:
        for _ in range(num_nets_per_vertex):
            e.new_net(v, v)

    # Vertices are placed on sequential chips along the x-axis
    e.placements = {v: (x, 0) for x, v in enumerate(vertices)}

    # Create example groups
    for num_samples in samples_per_group:
        with e.new_group():
            e.record_interval = e.duration / float(num_samples)

    # The run should fail with an exception when expected.
    if error and (num_vertices > 0 or reinject_packets):
        with pytest.raises(NetworkTesterError) as exc_info:
            e.run(0x33, create_group_if_none_exist=auto_create_group)
        results = exc_info.value.results
    else:
        results = e.run(0x33, create_group_if_none_exist=auto_create_group)

    # The results should be of the correct type...
    assert isinstance(results, Results)

    # The results returned should be all zeros (since that is what was written
    # back)
    if record and num_vertices > 0 and num_nets_per_vertex > 0:
        assert sum(results.totals()["sent"]) == 0

    # The supplied app ID should be used
    mock_mc.application.assert_called_once_with(0x33)

    # If reinjection is enabled, the binary should have been loaded
    reinjector_loaded = any("reinjector.aplx" in call[1][0]
                            for call in mock_mc.load_application.mock_calls)
    if reinject_packets:
        assert reinjector_loaded
    else:
        assert not reinjector_loaded

    # Each chip should have been issued with a suitable malloc for any vertices
    # on it.
    for x, vertex in enumerate(vertices):
        cmds_size = vertices_commands[vertex].size
        if record:
            # The space required to record the sent counters.
            result_size = (1 + (num_nets_per_vertex *
                                sum(samples_per_group))) * 4
        else:
            result_size = 4  # Just the status value
        size = max(cmds_size, result_size)
        if reinject_packets:
            # During packet reinjection, core 1 is used.
            core_num = 2
        else:
            core_num = 1
        mock_mc.sdram_alloc_as_filelike.assert_any_call(size, x=x, y=0,
                                                        tag=core_num)

    # The correct number of barriers should have been reached
    num_groups = len(samples_per_group)
    if auto_create_group:
        num_groups = max(1, num_groups)
    assert len(mock_mc.send_signal.mock_calls) == num_groups
