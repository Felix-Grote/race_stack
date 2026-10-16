# W2 independent adversarial findings — original observations

Reviewed source: `e852641849b2497efea51dfca5ead38ad4476235`, PR #2,
`project-a/w2-optimization`, corrected W1 base
`9440c2ce68e3dee549de7efacff1cf723fe830df`. Recorded on 16 October 2026.
This document preserves Phase I observations before implementation changes.
The final remediation report supersedes its acceptance state, not its evidence.

## F1 — P1: final coefficient/q authority is not independently bound at handoff

`route_validate.py:554–635` reconstructs coefficients, route and q, checking
monotonicity, exact occurrence anchors and owners. The original geometry API
has a separately approved route but no separately approved final q authority.
`route_validate_dynamics.py:586–591` compares a profile digest against a digest
computed from the candidate's own coefficients/q. That establishes consistency
with the supplied q map; it cannot establish that this is the map approved at
the optimizer handoff.

The preserved reproducer adds a 0.1 m/s cap on original seed q [3,3.01] m to
the original S0 route. It leaves all coefficients unchanged and replaces q by
`q + 1.5*sin(pi*(q-1)/7)**2` only for `1 < q < 8`. The result remains monotone
and retains occurrence, initialization and portal anchors. Regenerating the
profile and candidate hashes yields **geometry PASS / dynamics PASS**.
Checking that same speed profile with the original q map instead gives
**FAIL**, original static/model speed violation at edge 14.

This is a demonstrated handoff trust gap under this review's explicit
intermediate-tampering requirement. The inequalities are correctly evaluated
under the altered supplied q map; this is not a false enclosure of curvature,
body clearance or acceleration, nor evidence that A04 actually computes bad q.
W1's internal/factory record trust boundary explains why consistent arbitrary
q was previously accepted, but does not satisfy the newly required independent
binding against post-A04 corruption. Hashing untrusted data again cannot fix it.

The bounded correction is to require a separately captured full curve-authority
digest for any validator PASS, recompute it independently in each checker, and
pass the same frozen value through actual source and installed pipelines.
It covers coefficients, q, owners, approved-route identity and numerical policy.
It is captured at the trusted, audited A04 handoff before downstream operations;
neither a profile's self-digest nor a digest recomputed after corruption is an
independent approval. Missing authority must be INCONCLUSIVE, malformed or
mismatched authority FAIL. This is a trust input, not a cryptographic proof of
optimization history. A04 inheritance must still be audited from its traces.

## Original reproducer and failing-first evidence

[Preserved archive](evidence/w2-adversarial/phase-i/original-handoff-reproducer.zip)
contains the original probes, complete failing-first log/JUnit and identities,
plus the observed q arrays and statuses. Extract it into an initial-SHA checkout
and run, after safe setup:

```bash
scripts/project_a/unit.sh work/adversarial/replay-red \
  work/adversarial/integration/test_handoff_binding_regression.py
```

At the reviewed SHA both tests fail: absent external approval still receives
two PASS results; the API has no independent expected-authority argument.
The separate original probe records the coordinated q alteration's dual PASS.
All exploratory failures remain evidence and are not acceptance results.

## Other Phase I observations

The per-cubic displacement bound `(1+R*K)*V*dt/2`, exact Bernstein curvature/rate
bounds, full polygon/body predicates and squared-speed corner inequalities
survived the independent mathematical and numerical probes so far. Their
shared numerical kernels remain correlated dependencies, not separate proofs.
The S0 curvature-energy degradation is inherent in the retained frozen-derivative
TUM surrogate; its objective is not true integrated squared curvature. Remeshing
changes cyclic-origin results and may change retiming conservatism. These
limitations must be measured and carried into the final report, without
inventing improvement or invariance thresholds.
