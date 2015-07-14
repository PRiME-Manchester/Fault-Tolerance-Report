"""This is (more-or-less) the example experiment described in the getting
started section of the manual.

In this experiment we simply measure the number of packets received as we ramp
up the amount of traffic generated.
"""

import sys
import random

from network_tester import Experiment, to_csv

# Take the SpiNNaker board IP/hostname from the command-line
e = Experiment(sys.argv[1])

# Define a random network
vertices = [e.new_vertex() for _ in range(64)]
nets = [e.new_net(vertex, random.sample(vertices, 8))
        for vertex in vertices]

e.timestep = 1e-5  # 10 us

# Sweep over a range of packet-generation probabilities
num_steps = 10
for step in range(num_steps):
    with e.new_group() as group:
        e.probability = step / float(num_steps - 1)
        group.add_label("probability", e.probability)

# Run each group for 1/10th of a second (with some time for warmup cooldown)
e.warmup = 0.05
e.duration = 0.1
e.cooldown = 0.01

e.record_received = True

# When the network saturates (for particularly high packet rates) realtime
# deadlines will be missed in the packet sinks. We'll just ignore them in this
# experiment.
results = e.run(ignore_deadline_errors=True)

totals = results.totals()

# Plot the results
import matplotlib.pyplot as plt
plt.plot(totals["probability"], totals["received"])
plt.xlabel("Packet injection probability")
plt.ylabel("Packets received at sinks")
plt.show()

# Produce an R-compatible CSV file.
print(to_csv(totals))
