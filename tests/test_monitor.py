import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monitor import Monitor, log_follow_command, scan_folder


class DevPetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name)
        self.monitor = Monitor(path / "events.log", path / "save.json", interval=0.1)
        self.monitor.log_file.touch()

    def tearDown(self):
        self.temp.cleanup()

    def test_folder_scan_detects_edits(self):
        folder = Path(self.temp.name) / "testfiles"
        folder.mkdir()
        file = folder / "sample.txt"
        self.assertEqual(scan_folder(folder), {})
        file.write_text("first")
        initial = scan_folder(folder)
        file.write_text("something longer")
        self.assertNotEqual(initial, scan_folder(folder))

    def test_add_and_remove_watch(self):
        path = str(Path(self.temp.name))
        self.monitor.add_watch("folder", path)
        self.assertEqual(len(self.monitor.snapshot()["watches"]), 1)
        with self.assertRaises(ValueError):
            self.monitor.add_watch("folder", path)
        self.monitor.remove_watch("folder", path)
        self.assertFalse(self.monitor.snapshot()["watches"])

    def test_process_input(self):
        self.monitor.add_watch("process", "notepad.exe")
        self.monitor.add_watch("process", "4321")
        self.assertEqual(self.monitor.snapshot()["watches"][1]["target"], "pid:4321")

    def test_real_events_affect_xp_and_demo_does_not(self):
        self.monitor._apply({"id": "1", "type": "TEST_PASSED", "message": "OK", "demo": False})
        self.assertEqual(self.monitor.snapshot()["pet"]["xp"], 25)
        self.monitor._apply({"id": "2", "type": "TEST_PASSED", "message": "demo", "demo": True})
        self.assertEqual(self.monitor.snapshot()["pet"]["xp"], 25)

    def test_cpu_reading_no_event_history(self):
        self.monitor._apply({"type": "METRIC", "system": {"cpu": 42, "memory": 34, "disk": 12}})
        self.assertEqual(self.monitor.snapshot()["system"]["cpu"], 42)
        self.assertFalse(self.monitor.snapshot()["events"])

    def test_save_load(self):
        self.monitor.add_watch("process", "notepad.exe")
        self.monitor._apply({"id": "1", "type": "BUILD_PASSED", "message": "OK"})
        restored = Monitor(self.monitor.log_file, self.monitor.save_file)
        self.assertEqual(restored.snapshot()["pet"]["xp"], 25)
        self.assertEqual(len(restored.snapshot()["watches"]), 1)

    def test_event_is_jsonl(self):
        self.monitor.emit("APP_STOPPED", "Example", demo=True)
        event = json.loads(self.monitor.log_file.read_text().strip())
        self.assertEqual(event["type"], "APP_STOPPED")
        self.assertTrue(event["demo"])

    def test_windows_powershell_fallback(self):
        with patch("monitor.Path.is_file", return_value=False):
            command, name = log_follow_command(self.monitor.log_file, "win32", lambda key: "powershell.exe" if key == "powershell.exe" else None)
        self.assertEqual(command[0], "powershell.exe")
        self.assertIn("-Tail 0 -Wait", command[-1])
        self.assertIn("PowerShell", name)

    def test_gnu_tail(self):
        command, label = log_follow_command(self.monitor.log_file, "linux", lambda key: "/usr/bin/tail")
        self.assertEqual(command[1:4], ["-n", "0", "-F"])
        self.assertEqual(label, "GNU tail")


if __name__ == "__main__":
    unittest.main()
