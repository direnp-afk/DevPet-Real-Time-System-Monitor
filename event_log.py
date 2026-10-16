"""Append-only structured logging that can be followed by the real `tail` CLI."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_LOG = ROOT / "logs" / "events.log"


def write_event(kind, message, log_path=DEFAULT_LOG, **details):
    if not isinstance(kind, str) or not kind.isupper() or not all(c.isalnum() or c == "_" for c in kind):
        raise ValueError("Event type must be uppercase letters, digits, or underscores")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("An event message is required")
    record = {
        "id": uuid.uuid4().hex,
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "type": kind,
        "message": message.strip()[:240],
    }
    for key, val in details.items():
        if key not in record:
            record[key] = val
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # One short O_APPEND write prevents separate writers from interleaving lines.
    line = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        n = os.write(fd, line)
        if n != len(line):
            raise OSError("Incomplete log write")
    finally:
        os.close(fd)
    return record
