# W2 independent finding F2 — P2 exact shared-cap roundoff

Observed against correction checkpoint
`6b778519de74b09a7b66be2ac89e12d687226c9d`, before F2 implementation changes.

An independently generated asymmetric ellipse (semiaxes 9.7/4.6 m, rotated
0.37 rad and translated by (19.25,-7.5) m) has four explicitly approved owned
ribbons, exact reused cap endpoints, varying signed widths and an interior speed
restriction. Its unchanged seed receives independent A05 **PASS**, 137 proof
leaves. Default A04 nevertheless returns **GEOMETRY_FAILURE** during first-iteration
corridor checking: `reference outside/ambiguous connected legal interval`.
An independent process replay confirms one QP and the second geometry call
(the first damped shifted fit), before any completed iteration trace. The initial
interpretation as the first reference preparation was incorrect; traces are
appended only after shifted geometry succeeds. The geometric counterexample and
all recorded normal coordinates are unchanged.

At q=23.180201347200946, p=(10.346273849151595,-10.953427375385925) and left
normal n=(0.9350684075601509,0.3544673090468617), the very same undirected cap
is traversed oppositely by its two adjacent polygons. `_route_geometry.py:107`
computes its line intersection separately with floating-point subtraction,
cross products and division. One polygon ends at -7.56631403522638e-14; the
next starts at -7.25105095042528e-14. Their artificial gap is
3.1526308480109937e-15 m. Exact rational evaluation of the binary64 inputs gives
the same root in both orientations:

```
-6493513456432416 / 89282567569951896214720469081
```

The true explicitly approved union is connected. The W1 F1 repair correctly
does not merge positive gaps, so this unequal evaluation rejects a valid portal.
This is a numerical false negative, not permission to loosen `_merge`, add an
epsilon join or enlarge legal geometry.

The bounded remedy is to canonicalize each undirected edge's endpoint order
before line-intersection arithmetic. Reversed identical binary64 edges then
execute identical operations; z is mathematically orientation-independent and
the finite edge parameter merely changes from t to 1-t. Preserve all existing
EPS values, component tests, allowed-cap checks and open-interior contact cuts.

The original full route, failed optimizer run, independently legal seed,
minimal four-vertex reproducer, exact oracle and failing-first log are preserved
in [the red archive](evidence/w2-adversarial/f2-red/original-shared-cap-reproducer.zip).
The minimal original-source test fails in 0.05 s. A scratch-only canonicalization
passes 49 independent controls: the minimal case, 12 transformed/winding cases,
24 genuine positive gaps from 1e-10 to 1e-6 m, and 12 ordinary tangent contacts.
These proposed tests do not yet establish final-source acceptance.

The real production correction, original W0–W2 suites, unchanged new-ellipse
complete pipeline and exact final-head CI must pass before release. Do not
reinterpret this demonstrated supported portal as unsupported geometry.
