"""Validate Windows command selection from Linux without requiring Ubuntu or WSL."""
from pathlib import Path

import pytest

from runtime import tail_command


def test_native_windows_powershell_fallback(tmp_path):
    logfile = tmp_path / "events.log"
    def which(command):
        return "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" if command == "powershell.exe" else None
    command, label = tail_command(logfile, platform="win32", find_executable=which)
    assert command[0].lower().endswith("powershell.exe")
    assert command[1:4] == ["-NoProfile", "-NonInteractive", "-Command"]
    assert "Get-Content" in command[4]
    assert "-Tail 2147483647 -Wait" in command[4]
    assert "-Encoding UTF8" in command[4]
    assert label == "PowerShell Get-Content -Tail -Wait"


def test_windows_prefers_gnu_tail_when_available(tmp_path):
    cmd, label = tail_command(tmp_path / "events.log", platform="win32", find_executable=lambda name: "C:/Git/usr/bin/tail.exe" if name == "tail" else None)
    assert cmd[0] == "C:/Git/usr/bin/tail.exe"
    assert cmd[1:4] == ["-n", "+1", "-F"]
    assert "GNU tail" in label


def test_windows_powershell_escapes_apostrophes(tmp_path):
    cmd, _ = tail_command(tmp_path / "it's ready.log", platform="win32", find_executable=lambda name: "powershell.exe" if name == "powershell.exe" else None)
    assert "it''s ready.log" in cmd[-1]


def test_windows_missing_followers_has_useful_error(tmp_path):
    with pytest.raises(RuntimeError, match="PowerShell"):
        tail_command(tmp_path / "events.log", platform="win32", find_executable=lambda name: None)
