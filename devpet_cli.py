import argparse
import subprocess
import sys

from monitor import LOG_FILE
import json
import os
import uuid
from datetime import datetime


def send_event(kind, message):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "id": uuid.uuid4().hex,
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "type": kind,
        "message": message[:180],
        "demo": False,
    }
    line = (json.dumps(event) + "\n").encode("utf-8")
    fd = os.open(LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["test", "build"])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Add a command to run")
    try:
        result = subprocess.run(command)
        code = result.returncode
    except OSError as exc:
        print(exc, file=sys.stderr)
        code = 1
    name = "TEST" if args.kind == "test" else "BUILD"
    send_event(f"{name}_{'PASSED' if code == 0 else 'FAILED'}", f"{' '.join(command)} (exit {code})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
