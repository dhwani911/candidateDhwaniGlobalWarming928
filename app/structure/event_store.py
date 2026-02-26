import json
from pathlib import Path
from typing import List, Dict


class EventStore:

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._event_ids = set()

        if self.file_path.exists():
            for line in self.file_path.read_text().splitlines():
                event = json.loads(line)
                self._event_ids.add(event["event_id"])

    def append(self, event: Dict) -> bool:
        if str(event["event_id"]) in self._event_ids:
            return False

        with open(self.file_path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

        self._event_ids.add(str(event["event_id"]))
        return True

    def load_all(self) -> List[Dict]:
        if not self.file_path.exists():
            return []
        return [json.loads(line) for line in self.file_path.read_text().splitlines()]

    def load_by_locker(self, locker_id: str) -> List[Dict]:
        return [e for e in self.load_all() if e["locker_id"] == locker_id]