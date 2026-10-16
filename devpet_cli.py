"""CLI integrations for real builds, test runs, and custom developer events."""
import argparse
import subprocess
import sys

from event_log import write_event


def execute(kind, argv, log_path):
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("Missing command after --", file=sys.stderr)
        return 2
    try:
        result = subprocess.run(argv, check=False)
        code = result.returncode
    except OSError as exc:
        code = 127
        print(f"Could not run command: {exc}", file=sys.stderr)
    if kind == "tests":
        event_type = "TEST_PASSED" if code == 0 else "TEST_FAILED"
        message = f"Tests {'passed' if code == 0 else 'failed'} (exit code {code}): {' '.join(argv)}"
    else:
        event_type = "BUILD_SUCCESS" if code == 0 else "APP_CRASH"
        message = f"Command {'succeeded' if code == 0 else 'failed'} (exit code {code}): {' '.join(argv)}"
    write_event(event_type, message, log_path)
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(description="Send real development events to DevPet.")
    parser.add_argument("--log", default=None, help="Optional alternate events.log path")
    commands = parser.add_subparsers(dest="command", required=True)
    emit = commands.add_parser("emit", help="Append a custom event")
    emit.add_argument("type", help="e.g. GIT_COMMIT or BUILD_SUCCESS")
    emit.add_argument("message", nargs="+", help="Short event description")
    for name in ("tests", "run"):
        p = commands.add_parser(name, help=f"Run a command and record its {'test' if name == 'tests' else 'exit'} status")
        p.add_argument("command_to_run", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    from event_log import DEFAULT_LOG
    log_path = args.log or DEFAULT_LOG
    if args.command == "emit":
        try:
            write_event(args.type, " ".join(args.message), log_path)
        except ValueError as exc:
            parser.error(str(exc))
        print("Event recorded.")
        return 0
    return execute(args.command, args.command_to_run, log_path)


if __name__ == "__main__":
    sys.exit(main())
