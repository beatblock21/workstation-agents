import json, os
from handoff import ROOT

class Journal:
    def __init__(self):
        self.path = None
        self.entries = []
        self.meta = {}
        self.pos = 0
        self.last_replayed = False

    def start(self, run_id, meta=None):
        self.path = os.path.join(ROOT, "state", f"run-{run_id}.local.json")
        self.entries, self.pos, self.last_replayed = [], 0, False
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.entries, self.meta = data.get("entries", []), data.get("meta", {})
        else:
            self.meta = meta or {}
            self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"meta": self.meta, "entries": self.entries}, f, indent=1)

    def replay(self, kind):
        self.last_replayed = False
        if self.path and self.pos < len(self.entries):
            e = self.entries[self.pos]
            if e["kind"] == kind:
                self.pos += 1
                self.last_replayed = True
                return e["value"]
            self.entries = self.entries[:self.pos]  # diverged: stop replaying
        return None

    def record(self, kind, value):
        if not self.path:
            return
        self.entries.append({"kind": kind, "value": value})
        self.pos = len(self.entries)
        self._save()

    def finish(self):
        if self.path:
            self.meta["done"] = True
            self._save()

J = Journal()
