# W0 source audit — 2026-10-16

Live upstream/fork base is `67981ed7964a6d35e1da48f0c22bbd9f6d123d5e`, not the
architecture's `00a166de...` research base. Recursive optimizer remains
`b1b38ecfefec7200d5bcb243f115af1d795b3766`; all seven gitlinks match and submodules
are clean. [Machine-readable source hashes/gitlinks](evidence/source-baseline.json).

Inspected `global_planner_node.py`, `global_planner_utils.py`,
`mapping_node.py`, `readwrite_global_waypoints.py`, package setup/manifests,
optimizer wrapper/helper imports and current changes since the research base.

- Latest commit tunes vehicle steering config; outside Project A and untouched.
- Merge #43 changes mapping pose acquisition to TF `map -> base_link`, including
  latching initial pose. Planner README now describes TF. Do not revert or assume
  the old carstate/odom integration. No mapping/node behavior is changed in W0.
- Legacy global planner remains GUI/TkAgg/map/stack_master coupled. Keep its entry
  points; W0 imports installed utilities and serializers without constructing nodes
  or a GUI. No full legacy map-planning solve or mapping launch is claimed.
- Legacy bounds use extraction and nearest-XY methods; no occurrence-owned manual
  route modules exist. The new offline compiler is not implemented in W0.
- Existing package metadata does not fully declare runtime numerical/ROS imports;
  W0 supplies exact test dependencies independently without changing runtime
  metadata. Build success alone is insufficient; installed utility imports and
  actual generated message roundtrips are checked.
- Optimizer package `__init__` imports its wrapper and minimum-time modules, which
  import CasADi/scikit-learn even for curvature use. Include those for an honest
  wheel import; no claim that that backend or IPOPT has been validated.
- No P01 `docker-compose.test.yaml` or repo-local baseline existed at base. Workspace
  onboarding scripts are external/uncommitted and use host networking. W0 creates
  a standalone isolated target without using the hardware Compose file.
- Re-executed unmodified TPH preparation still raises the SciPy 1-D shape error;
  metric interpolation still uses linear parameter fractions. The W0 probes
  characterize both defects without patching dependencies or endorsing outputs.

All new changes are docs, development guidance, test/environment scripts and CI.
Original planner source, map/config files, messages, Frenet code and every gitlink
remain byte-identical to base. This is a Cloud foundation checkpoint, not A01.
