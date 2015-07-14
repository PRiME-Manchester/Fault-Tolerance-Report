"""In this example we attempt to discover the behaviour of the
network when the burstiness of the traffic is varied."""

import sys
import random

from network_tester import Experiment, NetworkTesterError, to_csv

e = Experiment(sys.argv[1])

#################################################################
# Network description
#################################################################

# We'll create a random network of a certain number of nodes
num_vertices = 64
fan_out = 8
vertices = [e.new_vertex() for _ in range(num_vertices)]
nets = [e.new_net(v, random.sample(vertices, fan_out))
        for v in vertices]

# Uncomment to place the network using the (dumb) Hilbert placer.
#from rig.place_and_route.place.hilbert import place as 
#hilbert_place
#e.place_and_route(place=hilbert_place)


#################################################################
# Traffic description
#################################################################

# We'll generate bursts of traffic every millisecond
e.burst_period = 1e-3

# We'll choose a particular number (and type) of packet to be 
#sent each period
packets_per_period = 32
e.use_payload = True

# We'll run the experiment for a reasonable number of periods, 
#allowing some warmup time for the network behaviour to 
#stabilise and also adding some cooldown time to ensure all 
#vertices have finished recording before stopping traffic 
#generation.
e.duration = e.burst_period * 100
e.warmup = e.burst_period * 10
e.cooldown = e.burst_period * 10

# In the experiment we'll generate bursts of traffic with the 
#packets being sent in different sized bursts. We'll also repeat 
#experiment with and without packet reinjection.
num_steps = 30
for reinject_packets in [False, True]:
    for step in range(num_steps):
        # Work out the proportion of the burst period over which 
        #we'll send the packets.
        burst_duty = step / float(num_steps - 1)

        # Work out the time between each packet being sent, 
        #we'll use this as the timestep for the traffic 
        #generator (which will generate one packet per timestep 
        #during the burst).
        timestep = (e.burst_period * burst_duty) /
                    packets_per_period

        # Don't bother trying things with too-tight a timestep 
        #since the traffic generator cannot generate packets 
        #that fast.
        if timestep < 2e-6:
            continue

        with e.new_group() as g:
            e.reinject_packets = reinject_packets
            e.burst_duty = burst_duty
            e.timestep = timestep

            # We'll add the duty and reinjection option to the 
            #results tables
            g.add_label("duty", e.burst_duty)
            g.add_label("reinject_packets", e.reinject_packets)

#################################################################
# Running the experiment
#################################################################

# Record various counter values
e.record_sent = True
e.record_blocked = True
e.record_received = True
e.record_local_multicast = True
e.record_external_multicast = True
e.record_dropped_multicast = True

# Run the experiment
results = e.run(ignore_deadline_errors=True)


#################################################################
# Result plotting
#################################################################

totals = results.totals()

# Scale from 0.0 (nothing received) to 1.0 (every packet which 
#was actually sent was received).
totals["received"] /= totals["sent"] * fan_out

# Scale from 0.0 (no packets were sent) to 1.0 (every packet we 
#tried to send was sent without being blocked by backpressure).
totals["sent"] /= totals["sent"] + totals["blocked"]

# Scale from 0.0 (no packets dropped) to 1.0 (every MC packet 
#routed was dropped).
totals["dropped_multicast"] /= (totals["local_multicast"] +
  totals["external_multicast"])

# Plot with matplotlib
import matplotlib.pyplot as plt

tr = totals[totals["reinject_packets"] == True]
tn = totals[totals["reinject_packets"] == False]

# Plot results with reinjection enabled with solid lines
plt.plot(tr["duty"], tr["sent"], label="sent", color="b")
plt.plot(tr["duty"], tr["received"], label="received", color="g")
plt.plot(tr["duty"], tr["dropped_multicast"],
  label="dropped", color="r")

# Plot results with reinjection disabled with dashed lines
plt.plot(tn["duty"], tn["sent"], linestyle="dashed", color="b")
plt.plot(tn["duty"], tn["received"], linestyle="dashed",
  color="g")
plt.plot(tn["duty"], tn["dropped_multicast"], linestyle="dashed",
  color="r")

plt.legend()
plt.xlabel("Network duty")
plt.show()
