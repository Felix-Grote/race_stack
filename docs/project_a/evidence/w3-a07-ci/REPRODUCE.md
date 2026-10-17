# A07 exact-head hosted evidence

Push CI [38918290086](https://github.com/Felix-Grote/race_stack/actions/runs/38918290086)
completed successfully for literal A07 commit
`0c2d7c35fc50051a2ae96b9260de636610e280f4`. The original downloaded
artifact ZIP includes all 68 files, including full logs and JUnit.

`gh run download 38918290086` can retrieve the original artifact while retained;
the committed ZIP is the independently downloaded copy. Verify SHA256SUMS before
extracting into private scratch. The before/after source manifests are equal.

All 532 functional tests pass in 24 groups; three packages build. The separate
legacy aggregate is 528 tests, zero errors, the exact ten inherited failures
and two original skips. It is not a green legacy suite.

This is A07 evidence, not final W3 acceptance. The initial installed mutation
filenames caused path rejection; they are not credited as installed content
validation. The source artifact mutation tests used valid product paths. A09
corrects and reruns installed content mutations in source-free runtime.
