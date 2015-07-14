SpiNNaker 'Network Tester' Documentation
========================================

'Network Tester' is a library designed to enable experimenters to quickly and
easily describe and run experiments on SpiNNaker_'s interconnection network. In
particular, network tester is designed to make recreating traffic loads similar
to typical neural software straight-forward. Such network loads feature a fixed
set of vertices (cores) which produce SpiNNaker packets which are then
multicast to a fixed set of vertices.

The following is a (non-exhaustive) list of the kinds of experiments which can
be performed with 'Network Tester':

* Determining how a network copes with different rates and patterns of packet
  generation. For example to determining the maximum speed at which a particular
  neural simulation may run on SpiNNaker without dropping packets.
* Determining the effectiveness of place and route algorithms by finding
  'hot-spots' in the network.
* Characterising the behaviour of the network in the presence of locally and
  globally synchronised bursting traffic.

.. _SpiNNaker: http://apt.cs.manchester.ac.uk/projects/SpiNNaker/

Getting started
---------------

.. toctree::
   :maxdepth: 3
   
   getting_started

API Reference
-------------

.. toctree::
   :maxdepth: 3
   
   api



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

