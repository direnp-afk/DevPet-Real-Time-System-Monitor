"""Pure game-state rules. The event log is the source of truth."""
from collections import deque

EFFECTS = {
    "CPU_HIGH": (-5, -8, +18, 0, "stressed"),
    "RAM_HIGH": (-5, -10, +15, 0, "tired"),
    "APP_CRASH": (-25, -12, +30, 0, "sick"),
    "APP_STOPPED": (-3, -2, +5, 0, "worried"),
    "TEST_FAILED": (-12, -6, +16, 0, "sad"),
    "TEST_PASSED": (+8, +10, -10, +25, "excited"),
    "BUILD_SUCCESS": (+12, +10, -12, +30, "excited"),
    "GIT_COMMIT": (+4, +5, -6, +15, "happy"),
    "SYSTEM_RECOVERED": (+8, +12, -18, 0, "happy"),
}
ALERT_TYPES = frozenset({"CPU_HIGH", "RAM_HIGH", "APP_CRASH", "APP_STOPPED", "TEST_FAILED"})
SUPPORTED_DEMO_EVENTS = {
    "CPU_HIGH": "Demo: CPU jumped to 96%",
    "RAM_HIGH": "Demo: memory usage reached 94%",
    "APP_CRASH": "Demo: server.py exited with an error",
    "TEST_FAILED": "Demo: 3 tests failed",
    "TEST_PASSED": "Demo: all 24 tests passed",
    "BUILD_SUCCESS": "Demo: build completed successfully",
    "GIT_COMMIT": "Demo: changes committed successfully",
    "SYSTEM_RECOVERED": "Demo: system has recovered",
}


def clamp(number):
    return max(0, min(100, int(number)))


class PetEngine:
    """Deterministic replay of JSONL log events."""

    def __init__(self):
        self.health = 85
        self.energy = 80
        self.stress = 15
        self.total_xp = 0
        self.mood = "happy"
        self.events_seen = 0
        self.alerts_seen = 0
        self.recent = deque(maxlen=40)
        self.metrics_history = deque(maxlen=40)
        self.cpu = None
        self.ram = None
        self.last_event = None

    def apply(self, event):
        event_type = event.get("type")
        if not isinstance(event_type, str):
            return
        if event_type == "METRIC":
            try:
                cpu = float(event["cpu"])
                ram = float(event["ram"])
                if 0 <= cpu <= 100 and 0 <= ram <= 100:
                    self.cpu, self.ram = round(cpu, 1), round(ram, 1)
                    self.metrics_history.append({"cpu": self.cpu, "ram": self.ram})
            except (TypeError, ValueError, KeyError):
                pass
            return

        self.events_seen += 1
        self.last_event = event_type
        self.recent.appendleft({
            "id": str(event.get("id", "")),
            "ts": str(event.get("ts", "")),
            "type": event_type,
            "message": str(event.get("message", ""))[:240],
        })
        if event_type in ALERT_TYPES:
            self.alerts_seen += 1
        if event_type in EFFECTS:
            health, energy, stress, xp, mood = EFFECTS[event_type]
            self.health = clamp(self.health + health)
            self.energy = clamp(self.energy + energy)
            self.stress = clamp(self.stress + stress)
            self.total_xp += xp
            self.mood = mood

    def snapshot(self):
        return {
            "pet": {
                "name": "Byte",
                "mood": self.mood,
                "health": self.health,
                "energy": self.energy,
                "stress": self.stress,
                "level": self.total_xp // 100 + 1,
                "xp": self.total_xp % 100,
                "total_xp": self.total_xp,
            },
            "system": {"cpu": self.cpu, "ram": self.ram},
            "history": list(self.metrics_history),
            "events": list(self.recent),
            "events_seen": self.events_seen,
            "alerts_seen": self.alerts_seen,
        }
