# Independent W3 original failing-first evidence

Original reviewed implementation: `17e4ec4e8fedfa736467d02f6204b04e8552decb`.
The finding is described in `../../W3_INDEPENDENT_FINDINGS.md`.

`phase-i/query_zero_repro.py` retains the independently written original
reproducer. Run it with the pinned environment produced by the repository's safe
setup, with explicit paths:

```bash
python query_zero_repro.py --repo /explicit/exact-17e4ec4-checkout \
  --output /explicit/new-scratch/positive-profile --publish
```

The original expected exit is nonzero at the final positive-speed assertion,
after actual geometry/dynamics PASS and public publication/load PASS. The log
records Python 3.10.12 and unchanged original q, H, exact query station and observed
zero speed. It is not an unsupported-host or wrong-filename negative control.

`phase-i/original-source-identity.json` records the original source identities;
`SHA256SUMS` records these retained files relative to the repository root.
The corrected implementation must pass the new permanent regression and complete
final verification with its own literal-head push CI. This evidence alone is not
a final acceptance verdict or a physical vehicle claim.

`phase-ii` retains strict lint and the 141-PASS regression result, independent
65-digit/public numerical reports, and the initial harness PATH failure (exit127,
not a product result). The expanded permanent test covers both coefficient and
interior profile knots. All 4,442 independent queries and 496 strict endpoint
checks pass for production SHA256
`076a5283865ec02fa720692bcf9dfd4fcf82e891035ff70111b86733da6339bc`.
Fresh literal-commit verification and matching hosted replay remain release gates.
