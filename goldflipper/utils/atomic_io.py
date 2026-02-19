import json
import os
import tempfile
from typing import Any


def atomic_write_text(target_path: str, data: str, encoding: str = "utf-8") -> None:
    """Atomically write text to target_path.

    Writes to a temporary file in the same directory and replaces the target
    using os.replace (atomic on same filesystem).
    """
    directory = os.path.dirname(target_path) or "."
    os.makedirs(directory, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", encoding=encoding, delete=False, dir=directory, prefix=".tmp_", suffix=".txt") as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_path = tmp.name

    os.replace(temp_path, target_path)


def atomic_write_json(target_path: str, obj: Any, indent: int = 4, encoder: type[json.JSONEncoder] | None = None) -> None:
    """Atomically write a JSON object to target_path."""
    if encoder is not None:
        data = json.dumps(obj, indent=indent, cls=encoder)
    else:
        data = json.dumps(obj, indent=indent)
    atomic_write_text(target_path, data, encoding="utf-8")
