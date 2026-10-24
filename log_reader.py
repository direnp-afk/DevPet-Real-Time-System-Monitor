import re
from pathlib import Path

ERROR = re.compile(r"\b(error|critical|fatal|exception|traceback)\b", re.I)
WARNING = re.compile(r"\b(warn|warning)\b", re.I)
SECRET = re.compile(r"\b(password|token|api[_-]?key|secret)\s*[:=]\s*[^\s,;]+", re.I)


def classify(line):
    text = SECRET.sub(r"\1=[REDACTED]", line.strip())[:180]
    if ERROR.search(text):
        return "LOG_ERROR", text
    if WARNING.search(text):
        return "LOG_WARNING", text
    return "LOG_INFO", text


class LogReader:
    def __init__(self, path):
        self.path = Path(path)
        self.position = None
        self.identity = None
        self.pending = b""

    def poll(self):
        try:
            stat = self.path.stat()
            identity = (stat.st_dev, stat.st_ino, stat.st_ctime_ns if not stat.st_ino else None)
            if self.position is None:
                self.position = stat.st_size
                self.identity = identity
                return []
            if self.identity != identity or stat.st_size < self.position:
                self.identity = identity
                self.position = 0
                self.pending = b""
            with self.path.open("rb") as stream:
                stream.seek(self.position)
                data = stream.read(65536)
                self.position = stream.tell()
        except (FileNotFoundError, PermissionError, OSError):
            self.position = None
            self.identity = None
            self.pending = b""
            return []
        if not data:
            return []
        lines = (self.pending + data).split(b"\n")
        self.pending = lines.pop()[-4096:]
        events = []
        for raw in lines:
            text = raw.decode("utf-8", errors="replace").rstrip("\r")
            if text.strip():
                events.append(classify(text))
        important = [i for i, item in enumerate(events) if item[0] != "LOG_INFO"][:12]
        normal = [i for i, item in enumerate(events) if item[0] == "LOG_INFO"][-3:]
        return [events[i] for i in sorted(important + normal)][:15]
