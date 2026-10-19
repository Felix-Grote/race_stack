# Proposed root-owned final archive updates

Apply only after actual completed merge CI audit PASS; this file is a proposal, not evidence of completion.

Replace the existing README PR3 pending paragraph with:

> [Research PR3](https://github.com/Felix-Grote/race_stack/pull/3) merged as `4bfcf35fcc08a80abbe72bdbc294cf3400e99df2`, whose tree is identical to accepted source `b961d20ce4a803e55336fb5590c30574e23b2fad`. [Exact merge push CI39302290392](https://github.com/Felix-Grote/race_stack/actions/runs/39302290392) and its authenticated original artifact passed the [merge closure audit](research-merge-closure/completed/REPORT.md): 612 tests/27 groups, five source-free tests, nine scenarios, 1,488 queries and 36 scenario CLI calls. Ten inherited legacy failures and two copyright skips remain identified. Actual build provenance binds the merge SHA; H equality across builds is not claimed.

After archive append remote readback PASS, add:

> The immutable final archive tag `project-a/w3-research-archive-final-b961d20` identifies this evidence-only archive commit. The accepted implementation tag `project-a/w3-accepted-b961d20` remains unchanged. Archive commits are evidence publication identities, not build source identities. [Publication readback](research-merge-closure/remote-readback.json) verifies the final remote bytes.

Use a new annotated `project-a/w3-research-archive-final-b961d20` tag targeting the final archive append commit, after checking that tag is absent and after verifying its remote archive bytes. Never move the accepted-source tag or overwrite any existing tag. The proposed final tag was absent from the local archive clone when this preparation was written; root must check remote absence immediately before creation.

Preserve all eight existing bundles and their sidecars byte-for-byte. Append the original merge CI ZIP, API snapshots, the frozen auditor and completed closure outputs under `research-merge-closure/`. Directly retain the native ZIP (<90MB expected, assert actual); no recompression is necessary. If a file unexpectedly exceeds the archive limit, stop and prepare deterministic logical splits rather than overwrite old bundles. Refresh root PUBLICATION_SHA256SUMS to cover new files and updated README; retain the original manifest as research-merge-closure/initial-PUBLICATION_SHA256SUMS. Do not include final readback's own hash in the commit it verifies: write and retain the final readback externally or in a later receipts-only append with an explicitly separate identity. Ensure the README's readback link names a genuinely published receipt; otherwise link to the parent-supplied external receipt location.

The archive append is complete only after remote byte readback, final tag target verification and root's final closure receipt. Production extraction and validation remain separate later gates.
