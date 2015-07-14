SpiNNaker `network_tester` Kernel
=================================

The SpiNNaker applicatilon which generates traffic and records results on a
SpiNNaker machine.

Compilation
-----------

The latest version of the binary is checked into the respository meaning most
users will not need to build it. When changes are made, the binary can be
recompiled using:

    $ make

The makefile and library make use of
[`spinnaker_tools`](https://github.com/SpiNNakerManchester/spinnaker_tools).
