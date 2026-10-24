"""Small, validated per-user desktop settings; never stores API credentials."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass
class DesktopSettings:
    shortcut: str = ""
    spoken_replies: bool = True
    microphone: int | None = None
    pause_seconds: float = 0.6

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            return cls(
                shortcut=data.get("shortcut", "") if isinstance(data.get("shortcut", ""), str) else "",
                spoken_replies=data.get("spoken_replies", True) is not False,
                microphone=data.get("microphone") if type(data.get("microphone")) is int else None,
                pause_seconds=data.get("pause_seconds", 0.6) if data.get("pause_seconds") in (0.6, 0.9, 1.4) else 0.6,
            )
        except (OSError, ValueError):
            return cls()

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        temporary.replace(path)
