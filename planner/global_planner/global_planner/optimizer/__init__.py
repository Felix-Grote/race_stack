"""
The global planner's line optimizer, built on the route and speed packages.

Moves the points of a lap to the line of least curvature that keeps the car's whole body
on legal road and, given the car's speed limits, on to the fastest such line with a share
of that smoothness kept. Solved with IPOPT through CasADi; see solve.optimize.
"""
