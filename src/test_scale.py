import llm, pipeline

BT = chr(96) * 3
calls = []
CODE = "### FILE: calc.py\n" + BT + "python\ndef add(a, b):\n    return a + b\n" + BT
TESTS = ("### FILE: test_calc.py\n" + BT + "python\nfrom calc import add\nassert add(1, 2) == 3\n"
         "print('All tests passed.')\n" + BT)
CLASSIC = "### FILE: a.py\n" + BT + "python\nassert 1 == 1\n" + BT

def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    sysm = messages[0]["content"]
    role = ("lead" if "Dev lead" in sysm else "author" if "Dev author" in sysm else "tester" if "Dev tester" in sysm
            else "fixer" if "Dev fixer" in sysm else "auditor" if "constraint auditor" in sysm
            else "prober" if "edge-case prober" in sysm else "spec" if "Research specialist" in sysm else dept)
    calls.append(role)
    if role == "lead":
        return "contract"
    if role == "author":
        return CODE
    if role == "tester":
        return TESTS
    if role in ("auditor", "prober", "spec"):
        return "note"
    if role == "qa":
        return "PASS\n1. ok"
    if role == "research":
        return "OPTION A: x\nRECOMMENDATION: OPTION A - y"
    if role == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    return CLASSIC

llm.ask = fake_ask
llm.RETRY_WAIT = False
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

S = pipeline.split_scale
check("solo turns every team off", S("solo") == ("solo", "solo", "solo"))
check("small turns every team on", S("small") == ("small", "small", "small"))
check("full turns every team on", S("full") == ("full", "full", "full"))
check("small:dev turns only Dev on", S("small:dev") == ("solo", "small", "solo"))
check("full:research+qa turns Research and QA on", S("full:research+qa") == ("full", "solo", "full"))
try:
    S("small:dev+nope")
    check("unknown team raises", False)
except ValueError:
    check("unknown team raises", True)

def roles_for(scale):
    n = len(calls)
    res = pipeline.run("demo", auto=True, scale=scale)
    return res.status, set(calls[n:])

TEAM_ROLES = {"lead", "author", "tester", "fixer", "auditor", "prober", "spec"}
st, r = roles_for("solo")
check("run solo: no team roles at all", st == "ok" and not (TEAM_ROLES & r))
st, r = roles_for("small:dev")
check("run small:dev: only the Dev team works", st == "ok" and {"lead", "author", "tester"} <= r and not ({"auditor", "prober", "spec"} & r))
st, r = roles_for("small:qa")
check("run small:qa: only the QA team works", st == "ok" and {"auditor", "prober"} <= r and not ({"lead", "spec"} & r))
st, r = roles_for("small:research")
check("run small:research: only the Research team works", st == "ok" and "spec" in r and not ({"lead", "auditor", "prober"} & r))

print(f"\n{sum(results)}/{len(results)} passed")
