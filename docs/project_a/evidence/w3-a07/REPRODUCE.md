# A07 checkpoint evidence

The full W0–W2 baseline is in ../w3-baseline. New 156 tests ran together in a read-only selected-package snapshot in the pinned Humble image with generated installed interfaces. Command: python -m pytest -q -p no:cacheprovider test_route_artifact.py test_route_compile.py test_route_legacy_export.py. The command paths and strict lint output are retained in a07.log.gz.

The installed snapshot builds the selected3 packages without symlinks, then executes existing ROS/W1/W2 and new W3 tests, followed by the two explicit actualROS export tests. Raw build/test output is installed.log.gz. installed-product.zip retains the exact artifact, compile receipt, separate-process commands, query/export and mutation evidence. summary.json distinguishes duplicate test executions.

internal-challenge.zip retains independent high-precision portal/query probes and their actual input references; optional oracle environment mpmath 1.3.0 at 70/90 digits. This internal challenge is not final external acceptance.
