# Research merge closure preparation

Status: **PENDING actual completed merge CI evidence**. No merge CI success or final R3 closure is claimed by these preparation files.

Research PR3 merged at `4bfcf35fcc08a80abbe72bdbc294cf3400e99df2`. The preserved merge-verification receipt records its tree `c15b269c58ff82a12f6fae6c2481a56ce317f9fb` identical to accepted research source `b961d20ce4a803e55336fb5590c30574e23b2fad`; the auditor repeats the literal Git object checks. Initial archive commit `4b222ff37101c72d79cd6da0467a562214817d79` has preserved remote readback PASS. Exact merge push run `39302290392` still requires completed authenticated snapshots and its native original artifact ZIP.

The root agent owns all network calls, artifact downloads, archive copying, Git mutations, pushes and tags. This directory contains only preparatory scripts, preserved receipts and a publication plan. No product imports or numerical workloads are required.

After downloading the original native ZIP, save completed GitHub run and artifact-list API JSON snapshots and invoke:

```bash
python /workspace/forza-audit-records/research-merge-closure/audit_merge.py \
  --run-json /path/to/completed-run.json \
  --artifacts-json /path/to/completed-artifacts.json \
  --zip /path/to/original-native-artifact.zip \
  --git-repository /workspace/forza-w3-audit \
  --output /workspace/forza-audit-records/research-merge-closure/completed
```

Use an absent output directory; a failed audit is preserved and must not be overwritten. Choose another absent closure subdirectory after diagnosing any actual failure. Run with ordinary Python and assertions enabled. Read-only Git object access requires the literal merge and accepted commits in the local repository, plus the preserved recursive gitlink objects under the initial fresh checkout, as documented by `audit_hosted_inherited.py`. No fetch or checkout occurs.

The helper authenticates exact successful push run/head/attempt/repository and artifact run/digest/size, then invokes the frozen accepted-source provenance auditor for the actual merge SHA. It supplements that audit with exact group/XML coverage (612 tests, 27 groups), inherited raw legacy failure identities/597-test summary/10 failures/2 copyright skips and original exit codes, all five source-free tests, nine distinct scenario identities, 1,488 queries and 36 compile/validate/query/export CLI calls. It checks 138 source hashes, 21 installed resources, two locks, seven recursive gitlinks, ten installed module origins and all eleven implementation hashes within each of nine authenticated producer/validator H/C envelopes. Every envelope must bind the actual merge SHA and canonical actual build manifest. The original ZIP, API snapshots, full hosted audit, raw approved artifact catalog and nine reference artifacts are preserved under the output directory.

Merge build H may differ from accepted-source build H because source commit provenance changes. No cross-build H equality or fresh numerical replay is asserted. Existing research scope limitations and all inherited failures remain unchanged.

On successful actual audit, `completed/closure.json` and `completed/REPORT.md` report CI audit PASS while explicitly leaving archive append publication/remote readback pending. `completed/append-inventory.json` lists every output path, size and SHA. The parent must complete publication/readback and record that separate result before declaring final R3 closure. Preparatory pending snapshots remain historical records.
