import tempfile
import unittest
from pathlib import Path

from log_reader import LogReader, classify
from monitor import Monitor


class LogReading(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.log = self.root / "service.log"
        self.log.write_text("old message\n", encoding="utf-8")
        self.reader = LogReader(self.log)

    def tearDown(self):
        self.temp.cleanup()

    def test_starts_at_end_and_catches_only_new_lines(self):
        self.assertEqual(self.reader.poll(), [])
        with self.log.open("a", encoding="utf-8") as file:
            file.write("INFO started\nERROR database is down\n")
        self.assertEqual(self.reader.poll(), [("LOG_INFO", "INFO started"), ("LOG_ERROR", "ERROR database is down")])

    def test_partial_lines_wait_until_newline(self):
        self.reader.poll()
        with self.log.open("a", encoding="utf-8") as file:
            file.write("WARN partial")
        self.assertEqual(self.reader.poll(), [])
        with self.log.open("a", encoding="utf-8") as file:
            file.write(" line\n")
        self.assertEqual(self.reader.poll(), [("LOG_WARNING", "WARN partial line")])

    def test_handles_truncation(self):
        self.reader.poll()
        self.log.write_text("ERROR new\n", encoding="utf-8")
        self.assertEqual(self.reader.poll(), [("LOG_ERROR", "ERROR new")])

    def test_log_replacement(self):
        self.reader.poll()
        self.log.rename(self.root / "service.log.1")
        self.log.write_text("WARNING restarted\n", encoding="utf-8")
        self.assertEqual(self.reader.poll(), [("LOG_WARNING", "WARNING restarted")])

    def test_classifies_and_redacts_secrets(self):
        kind, text = classify("ERROR bad password=letmein")
        self.assertEqual(kind, "LOG_ERROR")
        self.assertNotIn("letmein", text)

    def test_missing_log_can_be_recreated(self):
        self.reader.poll()
        self.log.unlink()
        self.assertEqual(self.reader.poll(), [])
        self.log.write_text("new baseline\n", encoding="utf-8")
        self.assertEqual(self.reader.poll(), [])
        with self.log.open("a") as file:
            file.write("ERROR later\n")
        self.assertEqual(self.reader.poll(), [("LOG_ERROR", "ERROR later")])

    def test_monitor_emits_classified_events_and_alert(self):
        monitor = Monitor(self.root / "events.log", self.root / "save.json")
        monitor.log_file.touch()
        monitor.add_watch("log", str(self.log))
        with self.log.open("a", encoding="utf-8") as file:
            file.write("ERROR database disconnected\n")
        monitor._check_watches()
        events = monitor.log_file.read_text()
        self.assertIn("LOG_ERROR", events)
        import json
        for entry in events.splitlines():
            monitor._apply(json.loads(entry))
        self.assertEqual(monitor.snapshot()["pet"]["mood"], "worried")
        self.assertEqual(len(monitor.snapshot()["alerts"]), 1)

    def test_does_not_allow_watching_own_event_log(self):
        monitor = Monitor(self.root / "events.log", self.root / "save.json")
        monitor.log_file.touch()
        with self.assertRaises(ValueError):
            monitor.add_watch("log", str(monitor.log_file))


if __name__ == "__main__":
    unittest.main()
