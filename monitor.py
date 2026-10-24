import json
import os
import time
import shutil
import subprocess
import sys
import threading
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

from log_reader import LogReader

import psutil

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LOG_FILE = DATA_DIR / "events.log"
SAVE_FILE = DATA_DIR / "save.json"
SKIP_FOLDERS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".idea"}

CHANGES = {
    "CPU_HIGH": (-7, 12, 0, "stressed"),
    "MEMORY_HIGH": (-7, 12, 0, "stressed"),
    "APP_STOPPED": (-12, 16, 0, "worried"),
    "FILE_DELETED": (-4, 5, 0, "worried"),
    "TEST_FAILED": (-9, 12, 0, "sad"),
    "BUILD_FAILED": (-9, 12, 0, "sad"),
    "CPU_NORMAL": (6, -8, 5, "happy"),
    "MEMORY_NORMAL": (6, -8, 5, "happy"),
    "APP_STARTED": (6, -6, 10, "happy"),
    "FILE_ADDED": (0, -1, 4, "happy"),
    "FILE_CHANGED": (0, -1, 3, "happy"),
    "TEST_PASSED": (7, -8, 25, "excited"),
    "BUILD_PASSED": (7, -8, 25, "excited"),
    "LOG_ERROR": (-8, 12, 0, "worried"),
    "LOG_WARNING": (-2, 4, 0, "stressed"),
}


def log_follow_command(path, platform=None, lookup=None):
    platform = platform or sys.platform
    lookup = lookup or shutil.which
    path = str(Path(path).resolve())
    tail = lookup("tail")
    if platform == "win32":
        locations = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/usr/bin/tail.exe",
            Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local")) / "Programs/Git/usr/bin/tail.exe",
        ]
        tail = tail or next((str(p) for p in locations if p.is_file()), None)
        if tail:
            return [tail, "-n", "0", "-F", path], "GNU tail"
        powershell = lookup("powershell.exe") or lookup("pwsh.exe")
        if powershell:
            safe_path = path.replace("'", "''")
            cmd = f"[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); Get-Content -LiteralPath '{safe_path}' -Encoding UTF8 -Tail 0 -Wait"
            return [powershell, "-NoProfile", "-NonInteractive", "-Command", cmd], "PowerShell log follower"
        raise RuntimeError("Install Git for Windows or use Windows PowerShell to follow logs")
    if tail:
        return [tail, "-n", "0", "-F", path], "GNU tail"
    raise RuntimeError("The tail command is missing")


def scan_folder(folder):
    result = {}
    for root, folders, files in os.walk(folder, followlinks=False):
        folders[:] = [name for name in folders if name not in SKIP_FOLDERS and not (Path(root) / name).is_symlink()]
        for name in files:
            path = Path(root) / name
            try:
                info = path.stat()
                result[str(path.relative_to(folder))] = (info.st_mtime_ns, info.st_size)
            except OSError:
                continue
            if len(result) >= 1500:
                return result
    return result


class Monitor:
    def __init__(self, log_file=LOG_FILE, save_file=SAVE_FILE, interval=2):
        self.log_file = Path(log_file).resolve()
        self.save_file = Path(save_file).resolve()
        self.interval = interval
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.threads = []
        self.follower = None
        self.follower_name = "Not started"
        self.follower_error = ""
        self.watched_before = {}
        self.cpu_alert = False
        self.memory_alert = False
        self.history = deque(maxlen=60)
        self.log_readers = {}
        self.network_before = None
        self.network_at = None
        self.last_log_alert = {}
        self.data = {
            "pet": {"name": "Byte", "health": 85, "stress": 15, "xp": 0, "mood": "happy", "reason": "System is running normally"},
            "system": {"cpu": None, "memory": None, "disk": None, "download": None, "upload": None},
            "alerts": [],
            "events": [],
            "watches": [],
        }
        self._load()

    def _load(self):
        try:
            old = json.loads(self.save_file.read_text(encoding="utf-8"))
            if isinstance(old.get("pet"), dict):
                for key in self.data["pet"]:
                    if key in old["pet"]:
                        self.data["pet"][key] = old["pet"][key]
            if isinstance(old.get("events"), list):
                self.data["events"] = old["events"][:50]
            if isinstance(old.get("alerts"), list):
                self.data["alerts"] = old["alerts"][:15]
            if isinstance(old.get("watches"), list):
                for item in old["watches"][:12]:
                    if item.get("kind") in ("process", "folder", "log") and isinstance(item.get("target"), str):
                        self.data["watches"].append({"kind": item["kind"], "target": item["target"], "status": "checking"})
        except (FileNotFoundError, OSError, TypeError, ValueError, KeyError):
            pass

    def save(self):
        self.save_file.parent.mkdir(parents=True, exist_ok=True)
        record = {key: self.data[key] for key in ("pet", "events", "alerts", "watches")}
        temp = self.save_file.with_suffix(".tmp")
        temp.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(temp, self.save_file)

    def start(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.touch(exist_ok=True)
        command, self.follower_name = log_follow_command(self.log_file)
        self.follower = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace", text=True, bufsize=1,
        )
        self.threads = [
            threading.Thread(target=self._read_events, daemon=True),
            threading.Thread(target=self._read_errors, daemon=True),
            threading.Thread(target=self._sample, daemon=True),
        ]
        for worker in self.threads:
            worker.start()

    def stop(self):
        self.stop_event.set()
        if self.follower and self.follower.poll() is None:
            self.follower.terminate()
            try:
                self.follower.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.follower.kill()
                self.follower.wait(timeout=2)
        for worker in self.threads:
            worker.join(timeout=3)
        if self.follower:
            for stream in (self.follower.stdout, self.follower.stderr):
                if stream and not stream.closed:
                    stream.close()
        with self.lock:
            self.save()

    def emit(self, kind, message, demo=False, **extra):
        event = {
            "id": uuid.uuid4().hex,
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "type": kind,
            "message": message[:180],
            "demo": demo,
        }
        event.update(extra)
        payload = (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        fd = os.open(self.log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        return event

    def _read_events(self):
        try:
            for line in self.follower.stdout:
                if self.stop_event.is_set():
                    break
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    self._apply(event)
        except OSError as exc:
            self.follower_error = str(exc)
        if not self.stop_event.is_set():
            self.follower_error = self.follower_error or "Log follower stopped"

    def _read_errors(self):
        if not self.follower:
            return
        try:
            errors = self.follower.stderr.read(500)
            if errors and not self.stop_event.is_set():
                self.follower_error = errors.strip()
        except (OSError, ValueError):
            pass

    def _apply(self, event):
        with self.lock:
            kind = event.get("type")
            if kind == "METRIC":
                data = event.get("system", {})
                if isinstance(data, dict):
                    self.data["system"] = data
                    self.history.append({"time": event.get("time"), "cpu": data.get("cpu"), "memory": data.get("memory")})
                return
            if not isinstance(kind, str):
                return
            self.data["events"].insert(0, event)
            self.data["events"] = self.data["events"][:50]
            if kind in ("CPU_NORMAL", "MEMORY_NORMAL", "APP_STARTED"):
                matches = {"CPU_NORMAL": "CPU_HIGH", "MEMORY_NORMAL": "MEMORY_HIGH", "APP_STARTED": "APP_STOPPED"}
                for alert in self.data["alerts"]:
                    if alert["type"] == matches[kind] and (kind != "APP_STARTED" or alert.get("target") == event.get("target")):
                        alert["status"] = "recovered"
            log_repeat = False
            if kind in ("LOG_ERROR", "LOG_WARNING"):
                key = (kind, event.get("source"))
                now = time.monotonic()
                log_repeat = now - self.last_log_alert.get(key, -1000) < 10
                if not log_repeat:
                    self.last_log_alert[key] = now
            if kind in ("CPU_HIGH", "MEMORY_HIGH", "APP_STOPPED", "LOG_ERROR", "LOG_WARNING", "TEST_FAILED", "BUILD_FAILED", "MONITOR_ERROR") and not log_repeat:
                self.data["alerts"].insert(0, {"id": event.get("id"), "type": kind, "message": event.get("message"), "time": event.get("time"), "target": event.get("target"), "status": "demo" if event.get("demo") else "new"})
                self.data["alerts"] = self.data["alerts"][:15]
            if kind in CHANGES and not log_repeat:
                health, stress, xp, mood = CHANGES[kind]
                pet = self.data["pet"]
                pet["health"] = max(0, min(100, pet["health"] + health))
                pet["stress"] = max(0, min(100, pet["stress"] + stress))
                if not event.get("demo"):
                    pet["xp"] += xp
                pet["mood"] = mood
                pet["reason"] = event.get("message", "")
            self.save()

    def _sample(self):
        psutil.cpu_percent(interval=None)
        while not self.stop_event.wait(self.interval):
            try:
                cpu = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory().percent
                disk = psutil.disk_usage(str(Path.home().anchor or "/")).percent
                now = time.monotonic()
                counters = psutil.net_io_counters()
                upload = download = 0.0
                if counters and self.network_before and self.network_at:
                    elapsed = max(now - self.network_at, 0.01)
                    download = max(0.0, (counters.bytes_recv - self.network_before.bytes_recv) / elapsed / 1024)
                    upload = max(0.0, (counters.bytes_sent - self.network_before.bytes_sent) / elapsed / 1024)
                self.network_before, self.network_at = counters, now
                self.emit("METRIC", "System reading", system={"cpu": cpu, "memory": memory, "disk": disk, "download": round(download, 1), "upload": round(upload, 1)})
                if cpu >= 90 and not self.cpu_alert:
                    self.emit("CPU_HIGH", f"CPU usage reached {cpu:.0f}%")
                    self.cpu_alert = True
                elif cpu < 75 and self.cpu_alert:
                    self.emit("CPU_NORMAL", "CPU usage returned to normal")
                    self.cpu_alert = False
                if memory >= 90 and not self.memory_alert:
                    self.emit("MEMORY_HIGH", f"Memory usage reached {memory:.0f}%")
                    self.memory_alert = True
                elif memory < 75 and self.memory_alert:
                    self.emit("MEMORY_NORMAL", "Memory usage returned to normal")
                    self.memory_alert = False
                self._check_watches()
            except (OSError, psutil.Error, ValueError) as exc:
                self.emit("MONITOR_ERROR", f"Could not sample system: {exc}")

    def _check_watches(self):
        with self.lock:
            watches = list(self.data["watches"])
        for item in watches:
            key = (item["kind"], item["target"])
            if item["kind"] == "process":
                target = item["target"]
                process = None
                try:
                    if target.startswith("pid:"):
                        candidate = psutil.Process(int(target[4:]))
                        if candidate.is_running() and candidate.status() != psutil.STATUS_ZOMBIE:
                            process = candidate
                    else:
                        process = next((p for p in psutil.process_iter(["name"]) if str(p.info.get("name") or "").lower() == target), None)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process = None
                online = process is not None
                previous = self.watched_before.get(key)
                if previous is not None and previous != online:
                    self.emit("APP_STARTED" if online else "APP_STOPPED", f"{target} {'started' if online else 'stopped'}", target=target)
                self.watched_before[key] = online
                status = "not running"
                if online:
                    try:
                        memory_mb = process.memory_info().rss / (1024 * 1024)
                        status = f"running · {memory_mb:.0f} MB"
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        status = "running"
            elif item["kind"] == "log":
                path = Path(item["target"])
                if not path.is_file():
                    status = "log missing"
                    self.log_readers.pop(key, None)
                else:
                    status = "following"
                    reader = self.log_readers.setdefault(key, LogReader(path))
                    for kind, message in reader.poll():
                        self.emit(kind, f"{path.name}: {message}", source=path.name)
            else:
                path = Path(item["target"])
                if not path.is_dir():
                    status = "folder missing"
                    previous = self.watched_before.get(key)
                    if previous is not None:
                        self.emit("FOLDER_MISSING", f"Folder is no longer available: {path.name}")
                        self.watched_before.pop(key, None)
                else:
                    status = "watching"
                    current = scan_folder(path)
                    previous = self.watched_before.get(key)
                    if isinstance(previous, dict):
                        created = current.keys() - previous.keys()
                        deleted = previous.keys() - current.keys()
                        changed = {f for f in current.keys() & previous.keys() if current[f] != previous[f]}
                        for kind, paths in (("FILE_ADDED", created), ("FILE_DELETED", deleted), ("FILE_CHANGED", changed)):
                            for relative in sorted(paths)[:12]:
                                self.emit(kind, f"{path.name} / {relative}")
                    self.watched_before[key] = current
            with self.lock:
                if item in self.data["watches"]:
                    item["status"] = status

    def add_watch(self, kind, target):
        target = str(target).strip()
        if kind not in ("folder", "process", "log") or not target or len(target) > 300:
            raise ValueError("Choose a type and enter a valid path or process")
        if kind in ("folder", "log"):
            path = Path(target).expanduser().resolve()
            if kind == "folder" and not path.is_dir():
                raise ValueError("This folder doesn't exist")
            if kind == "log" and not path.is_file():
                raise ValueError("This log file doesn't exist")
            if kind == "log" and path == self.log_file:
                raise ValueError("DevPet's own event log cannot be watched")
            target = str(path)
        else:
            if target.isdigit():
                target = f"pid:{target}"
            if not (target.startswith("pid:") and target[4:].isdigit() and int(target[4:]) > 0):
                if any(c in target for c in "\\/:*?\"<>|"):
                    raise ValueError("Enter a process name such as notepad.exe or a PID")
                target = target.lower()
        with self.lock:
            if len(self.data["watches"]) >= 8:
                raise ValueError("You can watch up to 8 things")
            if any(w["kind"] == kind and w["target"] == target for w in self.data["watches"]):
                raise ValueError("Already watching this")
            self.data["watches"].append({"kind": kind, "target": target, "status": "checking"})
            if kind == "log":
                reader = LogReader(target)
                reader.poll()
                self.log_readers[(kind, target)] = reader
            self.save()
        return target

    def remove_watch(self, kind, target):
        with self.lock:
            original = len(self.data["watches"])
            self.data["watches"] = [w for w in self.data["watches"] if (w["kind"], w["target"]) != (kind, target)]
            if len(self.data["watches"]) == original:
                raise ValueError("Watch not found")
            self.watched_before.pop((kind, target), None)
            self.log_readers.pop((kind, target), None)
            self.save()

    def snapshot(self):
        with self.lock:
            state = json.loads(json.dumps(self.data))
        state["history"] = list(self.history)
        state["tail"] = {
            "method": self.follower_name,
            "running": self.follower is not None and self.follower.poll() is None and not self.follower_error,
            "error": self.follower_error,
        }
        return state

    def acknowledge(self, alert_id):
        with self.lock:
            for alert in self.data["alerts"]:
                if alert.get("id") == alert_id:
                    if alert["status"] == "new":
                        alert["status"] = "acknowledged"
                        self.save()
                    return
        raise ValueError("Alert not found")
