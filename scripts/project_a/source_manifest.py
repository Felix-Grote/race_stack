"""Print deterministic source/fixture/harness hashes from the repository root."""
import hashlib
import json
from pathlib import Path


paths = set(Path('planner/global_planner').rglob('*.py'))
paths.update(Path('scripts/project_a').rglob('*.py'))
paths.update(p for p in Path('planner/global_planner/test/fixtures/project_a').rglob('*')
             if p.is_file())
paths.update(Path('scripts/project_a').glob('*.sh'))
paths.update((Path('docker-compose.test.yaml'), Path('.github/workflows/project-a.yml')))
print(json.dumps({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
                 indent=2, sort_keys=True))
