import os
import journal, llm, pipeline

calls, state = [], {"crash": True}

def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    calls.append(dept)
    if dept == "qa" and state["crash"]:
        raise KeyboardInterrupt("simulated crash")
    if dept == "dev":
        return "### FILE: a.py\n```python\nassert 1 == 1\n```"
    if dept == "qa":
        return "PASS\n1. ok"
    if dept == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    return "OPTION A: x\nRECOMMENDATION: A - y"

llm.ask = fake_ask
rid = "test-resume-" + str(os.getpid())
journal.J.start(rid, {"goal": "demo", "auto": True, "repo": None})
try:
    pipeline.run("demo", auto=True)
    crashed = False
except KeyboardInterrupt:
    crashed = True
first = len(calls)
print("PASS" if crashed and first == 3 else "FAIL", "- first run crashed at the qa step after", first, "calls")

journal.J.start(rid)
state["crash"] = False
res = pipeline.run("demo", auto=True)
new = len(calls) - first
print("PASS" if new == 2 else "FAIL", "- resume made", new, "new calls (expected 2: qa and shipping)")
print("PASS" if res.status == "ok" else "FAIL", "- resumed run finished with status", res.status)
os.remove(journal.J.path)
