# Independent W3 findings — original observations

Reviewed source: `17e4ec4e8fedfa736467d02f6204b04e8552decb`, PR #3.
These observations were recorded before changing production code. The same interpolation expression remains present at latest head
`67fbcc8283e59649d38dc9318291634089df3741` (line 594). Its three existing
remediation commits remain preserved. Independent
acceptance of the corrected source requires complete final verification and
literal-head push CI; the original green author suites do not close this review.

## Q1 — P2: positive approved squared speed can query as zero

Location: `planner/global_planner/global_planner/route_artifact.py:568`,
`Reference.sample`.

Contract: squared speed is affine in actual local metric arc, and a certified
positive moving profile must remain positive throughout its edge. Queries must
use the same saved coefficient/profile authority that passed both validators.

The independent reproducer retains the original approved W2 S0 coefficients,
owners and q verbatim, explicitly approves a synthetic high-dynamic-range model
and positive squared-speed endpoints `1e12` and `1e-12`, and executes both real
validators, public publication and public reload under a separately retained H.
Python 3.10.12, the supported numerical versions and unmodified q are asserted.
This is a numerical test model, not a vehicle calibration claim.

Original result: geometry PASS, dynamics PASS, public publication PASS and public
load PASS. At `s=0.2760027237149405`, immediately before the next coefficient
boundary `0.27600272371494056`, the preceding segment correctly remains selected
and the bounded metric inverse returns `t=1`. The query returns speed `0.0`.
The exact binary64 positive terminal squared speed has square root approximately
`9.9999999999999998994332381463e-7` m/s. The retained original artifact H is
`66ab322e8626ba1baed81a6074dc4351f4a5af4ed2c41d32a53ba1676c901597`.

Expected result: positive speed within the endpoint range, including the exact
terminal speed when the recovered local arc reaches the endpoint. Preceding
half-open occurrence ownership and the existing inverse accuracy allowance must
remain unchanged.

Root cause: evaluating `u0 + (u1-u0)*(local/distance)` loses the small positive
`u1` in the subtraction. At an endpoint the subtraction and addition cancel to
zero. This is query arithmetic, not a false geometry/dynamics certificate or a
reason to change the approved profile, model, coefficient or numerical policy.

Proposed correction: evaluate the same affine function from its nearer endpoint,
using the remaining arc directly near the upper endpoint. This avoids destructive
cancellation while preserving exact endpoints. Add a public publish/load query
regression and retain the failing-first script/output in the independent evidence
archive. No geometry bound, constraint or tolerance is relaxed.
