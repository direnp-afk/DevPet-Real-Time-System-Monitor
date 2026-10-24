import argparse
import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from monitor import Monitor

STATIC = Path(__file__).resolve().parent / "static"
DEMOS = {
    "CPU_HIGH": "Demo: CPU reached 96%",
    "APP_STOPPED": "Demo: notepad.exe stopped",
    "TEST_FAILED": "Demo: 3 tests failed",
    "TEST_PASSED": "Demo: all tests passed",
}


class Handler(BaseHTTPRequestHandler):
    monitor = None

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/state":
            return self.reply(200, self.monitor.snapshot())
        file = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/main.js": "main.js"}.get(path)
        if not file:
            return self.send_error(404)
        content = (STATIC / file).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if urlsplit(self.path).path not in ("/api/watch", "/api/demo", "/api/ack"):
            return self.reply(404, {"error": "Not found"})
        origin = self.headers.get("Origin", "")
        allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed:
            return self.reply(403, {"error": "Local requests only"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size < 2048:
                raise ValueError("Invalid request")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Invalid request")
            if self.path == "/api/ack":
                alert_id = body.get("id")
                if not isinstance(alert_id, str) or len(alert_id) > 40:
                    raise ValueError("Invalid alert")
                self.monitor.acknowledge(alert_id)
            elif self.path == "/api/demo":
                kind = body.get("type")
                if kind not in DEMOS:
                    raise ValueError("Unknown demo event")
                self.monitor.emit(kind, DEMOS[kind], demo=True)
            else:
                action = body.get("action")
                kind = body.get("kind")
                target = body.get("target")
                if not isinstance(target, str) or not isinstance(kind, str):
                    raise ValueError("Invalid watch")
                if action == "add":
                    self.monitor.add_watch(kind, target)
                elif action == "remove":
                    self.monitor.remove_watch(kind, target)
                else:
                    raise ValueError("Unknown action")
            self.reply(200, {"ok": True})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.reply(400, {"error": str(exc)})

    def reply(self, status, result):
        data = json.dumps(result).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        if not self.path.startswith("/api/state"):
            super().log_message(fmt, *args)


def create_server(monitor, host="127.0.0.1", port=8765):
    class DevPetHandler(Handler):
        pass
    DevPetHandler.monitor = monitor
    return ThreadingHTTPServer((host, port), DevPetHandler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    monitor = Monitor()
    server = create_server(monitor, port=args.port)
    try:
        monitor.start()
        print(f"DevPet running at http://127.0.0.1:{args.port}")
        print(f"Following logs with: {monitor.follower_name}")
        print("Press Ctrl+C to stop")
        if args.open:
            webbrowser.open(f"http://127.0.0.1:{args.port}")
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        monitor.stop()


if __name__ == "__main__":
    main()
