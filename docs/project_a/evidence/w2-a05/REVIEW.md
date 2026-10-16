# A05 independent review and evidence

Verdict: ACCEPT for the stated exact-input planar software certificate.
Final frozen acceptance: 50 tests passed in 103.41 s, exit 0, source/fixture/helper/
Compose hashes equal before and after. Strict flake8 --max-line-length=99 passes.

Reviewed production SHA256
da6ddcb89fb46823575fedfdc291a23bab96508b54f3bb8a98889b1898dc47ef.
Exact independent route/curve authority, owner intervals, all applicable gate
roots, nonoverlapping portal supports, exact shared caps/simple unions, full
rectangle interiors/edges and interval sweep bounds were checked separately.
No remaining substantive false-PASS issue was found.

Review found squared-rational underflow/subnormal conversion could understate
curvature; scaled sqrt and explicit overflow uncertainty repair it. Thirteen
independent Decimal oracle cases cover derivatives/K/dKds, cancellation, transforms,
scaling, hidden peaks, subnormal bounds and overflow. A supplemental host-only
exact-rational check enclosed 1,024 scaled square-root cases. Host evidence is
labelled and is not used as pinned route/ROS acceptance.

The first frozen run had 44 passes/1 test-fixture failure: intended legal endpoints
were on strict polygon caps. Correcting the outer caps preserves the tiny notch.
The second run had 49 passes. Final adds a reject-only tensor preflight and full
body-at-node assertions. No original W0/W1 test or acceptance tolerance changed.
Full-validator cases now prove legal solver endpoints/bodies can conceal interior
reference/rectangle-edge violations, hidden curvature and wrong gate phase.

The retained independent S3 reproducer in sibling w2-a05-independent reports all
44 nodal bodies legal, yet FAIL for a genuine between-node swept footprint exit.
Its final pinned run passed in 5.07 s with stable production/fixture/harness hashes.
The script hash is 7b01eece7f5069542f6c0d16a32147b65eb094bc9bf74021fcc288e4cfbb7cae.
Reproduce from repo root:

```bash
scripts/project_a/unit.sh work/w2/review-reproduce docs/project_a/evidence/w2-a05-independent/test_hidden_notch_probe.py -x
```

In that probe, original_fixture_sha256 denotes canonical Route.digest, not raw
file bytes; raw fixture SHA256 is in source-hashes-before.json. The generated
route, complete negative coefficients/q/owners/body/policy and verdict are retained.
No physical obstacle/contact/3D/tracking or dynamic certificate is claimed here.

The initial reported lint command suppressed E501/W503/W504 and did not match the
committed strict runner. The strict run exposed 44 line-length diagnostics. Only
line wrapping changed; AST SHA256 equality is retained in strict-ast-invariance.json.
Strict 99-character lint then passed with no ignores. The final formatted 50-test
run was rerun with stable hashes; pre-format acceptance and lint evidence remain
labelled. Independent probe/review pre-format source has the identical AST.
