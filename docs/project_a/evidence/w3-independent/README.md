# Independent W3 evidence

Reviewed initial source: `17e4ec4e8fedfa736467d02f6204b04e8552decb`.
Original failures, red/green JUnit/logs, exact source hashes, commands, independent
oracles, controlled H/C catalogs, hosted products and every benchmark attempt
are retained in the [immutable companion archive](https://github.com/Felix-Grote/race_stack/blob/e4ae5922c0d21f3a00395cae3eedebd758b5f086/docs/project_a/evidence/w3-independent-review/initial-independent.tar.gz).
It contains 350 regular evidence files plus its manifest, 19,274,976 stored bytes,
SHA256 `05cb942671a3ffb758541e72aa92281725902b270ad60b5fa66daa0165f90ad4`.
The adjacent MANIFEST, selection, receipt and README describe all members and
explicit exclusions. Full readback and a deterministic rebuild match exactly.

Extract to scratch after checking the archive SHA256. Paths inside preserve
`publication/`, `installed/`, `benchmarks/`, `artifact/`, `queries-export/`,
`filesystem/` and `hygiene/`; their reproducers and command records are authoritative.
Check each regular member against MANIFEST.json without treating an embedded H
or stored PASS as external artifact approval. Only reproducible checkout/build/
cache and synthetic Git fixture scratch is excluded; original failed outputs remain.

The [completed publication receipt](https://github.com/Felix-Grote/race_stack/blob/w3-independent-review-20261017/docs/project_a/evidence/w3-independent-review/final-publication.json)
separately records final literal source SHA, clean recursive fresh verification,
exact-head hosted CI, downloaded source identities and final-version hosted-product
replay. Those gates cannot be inferred from this initial archive or focused tests.
Original branch `w3-evidence-17e4ec4` is unchanged. Git-retained archives, maintained
by the fork owner, preserve the evidence beyond Actions artifact expiration.
