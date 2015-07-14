"""Top level experiment object."""

import pkg_resources

import time

import logging

from collections import OrderedDict

from six import iteritems, itervalues, integer_types

from rig.machine import Cores

from rig.machine_control import MachineController

from rig.netlist import Net as RigNet

from rig.place_and_route import place, allocate, route

from rig.place_and_route.utils import \
    build_routing_tables, build_application_map

from rig.place_and_route.constraints import ReserveResourceConstraint

from network_tester.commands import Commands

from network_tester.results import Results

from network_tester.counters import Counters

from network_tester.errors import NetworkTesterError


"""
This logger is used to report the progress of the Experiment.
"""
logger = logging.getLogger(__name__)


class Experiment(object):
    """Defines a network experiment to be run on a SpiNNaker machine.

    An experiment consists of a fixed set of 'vertices'
    (:py:meth:`.new_vertex`) connected together by 'nets'
    (:py:meth:`.new_net`). Vertices correspond with SpiNNaker application cores
    running artificial traffic generators and the nets correspond with traffic
    flows between cores.

    An experiment is broken up into 'groups' (:py:meth:`.new_group`), during
    which the traffic generators produce packets according to a specified
    traffic pattern. Within each group, metrics, such as packet counts, may be
    recorded. Though the placement of vertices and the routing of nets is
    fixed throughout an experiment, the rate and pattern with which which
    packets are produced can be varied between groups allowing, for example,
    different traffic patterns to be tested.

    When the experiment is :py:meth:`.run`, appropriately-configured traffic
    generator applications will be loaded onto SpiNNaker and, after the
    experiment completes, the results are read back ready for analysis.
    """

    def __init__(self, hostname_or_machine_controller):
        """Create a new network experiment on a particular SpiNNaker machine.

        Example usage::

            >>> import sys
            >>> from network_tester import Experiment
            >>> e = Experiment(sys.argv[1])  # Takes hostname as a CLI argument

        The experimental parameters can be set by setting attributes of the
        :py:class:`Experiment` instance like so::

            >>> e = Experiment(...)
            >>> # Set the probability of a packet being generated at the source
            >>> # of each net every timestep
            >>> e.probability = 1.0

        Parameters
        ----------
        hostname_or_machine_controller : \
                str or :py:class:`rig.machine_control.MachineController`
            The hostname or :py:class:`~rig.machine_control.MachineController`
            of a SpiNNaker machine to run the experiment on.
        """
        if isinstance(hostname_or_machine_controller, str):
            self._mc = MachineController(hostname_or_machine_controller)
        else:
            self._mc = hostname_or_machine_controller

        # A cached reference to the SpiNNaker machine the experiment will run
        # in. To be accessed via .machine which automatically fetches the
        # machine the first time it is requested.
        self._machine = None

        # A set of placements, allocations and routes for the
        # traffic-generating/consuming vertices.
        self._placements = None
        self._allocations = None
        self._routes = None

        # The experimental group currently being defined. Set and cleared on
        # entry and exit of Group context-managers.
        self._cur_group = None

        # A list of experimental groups which have been defined
        self._groups = []

        # A list of vertices in the experiment
        self._vertices = []

        # A list of nets in the experiment
        self._nets = []

        # Holds the value of every option along with any special cases.
        # If a value can have per-node or per-group exceptions it is stored as
        # a dictionary with keys (group, vert_or_net) with the value being
        # defined as below. Otherwise, the value is just stored immediately in
        # the _values dictionary. The list below gives the order of priority
        # for definitions.
        # * (None, None) The global default
        # * (group, None) The default for a particular experimental group
        # * (None, vertex) The default for a particular vertex
        # * (None, net) The default for a particular net
        # * (group, vertex) The value for a particular vertex in a specific
        #   group
        # * (group, net) The value for a particular net in a specific group
        # {option: value or {(group, vert_or_net): value, ...}, ...}
        self._values = {
            "seed": {(None, None): None},
            "timestep": {(None, None): 0.001},
            "warmup": {(None, None): 0.0},
            "duration": {(None, None): 1.0},
            "cooldown": {(None, None): 0.0},
            "flush_time": {(None, None): 0.01},
            "record_interval": {(None, None): 0.0},
            "probability": {(None, None): 1.0},
            "burst_period": {(None, None): 0.0},
            "burst_duty": {(None, None): 0.0},
            "burst_phase": {(None, None): 0.0},
            "use_payload": {(None, None): False},
            "consume_packets": {(None, None): True},
            "router_timeout": {(None, None): None},
            "reinject_packets": {(None, None): False},
        }

        # All counters are global-only options and default to False.
        for counter in Counters:
            self._values["record_{}".format(counter.name)] = False

    def new_vertex(self, name=None):
        """Create a new :py:class:`Vertex`.

        A vertex corresponds with a SpiNNaker application core and can produce
        or consume SpiNNaker packets.

        Example::

            >>> # Create three vertices
            >>> v0 = e.new_vertex()
            >>> v1 = e.new_vertex()
            >>> v2 = e.new_vertex()

        The experimental parameters for each vertex can also be overridden
        individually if desired::

            >>> # Nets sourced at vertex v2 will transmit with 50% probability
            >>> # each timestep
            >>> v2.probability = 0.5

        Parameters
        ----------
        name
            *Optional.* A name for the vertex. If not specified the vertex will
            be given a number as its name. This name will be used in results
            tables.

        Returns
        -------
        :py:class:`Vertex`
            An object representing the vertex.
        """
        v = Vertex(self, name if name is not None else len(self._vertices))
        self._vertices.append(v)

        # Adding a new vertex invalidates any existing placement solution
        self.placements = None

        return v

    def new_net(self, source, sinks, weight=1.0, name=None):
        """Create a new net.

        A net represents a flow of SpiNNaker packets from one source vertex to
        many sink vertices.

        For example::

            >>> # A net with v0 as a source and v1 as a sink.
            >>> n0 = e.new_net(v0, v1)

            >>> # Another net with v0 as a source and both v1 and v2 as sinks.
            >>> n1 = e.new_net(v0, [v1, v2])

        The experimental parameters for each net can also be overridden
        individually if desired. This will take precedence over any overridden
        values set for the source vertex of the net.

        For example::

            >>> # Net n0 will generate a packet in 80% of timesteps
            >>> n0.probability = 0.8

        Parameters
        ----------
        source : :py:class:`Vertex`
            The source :py:class:`Vertex` of the net. A stream of packets will
            be generated by this vertex and sent to all sinks.

            Only :py:class:`Vertex` objects created by this
            :py:class:`Experiment` may be used.
        sinks : :py:class:`Vertex` or [:py:class:`Vertex`, ...]
            The sink :py:class:`Vertex` or list of sink vertices for the net.

            Only :py:class:`Vertex` objects created by this
            :py:class:`Experiment` may be used.
        weight : float
            *Optional.* A hint for place and route tools indicating the
            relative amount of traffic that may flow through this net. This
            number is not used by the traffic generator.
        name
            *Optional.* A name for the net. If not specified the net will be
            given a number as its name. This name will be used in results
            tables.

        Returns
        -------
        :py:class:`Net`
            An object representing the net.
        """
        if name is None:
            name = len(self._nets)
        n = Net(self, name, source, sinks, weight)

        # Adding a new net invalidates any routing solution.
        self.routes = None

        self._nets.append(n)
        return n

    def new_group(self, name=None):
        """Define a new experimental group.

        The experiment can be divided up into groups where the traffic pattern
        generated (but not the structure of connectivity) varies for each
        group. Results are recorded separately for each group and the network
        is drained of packets between groups.

        The returned :py:class:`Group` object can be used as a context manager
        within which experimental parameters specific to that group may be set,
        including per-vertex and per-net parameters. Note that parameters set
        globally for the experiment in particular group do not take precedence
        over per-vertex or per-net parameter settings.

        For example::

            >>> with e.new_group():
            ...     # Overrides default probability of sending a packet within
            ...     # the group.
            ...     e.probability = 0.5
            ...     # Overrides the probability for v2 within the group
            ...     v2.probability = 0.25
            ...     # Overrides the probability for n0 within the group
            ...     n0.probability = 0.4

        Parameters
        ----------
        name
            *Optional.* A name for the group. If not specified the group will
            be given a number as its name. This name will be used in results
            tables.

        Returns
        -------
        :py:class:`Group`
            An object representing the group.
        """
        g = Group(self, name if name is not None else len(self._groups))
        self._groups.append(g)
        return g

    def run(self, app_id=0x42, create_group_if_none_exist=True,
            ignore_deadline_errors=False):
        """Run the experiment on SpiNNaker and return the results.

        If placements, allocations or routes have not been provided, the
        vertices and nets will be automatically placed, allocated and routed
        using the default algorithms in Rig.

        Following placement, the experimental parameters are loaded onto the
        machine and each experimental group is executed in turn. Results are
        recorded by the machine and at the end of the experiment are read back.

        .. warning::
            Though a global synchronisation barrier is used between the
            execution of each group, the timers in each vertex may drift out of
            sync during each group's execution. Further, the barrier
            synchronisation does not give any guarantees about how
            closely-synchronised the timers will be at the start of each run.

        Parameters
        ----------
        app_id : int
            *Optional.* The SpiNNaker application ID to use for the experiment.
        create_group_if_none_exist : bool
            *Optional.* If True (the default), a single group will be
            automatically created if none have been defined with
            :py:meth:`.new_group`. This is the most sensible behaviour for most
            applications.

            If you *really* want to run an experiment with no experimental
            groups (where no traffic will ever be generated and no results
            recorded), you can set this option to False.
        ignore_deadline_errors : bool
            If True, any realtime deadline-missed errors will no longer cause
            this method to raise an exception. Other errors will still cause an
            exception to be raised.

            This option is useful when running experiments which involve
            over-saturating packet sinks or the network in some experimental
            groups.

        Returns
        -------
        :py:class:`Results`
            If no vertices reported errors, the experimental results are
            returned.  See the :py:class:`Results` object for details.

        Raises
        ------
        NetworkTesterError
            A :py:exc:`NetworkTesterError` is raised if any vertices reported
            an error. The most common error is likely to be a 'deadline missed'
            error as a result of the experimental timestep being too short or
            the load on some vertices too high in extreme circumstances. Other
            types of error indicate far more severe problems.

            Any results recorded during the run will be included in the
            ``results`` attribute of the exception. See the :py:class:`Results`
            object for details.
        """
        # Sensible default: Create a single experimental group if none defined.
        if create_group_if_none_exist and len(self._groups) == 0:
            self.new_group()

        # Place and route the vertices (if required)
        self.place_and_route()

        # Add nodes to unused chips to access router registers/counters (if
        # necessary).
        (vertices, router_access_vertices,
         placements, allocations, routes) = \
            self._add_router_recording_vertices()

        # Assign a unique routing key to each net
        net_keys = {net: num << 8
                    for num, net in enumerate(self._nets)}
        routing_tables = build_routing_tables(
            routes,
            {net: (key, 0xFFFFFF00) for net, key in iteritems(net_keys)})

        network_tester_binary = pkg_resources.resource_filename(
            "network_tester", "binaries/network_tester.aplx")
        reinjector_binary = pkg_resources.resource_filename(
            "network_tester", "binaries/reinjector.aplx")

        # Specify the appropriate binary for the network tester vertices.
        application_map = build_application_map(
            {vertex: network_tester_binary for vertex in vertices},
            placements, allocations)

        # Get the set of source and sink nets for each vertex. Also sets an
        # explicit ordering of the sources/sinks within each.
        # {vertex: [source_or_sink, ...], ...}
        vertices_source_nets = {v: [] for v in vertices}
        vertices_sink_nets = {v: [] for v in vertices}
        for net in self._nets:
            vertices_source_nets[net.source].append(net)
            for sink in net.sinks:
                vertices_sink_nets[sink].append(net)

        vertices_records = self._get_vertex_record_lookup(
            vertices, router_access_vertices, placements,
            vertices_source_nets, vertices_sink_nets)

        # Fill out the set of commands for each vertex
        vertices_commands = {
            vertex: self._construct_vertex_commands(
                vertex=vertex,
                source_nets=vertices_source_nets[vertex],
                sink_nets=vertices_sink_nets[vertex],
                net_keys=net_keys,
                records=[cntr for obj, cntr in vertices_records[vertex]],
                router_access_vertex=vertex in router_access_vertices)
            for vertex in vertices
        }

        # The data size for the results from each vertex
        total_num_samples = sum(g.num_samples for g in self._groups)
        vertices_result_size = {
            vertex: (
                # The error flag (one word)
                1 +
                # One word per recorded value per sample.
                (total_num_samples * len(vertices_records[vertex]))
            ) * 4
            for vertex in vertices}

        # The raw result data for each vertex.
        vertices_result_data = {}

        # Actually load and run the experiment on the machine.
        with self._mc.application(app_id):
            # Allocate SDRAM. This is enough to fit the commands and also any
            # recored results.
            vertices_sdram = {}
            logger.info("Allocating SDRAM...")
            for vertex in vertices:
                size = max(
                    # Size of commands (with length prefix)
                    vertices_commands[vertex].size,
                    # Size of results (plus the flags)
                    vertices_result_size[vertex],
                )
                x, y = placements[vertex]
                p = allocations[vertex][Cores].start
                vertices_sdram[vertex] = self._mc.sdram_alloc_as_filelike(
                    size, x=x, y=y, tag=p)

            # Load each vertex's commands
            logger.info("Loading {} bytes of commands...".format(
                sum(c.size for c in itervalues(vertices_commands))))
            for vertex, sdram in iteritems(vertices_sdram):
                sdram.write(vertices_commands[vertex].pack())

            # Load routing tables
            logger.info("Loading routing tables...")
            self._mc.load_routing_tables(routing_tables)

            # Load the packet-reinjection application if used. This must be
            # completed before the main application since it creates a tagged
            # memory allocation.
            if self._reinjection_used():
                logger.info("Loading packet-reinjection application...")
                self._mc.load_application(reinjector_binary,
                                          {xy: set([1])
                                           for xy in self.machine})

            # Load the application
            logger.info("Loading application on to {} cores...".format(
                len(vertices)))
            self._mc.load_application(application_map)

            # Run through each experimental group
            next_barrier = "sync0"
            for group_num, group in enumerate(self._groups):
                # Reach the barrier before the run starts
                logger.info("Waiting for barrier...")
                num_at_barrier = self._mc.wait_for_cores_to_reach_state(
                    next_barrier, len(vertices), timeout=2.0)
                assert num_at_barrier == len(vertices), \
                    "Not all cores reached the barrier " \
                    "before {}.".format(group)

                self._mc.send_signal(next_barrier)
                next_barrier = "sync1" if next_barrier == "sync0" else "sync0"

                # Give the run time to complete
                warmup = self._get_option_value("warmup", group)
                duration = self._get_option_value("duration", group)
                cooldown = self._get_option_value("cooldown", group)
                flush_time = self._get_option_value("flush_time", group)
                total_time = warmup + duration + cooldown + flush_time

                logger.info(
                    "Running group {} ({} of {}) for {} seconds...".format(
                        group.name, group_num + 1, len(self._groups),
                        total_time))
                time.sleep(total_time)

            # Wait for all cores to exit after their final run
            logger.info("Waiting for barrier...")
            num_at_barrier = self._mc.wait_for_cores_to_reach_state(
                "exit", len(vertices), timeout=2.0)
            assert num_at_barrier == len(vertices), \
                "Not all cores reached the final barrier."

            # Read recorded data back
            logger.info("Reading back {} bytes of results...".format(
                sum(itervalues(vertices_result_size))))
            for vertex, sdram in iteritems(vertices_sdram):
                sdram.seek(0)
                vertices_result_data[vertex] = \
                    sdram.read(vertices_result_size[vertex])

        # Process read results
        results = Results(self, self._vertices, self._nets, vertices_records,
                          router_access_vertices, placements, routes,
                          vertices_result_data, self._groups)
        if any(not e.is_deadline if ignore_deadline_errors else True
               for e in results.errors):
            logger.error(
                "Experiment completed with errors: {}".format(results.errors))
            raise NetworkTesterError(results)
        else:
            logger.info("Experiment completed successfully")
            return results

    def place_and_route(self,
                        constraints=None,
                        place=place, place_kwargs={},
                        allocate=allocate, allocate_kwargs={},
                        route=route, route_kwargs={}):
        """Place and route the vertices and nets in the current experiment, if
        required.

        If extra control is required over placement and routing of vertices and
        nets in an experiment, this method allows additional constraints and
        custom placement, allocation and routing options and algorithms to be
        used.

        The result of placement, allocation and routing can be found in
        :py:attr:`placements`, :py:attr:`allocations` and  :py:attr:`routes`
        respectively.

        If even greater control is required, :py:attr:`placements`,
        :py:attr:`allocations` and  :py:attr:`routes` may be set explicitly.
        Once these attributes have been set, this method will not alter them.

        Since many applications will not care strongly about placement,
        allocation and routing, this method is called implicitly by
        :py:meth:`.run`.

        Parameters
        ----------
        constraints : [constraint, ...]
            A list of additional constraints to apply. A
            :py:class:`rig.place_and_route.constraints.ReserveResourceConstraint`
            will be applied to reserve the monitor processor on top of this
            constraint.
        place : placer
            A Rig-API complaint placement algorithm.
        place_kwargs : dict
            Additional algorithm-specific keyword arguments to supply to the
            placer.
        allocate : allocator
            A Rig-API complaint allocation algorithm.
        allocate_kwargs : dict
            Additional algorithm-specific keyword arguments to supply to the
            allocator.
        route : router
            A Rig-API complaint route algorithm.
        route_kwargs : dict
            Additional algorithm-specific keyword arguments to supply to the
            router.
        """
        # Each traffic generator consumes a core and a negligible amount of
        # memory.
        vertices_resources = {vertex: {Cores: 1} for vertex in
                              self._vertices}

        # Reserve the monitor processor for each chip
        constraints = constraints or []
        constraints += [ReserveResourceConstraint(Cores, slice(0, 1))]

        # Reserve a core for packet reinjection on each chip (if required)
        if self._reinjection_used():
            constraints += [ReserveResourceConstraint(Cores, slice(1, 2))]

        if self.placements is None:
            logger.info("Placing vertices...")
            self.placements = place(vertices_resources=vertices_resources,
                                    nets=self._nets,
                                    machine=self.machine,
                                    constraints=constraints,
                                    **place_kwargs)
            self.allocations = None
            self.routes = None

        if self.allocations is None:
            logger.info("Allocating vertices...")
            self.allocations = allocate(vertices_resources=vertices_resources,
                                        nets=self._nets,
                                        machine=self.machine,
                                        constraints=constraints,
                                        placements=self.placements,
                                        **allocate_kwargs)
            self.routes = None

        if self.routes is None:
            logger.info("Routing vertices...")
            self.routes = route(vertices_resources=vertices_resources,
                                nets=self._nets,
                                machine=self.machine,
                                constraints=constraints,
                                placements=self.placements,
                                allocations=self.allocations,
                                **allocate_kwargs)

    @property
    def placements(self):
        """A dictionary {:py:class:`Vertex`: (x, y), ...}, or None.

        Defines the chip on which each vertex will be placed during the
        experiment. Note that the placement must define the position of *every*
        vertex. If None, calling :py:meth:`.run` or :py:meth:`.place_and_route`
        will cause all vertices to be placed automatically.

        Setting this attribute will also set :py:attr:`.allocations` and
        :py:attr:`.routes` to None.

        Any placement must be valid for the :py:class:`~rig.machine.Machine`
        specified by the :py:attr:`.machine` attribute. Core 0 must always be
        reserved for the monitor processor and, if packet reinjection is used
        or recorded (see :py:attr:`Experiment.reinject_packets`), core 1 must
        also be reserved for the packet reinjection application.

        See also :py:func:`rig.place_and_route.place`.
        """
        return self._placements

    @placements.setter
    def placements(self, value):
        self._placements = value
        self.allocation = None
        self.routes = None

    @property
    def allocations(self):
        """A dictionary {:py:class:`Vertex`: {resource: slice}, ...} or None.

        Defines the resources allocated to each vertex. This must include
        exactly 1 unit of the :py:class:`~rig.machine.Cores` resource.  Note
        that the allocation must define the resource allocation of *every*
        vertex. If None, calling :py:meth:`.run` or :py:meth:`.place_and_route`
        will cause all vertices to have their resources allocated
        automatically.

        Setting this attribute will also set :py:attr:`.routes` to None.

        Any allocation must be valid for the :py:class:`~rig.machine.Machine`
        specified by the :py:attr:`.machine` attribute. Core 0 must always be
        reserved for the monitor processor and, if packet reinjection is used
        or recorded (see :py:attr:`Experiment.reinject_packets`), core 1 must
        also be reserved for the packet reinjection application.

        See also :py:func:`rig.place_and_route.allocate`.
        """
        return self._allocations

    @allocations.setter
    def allocations(self, value):
        self._allocations = value
        self.routes = None

    @property
    def routes(self):
        """A dictionary {:py:class:`Net`: \
        :py:class:`rig.place_and_route.routing_tree.RoutingTree`, ...} or None.

        Defines the route used for each net.  Note that the route must be
        defined for *every* net. If None, calling :py:meth:`.run` or
        :py:meth:`.place_and_route` will cause all nets to be routed
        automatically.

        See also :py:func:`rig.place_and_route.route`.
        """
        return self._routes

    @routes.setter
    def routes(self, value):
        self._routes = value

    def _any_router_registers_used(self):
        """Are any router registers (including reinjection counters) being
        recorded or configured during the experiment?"""
        return (any(self._get_option_value("record_{}".format(counter.name))
                    for counter in Counters if counter.router_counter) or
                self._get_option_value("router_timeout") is not None or
                any(self._get_option_value("router_timeout", g) is not None
                    for g in self._groups) or
                self._reinjection_used())

    def _reinjection_used(self):
        """Is dropped packet reinjection used (or recorded) in the
        experiment?
        """
        return (any(self._get_option_value("record_{}".format(counter.name))
                    for counter in Counters if counter.reinjector_counter) or
                self._get_option_value("reinject_packets") or
                any(self._get_option_value("reinject_packets", g)
                    for g in self._groups))

    @property
    def machine(self):
        """The :py:class:`~rig.machine.Machine` object describing the SpiNNaker
        system under test.

        This property caches the machine description read from the machine to
        avoid repeatedly polling the SpiNNaker system.
        """
        if self._machine is None:
            logger.info("Getting SpiNNaker machine information...")
            self._machine = self._mc.get_machine()
        return self._machine

    @machine.setter
    def machine(self, value):
        self._machine = value

    def _construct_vertex_commands(self, vertex, source_nets, sink_nets,
                                   net_keys, records, router_access_vertex):
        """For internal use. Produce the Commands for a particular vertex.

        Parameters
        ----------
        vertex : :py:class:`.Vertex`
            The vertex to pack
        source_nets : [:py:class:`.Net`, ...]
            The nets which are sourced at this vertex.
        sink_nets : [:py:class:`.Net`, ...]
            The nets which are sunk at this vertex.
        net_keys : {:py:class:`.Net`: key, ...}
            A mapping from net to routing key.
        records : [counter, ...]
            The set of counters this vertex records
        router_access_vertex : bool
            Should this vertex be used to configure router/reinjector
            parameters.
        """
        commands = Commands()

        # Set up the sources and sinks for the vertex
        commands.num(len(source_nets), len(sink_nets))
        for source_num, source_net in enumerate(source_nets):
            commands.source_key(source_num, net_keys[source_net])
        for sink_num, sink_net in enumerate(sink_nets):
            commands.sink_key(sink_num, net_keys[sink_net])

        # Generate commands for each experimental group
        for group in self._groups:
            # Set general parameters for the group
            commands.seed(self._get_option_value("seed", group))
            commands.timestep(self._get_option_value("timestep", group))
            commands.record_interval(self._get_option_value("record_interval",
                                                            group))

            # Set per-source parameters for the group
            for source_num, source_net in enumerate(source_nets):
                commands.burst(
                    source_num,
                    self._get_option_value("burst_period", group, source_net),
                    self._get_option_value("burst_duty", group, source_net),
                    self._get_option_value("burst_phase", group, source_net))
                commands.probability(
                    source_num,
                    self._get_option_value("probability",
                                           group,
                                           source_net))
                commands.payload(
                    source_num,
                    self._get_option_value("use_payload",
                                           group,
                                           source_net))

            # Synchronise before running the group
            commands.barrier()

            # Turn on reinjection as required
            if router_access_vertex:
                commands.reinject(
                    self._get_option_value("reinject_packets", group))

            # Turn off consumption as required
            commands.consume(
                self._get_option_value("consume_packets", group, vertex))

            # Set the router timeout
            router_timeout = self._get_option_value("router_timeout", group)
            if router_timeout is not None and router_access_vertex:
                if isinstance(router_timeout, integer_types):
                    commands.router_timeout(router_timeout)
                else:
                    commands.router_timeout(*router_timeout)

            # warming up without recording data
            commands.record()
            commands.run(self._get_option_value("warmup", group))

            # Run the actual experiment and record results
            commands.record(*records)
            commands.run(self._get_option_value("duration", group))

            # Run without recording (briefly) after the experiment to allow
            # for clock skew between cores.
            commands.record()  # Record nothing during cooldown
            commands.run(self._get_option_value("cooldown", group))

            # Restore router timeout, turn consumption back on and reinjection
            # back off after the run
            commands.consume(True)
            if router_timeout is not None and router_access_vertex:
                commands.router_timeout_restore()
            if router_access_vertex:
                commands.reinject(False)

            # Drain the network of any remaining packets
            commands.sleep(self._get_option_value("flush_time", group))

        # Finally, terminate
        commands.exit()

        return commands

    def _add_router_recording_vertices(self):
        """Adds extra vertices to chips with no other vertices to facilitate
        recording or setting of router counters and registers, if necessary.

        Returns
        -------
        (vertices, router_access_vertices, placements, allocations, routes)
            vertices is a list containing all vertices (including any added for
            router-recording purposes).

            router_access_vertices is set of vertices which are responsible
            for recording router counters or setting router registers on their
            core.

            placements, allocations and routes are updated sets of placements
            accounting for any new router-recording vertices.
        """
        # Make a local list of vertices, placements and allocations in the
        # model. This may be extended with extra vertices for recording router
        # counter values.
        vertices = self._vertices[:]
        placements = self.placements.copy()
        allocations = self.allocations.copy()
        routes = self.routes.copy()  # Not actually modified at present

        router_access_vertices = set()

        # The set of chips (x, y) which have a core allocated to recording
        # router counters.
        recorded_chips = set()

        # If router information is being recorded or the router registers are
        # changed, a vertex must be assigned on every chip to access these
        # registers.
        if self._any_router_registers_used():
            # Assign the job of recording/setting router registers to an
            # arbitrary vertex on every chip which already has vertices on it.
            for vertex, placement in iteritems(self.placements):
                if placement not in recorded_chips:
                    router_access_vertices.add(vertex)
                    recorded_chips.add(placement)

            # If there are chips without any vertices allocated, new
            # router-access-only vertices must be added.
            num_extra_vertices = 0
            for xy in self.machine:
                if xy not in recorded_chips:
                    # Create a new vertex for recording of router data only.
                    num_extra_vertices += 1
                    vertex = Vertex(self, "router access {}, {}".format(*xy))
                    router_access_vertices.add(vertex)
                    recorded_chips.add(xy)
                    placements[vertex] = xy
                    allocations[vertex] = {Cores: slice(2, 3)}
                    vertices.append(vertex)

            logger.info(
                "{} vertices added to access router registers".format(
                    num_extra_vertices))

        return (vertices, router_access_vertices,
                placements, allocations, routes)

    def _get_vertex_record_lookup(self, vertices, router_access_vertices,
                                  placements,
                                  vertices_source_nets, vertices_sink_nets):
        """Generates a lookup from vertex to a list of counters that vertex
        records.

        Parameters
        ----------
        vertices : [:py:class:`.Vertex`, ...]
        router_access_vertices : set([:py:class:`.Vertex`, ...])
        placements : {:py:class:`.Vertex`: (x, y), ...}
        vertices_source_nets : {:py:class:`.Vertex`: [net, ...], ...}
        vertices_sink_nets : {:py:class:`.Vertex`: [net, ...], ...}

        Returns
        -------
        vertices_records : {vertex: [(object, counter), ...], ...}
            For each vertex, gives an ordered-list of the things recorded by
            that vertex.

            For router counters, object will be a tuple (x, y) indicating which
            chip that counter is responsible for.

            For non-router counters, object will be the Net associated with the
            counter.
        """
        # Get the set of recorded counters for each vertex
        # {vertex, [counter, ...]}
        vertices_records = {}
        for vertex in vertices:
            records = []

            # Add any router-counters if this vertex is recording them
            if vertex in router_access_vertices:
                xy = placements[vertex]
                for counter in Counters:
                    if ((counter.router_counter or
                         counter.reinjector_counter) and
                            self._get_option_value(
                                "record_{}".format(counter.name))):
                        records.append((xy, counter))

            # Add any source counters
            for counter in Counters:
                if (counter.source_counter and
                        self._get_option_value(
                            "record_{}".format(counter.name))):
                    for net in vertices_source_nets[vertex]:
                        records.append((net, counter))

            # Add any sink counters
            for counter in Counters:
                if (counter.sink_counter and
                        self._get_option_value(
                            "record_{}".format(counter.name))):
                    for net in vertices_sink_nets[vertex]:
                        records.append((net, counter))

            vertices_records[vertex] = records

        return vertices_records

    def _get_option_value(self, option, group=None, vert_or_net=None):
        """For internal use. Get an option's value for a given
        group/vertex/net."""

        values = self._values[option]
        if isinstance(values, dict):
            if isinstance(vert_or_net, Net):
                vertex = vert_or_net.source
                net = vert_or_net
            else:
                vertex = vert_or_net

            global_value = values[(None, None)]
            group_value = values.get((group, None), global_value)
            vertex_value = values.get((None, vertex), group_value)
            group_vertex_value = values.get((group, vertex), vertex_value)

            if isinstance(vert_or_net, Net):
                net_value = values.get((None, net), group_vertex_value)
                group_net_value = values.get((group, net), net_value)
                return group_net_value
            else:
                return group_vertex_value
        else:
            return values

    def _set_option_value(self, option, value, group=None, vert_or_net=None):
        """For internal use. Set an option's value for a given
        group/vertex/net.
        """
        values = self._values[option]
        if isinstance(values, dict):
            values[(group, vert_or_net)] = value
        else:
            if group is not None or vert_or_net is not None:
                raise ValueError(
                    "Cannot set {} option on a group-by-group, "
                    "vertex-by-vertex or net-by-net basis.".format(option))
            self._values[option] = value

    class _Option(object):
        """A descriptor which provides access to the _values dictionary."""

        def __init__(self, option):
            self.option = option

        def __get__(self, obj, type=None):
            return obj._get_option_value(self.option, obj._cur_group)

        def __set__(self, obj, value):
            return obj._set_option_value(self.option, value, obj._cur_group)

    seed = _Option("seed")

    timestep = _Option("timestep")

    warmup = _Option("warmup")
    duration = _Option("duration")
    cooldown = _Option("cooldown")
    flush_time = _Option("flush_time")

    record_local_multicast = _Option("record_local_multicast")
    record_external_multicast = _Option("record_external_multicast")
    record_local_p2p = _Option("record_local_p2p")
    record_external_p2p = _Option("record_external_p2p")
    record_local_nearest_neighbour = _Option("record_local_nearest_neighbour")
    record_external_nearest_neighbour = _Option(
        "record_external_nearest_neighbour")
    record_local_fixed_route = _Option("record_local_fixed_route")
    record_external_fixed_route = _Option("record_external_fixed_route")
    record_dropped_multicast = _Option("record_dropped_multicast")
    record_dropped_p2p = _Option("record_dropped_p2p")
    record_dropped_nearest_neighbour = _Option(
        "record_dropped_nearest_neighbour")
    record_dropped_fixed_route = _Option("record_dropped_fixed_route")
    record_counter12 = _Option("record_counter12")
    record_counter13 = _Option("record_counter13")
    record_counter14 = _Option("record_counter14")
    record_counter15 = _Option("record_counter15")

    record_reinjected = _Option("record_reinjected")
    record_reinject_overflow = _Option("record_reinject_overflow")
    record_reinject_missed = _Option("record_reinject_missed")

    record_sent = _Option("record_sent")
    record_blocked = _Option("record_blocked")
    record_received = _Option("record_received")

    record_interval = _Option("record_interval")

    burst_period = _Option("burst_period")
    burst_duty = _Option("burst_duty")
    burst_phase = _Option("burst_phase")

    probability = _Option("probability")

    use_payload = _Option("use_payload")

    consume_packets = _Option("consume_packets")

    router_timeout = _Option("router_timeout")

    reinject_packets = _Option("reinject_packets")


class Vertex(object):
    """A vertex in the experiment, created by :py:meth:`Experiment.new_vertex`.

    A vertex represents a single core running a traffic generator/consumer.

    See :ref:`vertex parameters <vertex-attributes>` and :ref:`net parameters
    <net-attributes>` for experimental parameters associated with vertices.
    """

    def __init__(self, experiment, name):
        self._experiment = experiment
        self.name = name

    class _Option(object):
        """A descriptor which provides access to the experiment's _values
        dictionary."""

        def __init__(self, option):
            self.option = option

        def __get__(self, obj, type=None):
            return obj._experiment._get_option_value(
                self.option, obj._experiment._cur_group, obj)

        def __set__(self, obj, value):
            return obj._experiment._set_option_value(
                self.option, value, obj._experiment._cur_group, obj)

    seed = _Option("seed")

    burst_period = _Option("burst_period")
    burst_duty = _Option("burst_duty")
    burst_phase = _Option("burst_phase")

    probability = _Option("probability")

    use_payload = _Option("use_payload")

    consume_packets = _Option("consume_packets")

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, repr(self.name))


class Net(RigNet):
    """A connection between vertices, created by :py:meth:`Experiment.new_net`.

    This object inherits its attributes from :py:class:`rig.netlist.Net`.

    See :ref:`net parameters <net-attributes>` for experimental parameters
    associated with nets.
    """

    def __init__(self, experiment, name, *args, **kwargs):
        super(Net, self).__init__(*args, **kwargs)
        self._experiment = experiment
        self.name = name

    class _Option(object):
        """A descriptor which provides access to the experiment's _values
        dictionary."""

        def __init__(self, option):
            self.option = option

        def __get__(self, obj, type=None):
            return obj._experiment._get_option_value(
                self.option, obj._experiment._cur_group, obj)

        def __set__(self, obj, value):
            return obj._experiment._set_option_value(
                self.option, value, obj._experiment._cur_group, obj)

    burst_period = _Option("burst_period")
    burst_duty = _Option("burst_duty")
    burst_phase = _Option("burst_phase")

    probability = _Option("probability")

    use_payload = _Option("use_payload")

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, repr(self.name))


class Group(object):
    """An experimental group, created by :py:meth:`Experiment.new_group`."""

    def __init__(self, experiment, name):
        self._experiment = experiment
        self.name = name
        self.labels = OrderedDict()

    def add_label(self, name, value):
        """Set the value of a label results column for this group.

        Label columns can be used to give more meaning to each experimental
        group. For example::

            >>> for probability in [0.0, 0.5, 1.0]:
            ...     with e.new_group() as g:
            ...         g.add_label("probability", probability)
            ...         e.probability = probability

        In the example above, all results generated would feature a
        'probability' field with the corresponding value for each group making
        it much easier to plat experimental results.

        Parameters
        ----------
        name : str
            The name of the field.
        value
            The value of the field for this group.
        """
        self.labels[name] = value

    def __enter__(self):
        """Define parameters for this experimental group."""
        if self._experiment._cur_group is not None:
            raise Exception("Cannot nest experimental groups.")
        self._experiment._cur_group = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Completes the definition of this experimental group."""
        self._experiment._cur_group = None

    def __repr__(self):
        return "<{} {}>".format(self.__class__.__name__, repr(self.name))

    @property
    def num_samples(self):
        """The number of metric recordings which will be made during the
        execution of this group."""
        duration = self._experiment._get_option_value("duration", self)
        timestep = self._experiment._get_option_value("timestep", self)
        record_interval = \
            self._experiment._get_option_value("record_interval", self)

        run_steps = int(round(duration / timestep))
        interval_steps = int(round(record_interval / timestep))

        if interval_steps == 0:
            return 1
        else:
            return run_steps // interval_steps
