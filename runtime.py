"""Connect psutil -> JSONL events -> tail CLI -> pet game state."""
import json
import os
import shutil
import sys
import subprocess
import threading
from pathlib import Path

import psutil

from event_log import DEFAULT_LOG, write_event
from pet_engine import PetEngine


def tail_command(log_path, platform=None, find_executable=None):
    """Return a native command that replays an existing log and follows new lines.

    Prefer the genuine GNU `tail` CLI. On Windows, use Git for Windows' tail.exe
    when present; otherwise use built-in Windows PowerShell's Get-Content -Tail -Wait.
    """
    platform = sys.platform if platform is None else platform
    find_executable = shutil.which if find_executable is None else find_executable
    logfile = str(Path(log_path).resolve())

    found_tail = find_executable("tail")
    if platform == "win32":
        # Git for Windows includes a GNU tail.exe, often outside of PATH.
        git_paths = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "usr" / "bin" / "tail.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Git" / "usr" / "bin" / "tail.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "usr" / "bin" / "tail.exe",
        ]
        executable = found_tail or next((str(p) for p in git_paths if p.is_file()), None)
        if executable:
            return [executable, "-n", "+1", "-F", logfile], "GNU tail -n +1 -F (native Windows)"

        powershell = find_executable("powershell.exe") or find_executable("pwsh.exe")
        if not powershell:
            raise RuntimeError(
                "Neither GNU tail nor Windows PowerShell was found. "
                "PowerShell is included with Windows 10/11."
            )
        # -Tail MaxInt32 starts with the existing log (for persistence), and
        # -Wait streams appended lines. Quote apostrophes safely in PS literals.
        quoted = logfile.replace("'", "''")
        script = (
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "$ErrorActionPreference = 'Stop'; "
            f"Get-Content -LiteralPath '{quoted}' -Encoding UTF8 -Tail 2147483647 -Wait"
        )
        return [powershell, "-NoProfile", "-NonInteractive", "-Command", script], "PowerShell Get-Content -Tail -Wait"

    if found_tail:
        return [found_tail, "-n", "+1", "-F", logfile], "GNU tail -n +1 -F"
    raise RuntimeError("GNU `tail` was not found. Install coreutils or run on Windows with PowerShell.")


class DevPetRuntime:
    def __init__(self, log_path=DEFAULT_LOG, poll_seconds=2, watch_pid=None):
        self.log_path = Path(log_path).resolve()
        self.poll_seconds = poll_seconds
        self.watch_pid = watch_pid
        self.state = PetEngine()
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.tail_process = None
        self.threads = []
        self.tail_error = ""
        self.tail_label = ""
        self._started = False
        self._was_alerting = False

    def start(self):
        if self._started:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.touch(exist_ok=True)
        command, self.tail_label = tail_command(self.log_path)
        self.tail_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self._started = True
        self.threads = [
            threading.Thread(target=self._read_tail, name="devpet-tail", daemon=True),
            threading.Thread(target=self._monitor, name="devpet-monitor", daemon=True),
        ]
        for thread in self.threads:
            thread.start()

    def _read_tail(self):
        try:
            for line in self.tail_process.stdout:
                if self.stop_flag.is_set():
                    break
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        continue
                except (json.JSONDecodeError, UnicodeError):
                    continue  # malformed lines should not crash the app
                with self.lock:
                    self.state.apply(event)
        except OSError as exc:
            self.tail_error = str(exc)
        finally:
            if not self.stop_flag.is_set():
                self.tail_error = "Log follower stopped unexpectedly. Restart DevPet."

    def _monitor(self):
        psutil.cpu_percent(interval=None)  # Prime sampling rather than recording an inaccurate first sample.
        high_cpu = False
        high_ram = False
        pid_seen = False
        target_created = None
        if self.watch_pid is not None:
            try:
                target_created = psutil.Process(self.watch_pid).create_time()
                pid_seen = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        while not self.stop_flag.wait(self.poll_seconds):
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                write_event("METRIC", "System resource sample", self.log_path, cpu=cpu, ram=ram)

                if cpu >= 90 and not high_cpu:
                    write_event("CPU_HIGH", f"CPU usage is high ({cpu:.0f}%)", self.log_path)
                    high_cpu = True
                elif cpu <= 75 and high_cpu:
                    high_cpu = False

                if ram >= 90 and not high_ram:
                    write_event("RAM_HIGH", f"Memory usage is high ({ram:.0f}%)", self.log_path)
                    high_ram = True
                elif ram <= 75 and high_ram:
                    high_ram = False

                if not high_cpu and not high_ram and self._was_alerting:
                    write_event("SYSTEM_RECOVERED", "CPU and RAM returned to normal", self.log_path)
                self._was_alerting = high_cpu or high_ram

                if self.watch_pid is not None and pid_seen:
                    try:
                        p = psutil.Process(self.watch_pid)
                        alive = p.create_time() == target_created and p.is_running() and p.status() != psutil.STATUS_ZOMBIE
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        alive = False
                    if not alive:
                        write_event("APP_STOPPED", f"Watched process {self.watch_pid} exited or stopped", self.log_path)
                        pid_seen = False
            except (psutil.Error, OSError, ValueError) as exc:
                # Nonfatal monitoring errors should be visible rather than silently killing the thread.
                try:
                    write_event("MONITOR_ERROR", f"Monitoring issue: {exc}", self.log_path)
                except OSError:
                    pass


    def emit(self, kind, message):
        return write_event(kind, message, self.log_path)

    def snapshot(self):
        with self.lock:
            result = self.state.snapshot()
        result["tail"] = {
            "running": bool(self.tail_process and self.tail_process.poll() is None and not self.tail_error),
            "command": self.tail_label,
            "error": self.tail_error,
        }
        result["watch_pid"] = self.watch_pid
        return result

    def stop(self):
        self.stop_flag.set()
        if self.tail_process and self.tail_process.poll() is None:
            self.tail_process.terminate()
            try:
                self.tail_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.tail_process.kill()
                self.tail_process.wait(timeout=2)
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=3)
