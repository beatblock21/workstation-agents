import contextlib, io, json, os, re, sys, time
import pipeline
from handoff import ROOT

CASES = {
    "L2": "Write a single Python file lru.py with a class LRUCache(capacity) with get(key) returning None when missing and put(key, value) that evicts the least recently used item when full; both operations must be O(1). Put at least six assert tests at the bottom of the same file, including eviction order and updating an existing key.",
    "L3": "Write a small multi-file Python package todo/: todo/models.py (class Task with title and a done flag), todo/store.py (class TaskStore with add, complete, pending; in-memory), todo/report.py (function summary(store) returning a string like '2 pending, 1 done'), and tests/test_todo.py with at least five plain-assert tests.",
    "L4": "Build a fast, secure, offline tool that downloads every page of any website the user chooses, using no network access and no third-party libraries.",
}
USAGE = os.path.join(ROOT, "state", "usage.local.json")

def totals():
    try:
        with open(USAGE) as f:
            u = json.load(f)["usage"]
    except Exception:
        return 0, 0
    return sum(v["requests"] for v in u.values()), sum(v["tokens"] for v in u.values())

class Tee(io.StringIO):
    def write(self, s):
        sys.__stdout__.write(s)
        return super().write(s)

name = sys.argv[1]
auto = name != "L4"  # L4 is deliberately interactive
r0, t0 = totals()
tee = Tee()
start = time.time()
try:
    with contextlib.redirect_stdout(tee):
        res = pipeline.run(CASES[name], auto=auto)
    status = res.status
except Exception as e:
    status = f"CRASH: {type(e).__name__}: {e}"
out = tee.getvalue()
r1, t1 = totals()
print(f"\n=== STRESS RESULT {name} ===")
print("status:", status)
print("seconds:", round(time.time() - start))
print("api requests:", r1 - r0, "| tokens:", t1 - t0)
print("QA fails:", out.count("QA: FAIL"), "| exec checks:", out.count("execution check:"), "| not run:", out.count("execution check: NOT RUN"))
print("providers used:", sorted(set(re.findall(r"answered via (\w+)", out))))
