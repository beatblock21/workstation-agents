import devlog, devteam, edits, llm, pipeline, qateam
from handoff import Handoff

BT = chr(96) * 3
calls = []  # (role, user text)

CALC = "def add(a, b):\n    return a + b"
TEST = "from calc import add\nassert add(1, 2) == 3\nprint('ok')"
DELIV = edits.to_deliverable({"calc.py": CALC, "test_calc.py": TEST})
WORK = Handoff(goal="g", from_dept="dev", to_dept="qa", deliverable=DELIV)
OK = "RAN OK (exit 0)\n[test_calc.py] exit 0"

PROBE_SRC = (
    "import sys\nfrom calc import add\nfailed = 0\n"
    "def probe(name, fn):\n    global failed\n    try:\n        fn()\n        print('PROBE PASS: ' + name)\n"
    "    except Exception as e:\n        failed += 1\n        print('PROBE FAIL: ' + name + ': ' + str(e))\n"
    "def p_add():\n    assert add(1, 2) == 3\n"
    "def p_zero():\n    assert add(0, 0) == 1, 'zero case'\n"
    "probe('adds', p_add)\nprobe('zero', p_zero)\nprint('PROBES DONE')\nsys.exit(1 if failed else 0)\n")

def as_file(src):
    return "### FILE: test_qa_probe.py\n" + BT + "python\n" + src + BT

REPLY = {}
def reset_replies():
    REPLY.clear()
    REPLY.update({"auditor": "CONSTRAINT: stdlib only - PASS - no imports", "prober": as_file(PROBE_SRC),
                  "reviewer": "TESTS OK"})

def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    sysm, usr = messages[0]["content"], messages[-1]["content"]
    role = ("auditor" if "constraint auditor" in sysm else "prober" if "edge-case prober" in sysm
            else "reviewer" if "test reviewer" in sysm else dept)
    calls.append((role, usr))
    if role in REPLY:
        return REPLY[role]
    if role == "qa":
        return "PASS\n1. ok"
    if role == "research":
        return "OPTION A: x\nRECOMMENDATION: OPTION A - y"
    if role == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    return "CLASSIC DEV CALLED"

llm.ask = fake_ask
llm.RETRY_WAIT = False
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

def roles_since(n):
    return [c[0] for c in calls[n:]]

reset_replies(); qateam.reset()
n = len(calls)
check("solo: no evidence, no calls", qateam.evidence("g", WORK, OK, "solo") == "" and len(calls) == n)

reset_replies(); qateam.reset(); devlog.reset()
n = len(calls)
ev = qateam.evidence("g", WORK, OK, "small")
check("small: auditor then prober, probes run in the sandbox",
      roles_since(n) == ["auditor", "prober"] and "[constraint auditor]" in ev
      and "2 probes ran: 1 passed, 1 failed" in ev and "PROBE FAIL: zero: zero case" in ev)
check("probe file is never part of the deliverable", "test_qa_probe" not in WORK.deliverable and WORK.deliverable == DELIV)

n = len(calls)
ev2 = qateam.evidence("g", WORK, OK, "small")
check("auditor runs once per run, prober every round", roles_since(n) == ["prober"] and "[constraint auditor]" not in ev2)

qateam.reset(); n = len(calls)
check("code that already failed gets no evidence",
      qateam.evidence("g", WORK, "RAN WITH ERRORS (exit 1)\n[x] exit 1", "small") == "" and len(calls) == n)
check("code that was not executed gets no evidence",
      qateam.evidence("g", WORK, "NOT RUN: flagged for owner review: socket", "small") == "" and len(calls) == n)

reset_replies(); qateam.reset(); n = len(calls)
ev = qateam.evidence("g", WORK, OK, "full")
check("full: reviewer added", roles_since(n) == ["auditor", "reviewer", "prober"] and "[test reviewer]" in ev)

qateam.reset(); qateam._calls = qateam.CAP["small"]; n = len(calls)
check("call cap reached: no evidence", qateam.evidence("g", WORK, OK, "small") == "" and len(calls) == n)

reset_replies(); qateam.reset()
REPLY["prober"] = as_file("import socket\nprint('PROBE PASS: x')\n")
check("flagged probe is reported as not run, no prompt", "PROBES NOT RUN" in qateam.evidence("g", WORK, OK, "small"))

reset_replies(); qateam.reset()
REPLY["prober"] = as_file("import no_such_module_xyz\n")
check("crashing probe is marked invalid, not evidence", "PROBES INVALID" in qateam.evidence("g", WORK, OK, "small"))

reset_replies(); qateam.reset()
REPLY["prober"] = "I could not write a probe."
check("no probe file is reported", "no probe file" in qateam.evidence("g", WORK, OK, "small"))

# pipeline integration: the QA lead receives the evidence (Dev team off via cap 0 so the patched single Dev call is used)
reset_replies()
real_cap, real_dev = devteam.CAP["small"], pipeline.dev_step
devteam.CAP["small"] = 0
pipeline.dev_step = lambda h: Handoff(goal=h.goal, from_dept="dev", to_dept="qa", deliverable=DELIV)
n = len(calls)
res = pipeline.run("demo", auto=True, scale="small")
qa_inputs = [c[1] for c in calls[n:] if c[0] == "qa"]
check("pipeline small: QA lead receives the team evidence",
      res.status == "ok" and len(qa_inputs) == 1 and "QA TEAM EVIDENCE" in qa_inputs[0]
      and "PROBE FAIL: zero: zero case" in qa_inputs[0])

n = len(calls)
res = pipeline.run("demo", auto=True)
check("pipeline solo: no QA specialists", res.status == "ok" and not {"auditor", "prober", "reviewer"} & set(roles_since(n)))
pipeline.dev_step, devteam.CAP["small"] = real_dev, real_cap

print(f"\n{sum(results)}/{len(results)} passed")
