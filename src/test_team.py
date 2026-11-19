import human, llm, pipeline, team

users = []          # (dept, system, user) for every fake LLM call
FAIL = {"on": False}
NOTE = {"text": "note from specialist"}
BRIEF = {"text": "OPTION A: x\nRECOMMENDATION: OPTION A - y"}

def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    sysm, usr = messages[0]["content"], messages[-1]["content"]
    users.append((dept, sysm, usr))
    if FAIL["on"] and "requirements analyst" in sysm:
        raise RuntimeError("boom")
    if dept == "dev":
        return "### FILE: a.py\n```python\nassert 1 == 1\n```"
    if dept == "qa":
        return "PASS\n1. ok"
    if dept == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    if dept == "research" and "Research specialist" in sysm:
        return NOTE["text"]
    return BRIEF["text"]

llm.ask = fake_ask
llm.RETRY_WAIT = False
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

n = len(users); out = team.notes("g", "solo")
check("solo: no calls, empty notes", out == "" and len(users) == n)

n = len(users); out = team.notes("g", "small")
check("small: 2 specialist calls", len(users) - n == 2 and "SPECIALIST NOTES" in out)

n = len(users); team.notes("g", "full")
check("full (default profile): 3 calls", len(users) - n == 3)

n = len(users); team.notes("g", "full", "cli-tool")
check("full (cli-tool profile): 4 calls", len(users) - n == 4)

FAIL["on"] = True
out = team.notes("g", "small")
FAIL["on"] = False
check("failed specialist is skipped, others kept", "note from specialist" in out)

try:
    team.notes("g", "huge")
    check("unknown scale raises", False)
except ValueError:
    check("unknown scale raises", True)

s = len(users)
res = pipeline.run("demo", auto=True, scale="small")
research = [u for u in users[s:] if u[0] == "research"]
check("pipeline small/auto: 2 specialists + 1 admin call", len(research) == 3)
check("admin input carries SPECIALIST NOTES", "SPECIALIST NOTES" in research[-1][2])
check("pipeline small/auto finished ok", res.status == "ok")

s = len(users)
res = pipeline.run("demo", auto=True)
check("solo pipeline: only 1 research call", len([u for u in users[s:] if u[0] == "research"]) == 1)

asked = []
def fake_human(kind, dept, question, options=None):
    asked.append((kind, question))
    return "go with A"
human.ask_human = fake_human
human.ask_text = lambda dept, q, kind="question": "(use your judgment)"
human.log_decision = lambda rec: None

BRIEF["text"] = "OPTION A: x\nOPTION B: y\nDISPUTE: speed vs safety\nRECOMMENDATION: OPTION A - y"
pipeline.run("demo", auto=False, scale="small")
check("unresolved DISPUTE reaches the owner", any(k == "dispute" and "speed vs safety" in q for k, q in asked))

asked.clear()
BRIEF["text"] = "OPTION A: x\nOPTION B: y\nDISPUTE: none\nRECOMMENDATION: OPTION A - y"
pipeline.run("demo", auto=False, scale="small")
check("'DISPUTE: none' does not bother the owner", not any(k == "dispute" for k, q in asked))

asked.clear()
NOTE["text"] = "CONFLICT: speed vs safety"
BRIEF["text"] = "OPTION A: x\nOPTION B: y\nRECOMMENDATION: OPTION A - y"
pipeline.run("demo", auto=True, scale="small")
check("auto: specialist CONFLICT forces the owner decision", any(k == "decision" for k, q in asked))

asked.clear()
NOTE["text"] = "NONE"
pipeline.run("demo", auto=True, scale="small")
check("auto: no conflict means no question", not asked)

print(f"\n{sum(results)}/{len(results)} passed")
