import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import create_server
from monitor import Monitor


class API(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        home = Path(self.temp.name)
        self.monitor = Monitor(home / "events.log", home / "save.json")
        self.server = create_server(self.monitor, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=1)
        self.temp.cleanup()

    def request(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=2) as res:
            return res.status, res.read()

    def test_state_endpoint(self):
        status, body = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertIn("pet", json.loads(body))

    def test_dashboard_assets(self):
        for path in ("/", "/style.css", "/main.js"):
            status, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertGreater(len(body), 100)

    def test_watch_api(self):
        status, _ = self.request("POST", "/api/watch", {"action": "add", "kind": "process", "target": "notepad.exe"})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.monitor.snapshot()["watches"]), 1)
        self.request("POST", "/api/watch", {"action": "remove", "kind": "process", "target": "notepad.exe"})
        self.assertEqual(len(self.monitor.snapshot()["watches"]), 0)

    def test_demo_api(self):
        status, _ = self.request("POST", "/api/demo", {"type": "TEST_PASSED"})
        self.assertEqual(status, 200)
        line = json.loads(self.monitor.log_file.read_text().strip())
        self.assertTrue(line["demo"])

    def test_log_watch_and_ack_api(self):
        logfile = Path(self.temp.name) / "app.log"
        logfile.touch()
        self.request("POST", "/api/watch", {"action": "add", "kind": "log", "target": str(logfile)})
        self.assertEqual(self.monitor.snapshot()["watches"][0]["kind"], "log")
        self.monitor._apply({"id": "alert42", "type": "LOG_ERROR", "source": "app.log", "message": "ERROR in app"})
        self.request("POST", "/api/ack", {"id": "alert42"})
        self.assertEqual(self.monitor.snapshot()["alerts"][0]["status"], "acknowledged")

    def test_invalid_demo(self):
        with self.assertRaises(HTTPError) as error:
            self.request("POST", "/api/demo", {"type": "DO_ANYTHING"})
        self.assertEqual(error.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
