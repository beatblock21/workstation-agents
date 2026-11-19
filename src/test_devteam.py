import os
import devlog, devteam, llm, pipeline, shipper
from handoff import Handoff

BT = chr(96) * 3
calls = []  # (role, provider)

CODE = "### FILE: calc.py\n" + BT + "python\ndef add(a, b):\n    return a - b\n" + BT
TESTS = ("### FILE: test_calc.py\n" + BT + "python\nfrom calc import add\nassert add(1, 2) == 3\n"
         "print('All tests passed.')\n" + BT)
EDIT_GOOD = ("ROOT CAUSE: add subtracts\n### EDIT: calc.py\n<<<<<<< SEARCH\n    return a - b\n=======\n"
             "    return a + b\n>>>>>>> REPLACE\n")
EDIT_BAD = ("ROOT CAUSE: x\n### EDIT: calc.py\n<<<<<<< SEARCH\n    return a * b\n=======\n"
            "    return a + b\n>>>>>>> REPLACE\n")
REPORT = "RAN WITH ERRORS (exit 1)\n[test_calc.py] exit 1\nAssertionError: assert 1 == 3"

REPLY = {}
def reset_replies():
    REPLY.clear()
    REPLY.update({"lead": "Files: calc.py, test_calc.py\nadd(a, b) returns a + b", "author": CODE, "tester": TESTS,
                  "fixer": [], "qa": [], "dev": "CLASSIC DEV CALLED"})

def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    sysm = messages[0]["content"]
    role = ("lead" if "Dev lead" in sysm else "author" if "Dev author" in sysm else "tester" if "Dev tester" in sysm
            else "fixer" if "Dev fixer" in sysm else dept)
    calls.append((role, provider))
    if role == "fixer":
        return REPLY["fixer"].pop(0)
    if role == "qa":
        return REPLY["qa"].pop(0) if REPLY["qa"] else "PASS\n1. ok"
    if role == "research":
        return "OPTION A: x\nRECOMMENDATION: OPTION A - y"
    if role == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    return REPLY[role]

llm.ask = fake_ask
llm.RETRY_WAIT = False
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

H = Handoff(goal="g", from_dept="research", to_dept="dev", deliverable="brief")

reset_replies(); devteam.reset()
n = len(calls)
w = devteam.build(H, "g", "small")
files = shipper.parse_files(w.deliverable) if w else {}
check("build: team delivers code + independent tests in 3 calls",
      set(files) == {"calc.py", "test_calc.py"} and [c[0] for c in calls[n:]] == ["lead", "author", "tester"])
check("build: devlog records the contract", "contract:" in devlog.tail(1))

n = len(calls)
check("build: solo makes no calls and returns None", devteam.build(H, "g", "solo") is None and len(calls) == n)

reset_replies(); devteam.reset()
REPLY["tester"] = "no tests today"
check("build: missing test file falls back (None)", devteam.build(H, "g", "small") is None)

reset_replies(); devteam.reset()
real_cap = devteam.CAP["small"]
devteam.CAP["small"] = 2
check("build: call cap below 3 falls back (None)", devteam.build(H, "g", "small") is None)
devteam.CAP["small"] = real_cap

reset_replies(); devteam.reset()
w = devteam.build(H, "g", "small")
REPLY["fixer"] = [EDIT_GOOD]
w2 = devteam.fix("g", w, "FAIL\n1. add is wrong", REPORT, "small")
f2 = shipper.parse_files(w2.deliverable) if w2 else {}
check("fix: anchored edit applied, rest untouched", "return a + b" in f2.get("calc.py", "") and "test_calc.py" in f2)
check("fix: root cause lands in the devlog", "add subtracts" in devlog.tail(1))

reset_replies(); devteam.reset()
w = devteam.build(H, "g", "small")
REPLY["fixer"] = [EDIT_BAD, EDIT_GOOD]
n = len(calls)
w2 = devteam.fix("g", w, "FAIL", REPORT, "small")
check("fix: rejected edit gets one corrective retry",
      w2 is not None and "return a + b" in shipper.parse_files(w2.deliverable)["calc.py"]
      and [c[0] for c in calls[n:]] == ["fixer", "fixer"])

reset_replies(); devteam.reset()
w = devteam.build(H, "g", "small")
REPLY["fixer"] = [EDIT_BAD, EDIT_BAD]
check("fix: nothing applies even after retry -> None (classic fallback)", devteam.fix("g", w, "FAIL", REPORT, "small") is None)

check("signature ignores numbers",
      devteam.signature("x\nAssertionError: 12 != 34") == devteam.signature("x\nAssertionError: 99 != 5"))

reset_replies(); devteam.reset()
w = devteam.build(H, "g", "small")
REPLY["fixer"] = [EDIT_GOOD, EDIT_GOOD]
devteam.fix("g", w, "FAIL", REPORT, "small")
first = calls[-1][1]
devteam.fix("g", w, "FAIL", REPORT, "small")
check("loop breaker: same error again switches provider order", calls[-1][1] != first)

reset_replies(); devteam.reset()
w = devteam.build(H, "g", "small")
devteam._calls = devteam.CAP["small"]
REPLY["fixer"] = [EDIT_GOOD]
check("fix: call cap reached -> None", devteam.fix("g", w, "FAIL", REPORT, "small") is None)

# pipeline integration: QA fails once, the fixer repairs it with an edit, no classic Dev call at all
reset_replies()
REPLY["qa"] = ["FAIL\n1. add is wrong", "PASS\n1. ok"]
REPLY["fixer"] = [EDIT_GOOD]
s = len(calls)
res = pipeline.run("demo", auto=True, scale="small")
roles = [c[0] for c in calls[s:]]
check("pipeline small: team builds, fixer repairs, run finishes ok", res.status == "ok")
check("pipeline small: lead/author/tester/fixer once each, QA twice, classic Dev never",
      roles.count("lead") == 1 and roles.count("author") == 1 and roles.count("tester") == 1
      and roles.count("fixer") == 1 and roles.count("qa") == 2 and "dev" not in roles)
check("pipeline small: devlog file written", os.path.exists(devlog.path()))

# solo stays exactly as before
reset_replies()
REPLY["dev"] = "### FILE: a.py\n" + BT + "python\nassert 1 == 1\n" + BT
s = len(calls)
res = pipeline.run("demo", auto=True)
roles = [c[0] for c in calls[s:]]
check("pipeline solo: classic Dev once, no team roles",
      res.status == "ok" and roles.count("dev") == 1 and not {"lead", "author", "tester", "fixer"} & set(roles))

print(f"\n{sum(results)}/{len(results)} passed")
