import json
import tempfile
import unittest
from pathlib import Path

from monitor import Monitor


class Alerts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.monitor = Monitor(root / "events.log", root / "save.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_alert_acknowledgement_persists(self):
        self.monitor._apply({"id": "x", "type": "APP_STOPPED", "message": "notepad stopped", "target": "notepad.exe"})
        self.monitor.acknowledge("x")
        self.assertEqual(self.monitor.snapshot()["alerts"][0]["status"], "acknowledged")
        restored = Monitor(self.monitor.log_file, self.monitor.save_file)
        self.assertEqual(restored.snapshot()["alerts"][0]["status"], "acknowledged")

    def test_recovery_resolves_alert_for_same_process(self):
        self.monitor._apply({"id": "1", "type": "APP_STOPPED", "target": "notepad.exe", "message": "stopped"})
        self.monitor._apply({"id": "2", "type": "APP_STARTED", "target": "calc.exe", "message": "started"})
        self.assertEqual(self.monitor.snapshot()["alerts"][0]["status"], "new")
        self.monitor._apply({"id": "3", "type": "APP_STARTED", "target": "notepad.exe", "message": "started"})
        self.assertEqual(self.monitor.snapshot()["alerts"][0]["status"], "recovered")

    def test_duplicate_log_errors_do_not_farm_alerts(self):
        for i in range(5):
            self.monitor._apply({"id": str(i), "type": "LOG_ERROR", "message": "Error", "source": "app.log"})
        self.assertEqual(len(self.monitor.snapshot()["alerts"]), 1)
        self.assertEqual(self.monitor.snapshot()["pet"]["health"], 77)
        self.assertEqual(len(self.monitor.snapshot()["events"]), 5)

    def test_metrics_history_capped(self):
        for i in range(80):
            self.monitor._apply({"type": "METRIC", "time": str(i), "system": {"cpu": i, "memory": 50}})
        self.assertEqual(len(self.monitor.snapshot()["history"]), 60)
        self.assertEqual(self.monitor.snapshot()["history"][0]["cpu"], 20)

    def test_demo_alert_is_not_real_attention(self):
        self.monitor._apply({"id": "demo", "type": "CPU_HIGH", "message": "Fake CPU high", "demo": True})
        self.assertEqual(self.monitor.snapshot()["alerts"][0]["status"], "demo")


if __name__ == "__main__":
    unittest.main()
