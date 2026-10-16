"""DevPet dashboard server (Python stdlib, no web framework necessary)."""
import argparse
import json
import mimetypes
import signal
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pet_engine import SUPPORTED_DEMO_EVENTS
from runtime import DevPetRuntime

ASSET_ROOT = Path(__file__).resolve().parent / "static"


class Handler(BaseHTTPRequestHandler):
    runtime = None

    def do_GET(self):
        url = urlsplit(self.path).path
        if url == "/api/state":
            self.json_response(200, self.runtime.snapshot())
            return
        paths = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/main.js": "main.js"}
        if url not in paths:
            self.send_error(404, "Not Found")
            return
        path = ASSET_ROOT / paths[url]
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/demo":
            self.json_response(404, {"error": "Unknown endpoint"})
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > 2048:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(n))
            if not isinstance(body, dict) or not isinstance(body.get("type"), str):
                raise ValueError("Expected an event type")
            event_type = body["type"]
            if event_type not in SUPPORTED_DEMO_EVENTS:
                raise ValueError("Unsupported demo event")
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            self.json_response(400, {"error": str(exc)})
            return
        self.runtime.emit(event_type, SUPPORTED_DEMO_EVENTS[event_type])
        self.json_response(200, {"ok": True, "type": event_type})

    def json_response(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        # Keep terminal output quiet (the live feed is in the browser).
        if not self.path.startswith("/api/state"):
            super().log_message(fmt, *args)


def make_server(runtime, host, port):
    class AppHandler(Handler):
        pass
    AppHandler.runtime = runtime
    return ThreadingHTTPServer((host, port), AppHandler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Launch the DevPet dashboard.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: localhost)")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")
    parser.add_argument("--watch-pid", type=int, default=None, help="Optionally monitor whether a process exits")
    parser.add_argument("--log", type=Path, default=None, help="Use a different log file")
    parser.add_argument("--open-browser", action="store_true", help="Open the dashboard in your default web browser")
    args = parser.parse_args(argv)

    from event_log import DEFAULT_LOG
    runtime = DevPetRuntime(log_path=args.log or DEFAULT_LOG, watch_pid=args.watch_pid)
    runtime.start()
    try:
        server = make_server(runtime, args.host, args.port)
    except OSError:
        runtime.stop()
        raise
    print(f"\nDevPet is live at http://{args.host}:{server.server_port}")
    print(f"Watching log: {runtime.log_path}")
    print(f"Log follower: {runtime.tail_label}")
    print("Press Ctrl+C to quit.\n")
    if args.open_browser:
        webbrowser.open(f"http://{args.host}:{server.server_port}")
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
