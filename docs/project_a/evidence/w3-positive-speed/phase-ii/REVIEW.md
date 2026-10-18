# Independent resumed query numerical review

Scope: reviewed uncommitted repair based on `67fbcc8283e59649d38dc9318291634089df3741`; `route_artifact.py` SHA-256 `076a5283865ec02fa720692bcf9dfd4fcf82e891035ff70111b86733da6339bc`. No final-source acceptance is implied until the final SHA is identified and tests complete. Original red numerical evidence remains unchanged in `../numerical/`.

## Source review

Read scoped AGENTS, current execution/architecture/roadmap specifications, W3 artifact/runtime and W2/W1 numeric contracts. The profile's mathematical authority remains squared speed affine in true metric arc. W1 permits its existing bounded inversion residual and can return t=1 for a station strictly preceding a coefficient boundary without changing that station's half-open owner.

The correction computes the same affine function from its nearer endpoint. For first-half local fraction r, `u_i+(u_j-u_i)*r` cannot lose the positive endpoint floor through near-total cancellation, since r<=1/2. In the second half it uses `u_j+(u_i-u_j)*remaining/distance`; the short remaining coordinate is computed directly as `end_arc-current_arc`, rather than by subtracting local from total. This prevents the original subtraction from erasing u_j. The upper endpoint is the next knot's saved start arc for a same-coefficient edge, otherwise the segment length; the closing edge therefore retains correct arithmetic. The exact start-station branch still yields u_i. Both local and remaining coordinates retain the original station_abs gate and clamp; no ownership rule, coefficients, profile, model, validator, proof policy or tolerance changes are present.

Prefix-arc subtraction still inherits W1's existing bounded numerical accuracy. The correction is not a new exact interval integrator and does not claim to remove the pre-existing station/inversion allowance.

## Independent controls prepared

Copies of original 65-digit mpmath ordinary/interior coefficient-authority oracles now target the pinned Python 3.10.12 runtime, preserve original archived q exactly, and make explicit assertions on ownership, metric station residual, speed, acceleration, time, curvature, tangent and actual independent lap time enclosure. Test-only pure mpmath was copied into `vendor/`; it is not a production dependency. Original unsupported Python3.12 host results remain separate.

Two public high-dynamic-range probes exercise geometry and dynamics validators followed by public publish/load, then exact/neighbor coefficient/profile boundaries, both acceleration signs, ordinary interiors, seams, negative and multiple-lap progress. One profile has knots at coefficient starts; the other adds an interior t=.37 knot to every coefficient. Both require positive endpoint speed range, exact endpoint values, right-hand segment/owner agreement, and finite acceleration/time. They use separately retained H; no q rebasing or internal publication/loading bypass is used.

## Executed pinned results

All four commands completed with exit 0 against the reviewed source hash. Runtime is Python 3.10.12, NumPy 1.26.4, SciPy 1.11.4; test-only mpmath 1.3.0 at 65 decimal digits. No solver children, new Docker containers or production edits were performed by this reviewer.

| Independent control | Queries | Result |
|---|---:|---|
| S0 / reversed / rotated / S3 coefficient-authority ordinary oracle | 1452 | Both validators PASS in all four cases; no owner failures; every independently integrated true lap time enclosed |
| S0 t=.37 interior-profile/cap/portal oracle | 630 | Both validators PASS; no owner failures; true lap time enclosed |
| Actual public coefficient-knot high-dynamic profile | 788 | Publish/load PASS, exact archive q, positive range/owner checks PASS, 199 strict endpoint checks |
| Actual public t=.37 interior-knot high-dynamic profile | 1572 | Publish/load PASS, exact archive q, positive range/owner checks PASS, 297 strict endpoint checks |

Ordinary maximum errors: station 1.50145e-10 m, speed 1.47042e-16 m/s, acceleration 3.36157e-18 m/s^2, elapsed 6.51002e-15 s, signed curvature 1.57218e-16 /m, tangent 1.45581e-16. Interior maximum errors: station 1.52626e-10 m, speed 2.24209e-12 m/s, acceleration 3.57354e-18 m/s^2, elapsed 1.52502e-10 s, signed curvature 9.61237e-17 /m, tangent 1.33866e-16. Maximum true whole-lap length discrepancy is 3.01433e-15 m.

The original failing public coefficient query now returns exactly 1e-6 m/s at segment 0/t=1, under H `37ec8e558b11d22ad008ec3911c9a62bd11e29efa654db29fa715b2ee84841f4`. The separately retained interior public H is `1d0bcd9d51a8ea445bc211876305cdb0d15326a14bbcde5af0765fee4752e5c9`.

The high-gradient interior nextafter query can return t=.3699999999997062 preceding the t=.37 speed knot and speed .89145 m/s; exact station queries return the correct 1e-6 m/s endpoint. This reflects the pre-existing W1 inverse-position allowance under an extremely large synthetic profile gradient, not a guarantee of endpoint snapping or improved inverse precision. All values remain within positive endpoint ranges. These tests do not enlarge station accuracy claims.

Reproduction (existing shared container, from host; redirect stdout/stderr to the corresponding `*.pinned.log`):

```bash
docker --host=unix:///var/run/docker.sock exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 -e PYTHONDONTWRITEBYTECODE=1 forza-independent-probes /opt/project-a/bin/python3 /records/resume-numerical/ordinary_oracle.py
docker --host=unix:///var/run/docker.sock exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 -e PYTHONDONTWRITEBYTECODE=1 forza-independent-probes /opt/project-a/bin/python3 /records/resume-numerical/interior_profile_oracle.py
docker --host=unix:///var/run/docker.sock exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 -e PYTHONDONTWRITEBYTECODE=1 forza-independent-probes /opt/project-a/bin/python3 /records/resume-numerical/public_query_boundaries.py --repo /records/final-checkout --output /records/resume-numerical/coefficient-publication --publish
docker --host=unix:///var/run/docker.sock exec -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 -e PYTHONDONTWRITEBYTECODE=1 forza-independent-probes /opt/project-a/bin/python3 /records/resume-numerical/public_interior_boundaries.py --repo /records/final-checkout --output /records/resume-numerical/interior-publication --publish
```

The last two commands require absent output products; use fresh output directories for a rerun. Public H hashes include implementation content, so the original old-code red H is expected to differ from the corrected-code H.

**Numerical review verdict: PASS for the reviewed correction hash.** This is a scoped independent query/numerics verdict, not a full W3 release decision. The final committed source identity must be mapped to this unchanged implementation hash by root, alongside full fresh/hosted/install gates.

