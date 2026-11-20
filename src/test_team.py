import human, llm, pipeline, team

users = []          # (dept, system, user) for every fake LLM call
FAIL = {"on": False}
NOTE = {"text": "note from specialist"}
VERIFY = {"text": "YES - they cannot both hold"}
BRIEF = {"text": "OPTION A: x\nRECOMMENDATION: OPTION A - y"}

def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    sysm, usr = messages[0]["content"], messages[-1]["content"]
    users.append((dept, sysm, usr))
    if FAIL["on"] and "requirements analyst" in sysm:
        raise RuntimeError("boom")
    if "strict logic checker" in sysm:
        return VERIFY["text"]
    if dept == "dev":
        return "### FILE: a.py\n```python\nassert 1 == 1\n```"
    if dept == "qa":
        return "PASS\n1. ok"
    if dept == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    if dept == "research" and "Research specialist" in sysm:
        return NOTE["text"] if "conflict spotter" in sysm else "note from specialist"
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

from handoff import Handoff
real_dev_step = pipeline.dev_step
FLAGGED = "### FILE: a.py\n" + chr(96) * 3 + "python\nimport socket\nassert 1 == 1\nprint('ok')\n" + chr(96) * 3
pipeline.dev_step = lambda h: Handoff(goal=h.goal, from_dept="dev", to_dept="qa", deliverable=FLAGGED)

asked.clear()
human.ask_human = lambda kind, dept, question, options=None: (asked.append((kind, question)) or ("run in sandbox" if kind == "approval" else "go with A"))
res = pipeline.run("demo", auto=True)
check("flagged code: owner asked, sandbox run, pipeline finishes", any(k == "approval" for k, q in asked) and res.status == "ok")

asked.clear()
s = len(users)
human.ask_human = lambda kind, dept, question, options=None: (asked.append((kind, question)) or "abort")
res = pipeline.run("demo", auto=True)
check("flagged code: owner declines -> run stops", res.status == "failed" and any(k == "approval" for k, q in asked))
check("flagged code: QA never saw unexecuted code", not any(u[0] == "qa" for u in users[s:]))
pipeline.dev_step = real_dev_step

import json, os, tempfile
import owner, runstats

runstats.R.by.clear()
runstats.R.note("groq", "dev", 120)
runstats.R.note("gemini", "dev", 30)
runstats.R.note("gemini", "qa", 50)
sm = runstats.R.summary()
check("run report totals calls and tokens", "api calls: 3" in sm and "tokens: 200" in sm and "dev: 2 calls, 150 tokens" in sm)
runstats.R.by.clear()  # keep the exit-time report quiet

real_owner_path = owner.PATH
with tempfile.TemporaryDirectory() as td:
    owner.PATH = os.path.join(td, "o.json")
    check("owner defaults: missing file gives empty string", owner.defaults() == "")
    with open(owner.PATH, "w", encoding="utf-8") as fh:
        json.dump({"language": "Python 3.12", "notes": ["small and simple"]}, fh)
    dtext = owner.defaults()
    check("owner defaults: rendered as goal suffix", "OWNER STANDING DEFAULTS" in dtext and "- language: Python 3.12" in dtext and "- small and simple" in dtext)
    s = len(users)
    pipeline.run("demo", auto=True)
    check("owner defaults reach Research", any(u[0] == "research" and "OWNER STANDING DEFAULTS" in u[2] for u in users[s:]))
owner.PATH = real_owner_path

NOTE["text"] = "CONFLICT: dry-run default vs an --execute flag"
VERIFY["text"] = "NO - a default plus a flag satisfies both."
BRIEF["text"] = "OPTION A: x\nOPTION B: y\nRECOMMENDATION: OPTION A - y"
asked.clear()
pipeline.run("demo", auto=True, scale="small")
check("conflict check: a clear NO demotes the CONFLICT, no owner question", not asked)
out = team.notes("g", "small")
check("conflict check: demoted line is marked TENSION", "TENSION: dry-run default" in out and "CONFLICT:" not in out)

VERIFY["text"] = "Hmm, not sure."
asked.clear()
pipeline.run("demo", auto=True, scale="small")
check("conflict check: an unclear answer keeps the CONFLICT and asks", any(k == "decision" for k, q in asked))
VERIFY["text"] = "YES - they cannot both hold"
NOTE["text"] = "note from specialist"

print(f"\n{sum(results)}/{len(results)} passed")
