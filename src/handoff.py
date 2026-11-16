import json, os, time, uuid
from dataclasses import dataclass, field, asdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DIR = os.path.join(ROOT, "state")

@dataclass
class Handoff:
    goal: str
    from_dept: str
    to_dept: str
    deliverable: str = ""
    status: str = "ok"  # ok | needs_human | failed
    open_questions: list = field(default_factory=list)
    files: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    id: str = field(default_factory=lambda: time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4])

    def save(self):
        os.makedirs(DIR, exist_ok=True)
        path = os.path.join(DIR, f"handoff-{self.id}.local.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=1)
        return path

    @staticmethod
    def load(path):
        with open(path, encoding="utf-8") as f:
            return Handoff(**json.load(f))
