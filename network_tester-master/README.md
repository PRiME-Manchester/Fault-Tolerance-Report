SpiNNaker Network Tester
========================

[![Documentation](https://readthedocs.org/projects/network-tester/badge/?version=stable)](http://network-tester.readthedocs.org/en/stable/)
[![Build Status](https://travis-ci.org/project-rig/network_tester.svg?branch=master)](https://travis-ci.org/project-rig/network_tester)
[![Coverage Status](https://coveralls.io/repos/project-rig/network_tester/badge.svg?branch=master)](https://coveralls.io/r/project-rig/network_tester?branch=master)

‘Network Tester’ is a library designed to enable experimenters to quickly and
easily describe and run experiments on SpiNNaker‘s interconnection network. In
particular, network tester is designed to make recreating traffic loads similar
to typical neural software straight-forward. Such network loads feature a fixed
set of vertices (cores) which produce SpiNNaker packets which are then
multicast to a fixed set of vertices.

The following is a (non-exhaustive) list of the kinds of experiments which can
be performed with ‘Network Tester’:

* Determining how a network copes with different rates and patterns of packet
  generation. For example to determining the maximum speed at which a
  particular neural simulation may run on SpiNNaker without dropping packets.
* Determining the effectiveness of place and route algorithms by finding
  ‘hot-spots’ in the network.
* Characterising the behaviour of the network in the presence of locally and
  globally synchronised bursting traffic.


Installation
------------

The latest stable version of network tester may be installed from
[PyPI](https://pypi.python.org/pypi/network_tester) using:

    $ pip install network_tester

Documentation
-------------

The latest documentation can be read on [ReadTheDocs](http://network-tester.readthedocs.org/).


Development
-----------

For development information see [DEVELOP.md](./DEVELOP.md).
