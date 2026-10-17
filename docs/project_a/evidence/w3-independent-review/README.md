# Initial independent W3 evidence package

`initial-independent.tar.gz` contains stable original independent-review evidence from artifact, publication, queries-export, filesystem, hygiene, installed and benchmarks. It contains MANIFEST.json followed by regular files only. Every payload member has an exact size and SHA256 in the manifest; receipt.json binds the manifest itself and the full archive. selection.json gives explicit included files and excluded directory prefixes.

The archive preserves original red runs, environment/setup failures, timeout output, numerical reports, hosted products and trust catalogs. All 21 benchmark worker result files are retained: 19 completed reports, the separate direct-red result and the zero-length disk-partial result. Active installed-final and release-handoff trees are excluded.

Archive construction fixes gzip mtime, member order, uid/gid, names, file mode and member timestamps. Every member was read back in full and checked for exact size/hash, regular-file type, safe path, uniqueness and complete coverage. Selected source files were rehashed after readback. No extraction is required for validation.

`main-copy-candidate-summary.md` is a compact candidate for the implementation-branch report. Exact committed-SHA clean fresh verification and exact delivered-head CI remain pending; completed receipts belong on the durable companion evidence branch. Existing checkpoint CI cannot validate a later committed delivery.
