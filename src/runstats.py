import atexit, time


class Stats:
    """Counts real API calls per department for the current process (replayed
    journal steps cost nothing and are not counted)."""

    def __init__(self):
        self.t0 = time.time()
        self.by = {}  # dept -> {"calls": n, "tokens": n, "providers": {name: n}}
        self.qa_fails = 0

    def note(self, provider, dept, tokens):
        d = self.by.setdefault(dept, {"calls": 0, "tokens": 0, "providers": {}})
        d["calls"] += 1
        d["tokens"] += int(tokens or 0)
        d["providers"][provider] = d["providers"].get(provider, 0) + 1

    def summary(self):
        calls = sum(d["calls"] for d in self.by.values())
        toks = sum(d["tokens"] for d in self.by.values())
        lines = [f"time: {time.time() - self.t0:.0f}s | api calls: {calls} | tokens: {toks:,} | QA fails: {self.qa_fails}"]
        for dept, d in self.by.items():
            prov = ", ".join(f"{p} {n}" for p, n in sorted(d["providers"].items()))
            lines.append(f"{dept}: {d['calls']} calls, {d['tokens']:,} tokens ({prov})")
        return "\n".join(lines)


R = Stats()


def _at_exit():
    if R.by:
        print("\n--- RUN REPORT ---\n" + R.summary())


atexit.register(_at_exit)
