"""
The global planner's line optimizer, built on the route package.

Moves the points of a lap to the line of least curvature that keeps the car's whole body
on legal road, solved with IPOPT through CasADi; see solve.optimize.
"""
