"""Small JSON files shared by the server and the planning worker."""
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


def digest(data: bytes) -> str:
    """Return the identity of a captured input."""
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, data: object) -> None:
    """Publish a complete JSON document in one rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, allow_nan=False, separators=(',', ':'))
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
