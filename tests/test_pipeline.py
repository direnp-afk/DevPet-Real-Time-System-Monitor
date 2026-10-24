import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from monitor import Monitor


class FullPipeline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.monitor = Monitor(root / "events.log", root / "save.json", interval=0.2)
        self.monitor.start()
        time.sleep(0.6)

    def tearDown(self):
        self.monitor.stop()
        self.temp.cleanup()

    def wait_for(self, predicate, timeout=5):
        limit = time.monotonic() + timeout
        while time.monotonic() < limit:
            result = predicate(self.monitor.snapshot())
            if result:
                return result
            time.sleep(0.12)
        self.fail("Timed out waiting for an event to reach the pet through tail")

    def test_real_error_log_drives_alert_and_pet(self):
        path = Path(self.temp.name) / "error.log"
        path.write_text("initial line\n")
        self.monitor.add_watch("log", str(path))
        with path.open("a") as stream:
            stream.write("ERROR example failure\n")
        self.wait_for(lambda s: s["pet"]["mood"] == "worried")
        state = self.monitor.snapshot()
        self.assertEqual(state["alerts"][0]["type"], "LOG_ERROR")
        self.assertEqual(state["events"][0]["type"], "LOG_ERROR")

    def test_real_file_event_grants_xp(self):
        path = Path(self.temp.name) / "folder"
        path.mkdir()
        self.monitor.add_watch("folder", str(path))
        self.wait_for(lambda s: s["watches"][0]["status"] == "watching")
        (path / "new.txt").write_text("created")
        self.wait_for(lambda s: any(x["type"] == "FILE_ADDED" for x in s["events"]))
        self.assertEqual(self.monitor.snapshot()["pet"]["xp"], 4)

    def test_process_exit_creates_stopped_event(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdout=subprocess.DEVNULL)
        try:
            self.monitor.add_watch("process", str(process.pid))
            self.wait_for(lambda s: "running" in s["watches"][0]["status"])
            process.terminate()
            process.wait(timeout=3)
            self.wait_for(lambda s: any(x["type"] == "APP_STOPPED" for x in s["events"]))
            self.assertEqual(self.monitor.snapshot()["pet"]["mood"], "worried")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
