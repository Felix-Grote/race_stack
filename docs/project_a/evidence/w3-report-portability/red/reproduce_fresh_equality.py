"""Preserve the failed bitwise cross-host fresh-compile expectation."""
import json
from pathlib import Path
local = json.loads(Path('work/w3/final-fresh/verification/source-free/results/w3-scenario-campaign.json').read_text())
hosted = json.loads(Path('work/w3/final-ci/source-free/results/w3-scenario-campaign.json').read_text())
for a, b in zip(local['outcomes'], hosted['outcomes']):
    assert a['case'] == b['case']
    assert a['H'] == b['H'], (a['case'], a['H'], b['H'])
    assert a['curve_digest'] == b['curve_digest'], (a['case'], a['curve_digest'], b['curve_digest'])
