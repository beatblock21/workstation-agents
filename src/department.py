import json, os
from llm import chat
from handoff import Handoff, ROOT

with open(os.path.join(ROOT, "agents", "departments.json"), encoding="utf-8") as f:
    CFG = json.load(f)

class Department:
    def __init__(self, name):
        self.name = name
        self.cfg = CFG[name]

    def _ask(self, user, system=None):
        msgs = [{"role": "system", "content": system or self.cfg["prompt"]},
                {"role": "user", "content": user}]
        provider, text = chat(msgs, self.cfg["chain"], dept=self.name, max_tokens=self.cfg.get("max_tokens", 800))
        print(f"   [{self.name}] answered via {provider}")
        return text

    def delegate(self, subtasks):
        """Subagents: narrow task each, same department chain and budget."""
        sp = self.cfg["prompt"] + " You are a subagent: do only the narrow task given and be brief."
        return [self._ask(t, sp) for t in subtasks]

    def run(self, h, next_dept, subtasks=None):
        parts = [f"GOAL:\n{h.goal}", f"INPUT FROM {h.from_dept.upper()}:\n{h.deliverable or '(none)'}"]
        if subtasks:
            for t, r in zip(subtasks, self.delegate(subtasks)):
                parts.append(f"SUBAGENT TASK: {t}\nSUBAGENT RESULT:\n{r}")
        try:
            out, status = self._ask("\n\n".join(parts)), "ok"
        except Exception as e:
            out, status = f"ERROR: {e}", "failed"
        nh = Handoff(goal=h.goal, from_dept=self.name, to_dept=next_dept, deliverable=out, status=status)
        nh.save()
        return nh
