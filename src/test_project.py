import os, tempfile
import llm, pipeline, projectmap

BT = chr(96) * 3
calls, seen = [], []
Q = {"editor": [], "fixer": [], "qa": []}

INV = "class Inv:\n    def __init__(self):\n        self.d = {}\n"
TINV = "from inv import Inv\nassert Inv().d == {}\nprint('ok')\n"
EDIT_OK = ("PLAN: inv.py count\n### EDIT: inv.py\n<<<<<<< SEARCH\n        self.d = {}\n=======\n        self.d = {}\n\n"
           "    def count(self):\n        return len(self.d)\n>>>>>>> REPLACE\n### FILE: test_count.py\n" + BT
           + "python\nfrom inv import Inv\nassert Inv().count() == 0\nprint('ok')\n" + BT + "\n")
EDIT_BREAK = "PLAN: x\n### EDIT: inv.py\n<<<<<<< SEARCH\n        self.d = {}\n=======\n        self.d = []\n>>>>>>> REPLACE\n"
FIX_BACK = ("ROOT CAUSE: the change turned the dict into a list\n### EDIT: inv.py\n<<<<<<< SEARCH\n        self.d = []\n"
            "=======\n        self.d = {}\n>>>>>>> REPLACE\n")
EDIT_BAD = "PLAN: x\n### EDIT: inv.py\n<<<<<<< SEARCH\n        self.nothing = 1\n=======\n        self.d = {}\n>>>>>>> REPLACE\n"
CLASSIC = ("### FILE: inv.py\n" + BT + "python\n" + INV + BT + "\n\n### FILE: test_inv.py\n" + BT + "python\n" + TINV + BT + "\n")

def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    sysm, usr = messages[0]["content"], messages[-1]["content"]
    role = "editor" if "Dev editor" in sysm else "fixer" if "Dev fixer" in sysm else dept
    calls.append(role)
    seen.append((role, usr))
    if role in ("editor", "fixer"):
        return Q[role].pop(0)
    if role == "qa":
        return Q["qa"].pop(0) if Q["qa"] else "PASS\n1. ok"
    if role == "dev":
        return CLASSIC
    if role == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    return "OPTION A: x\nRECOMMENDATION: OPTION A - y"

llm.ask = fake_ask
llm.RETRY_WAIT = False
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

def make_project(d, files):
    for rel, text in files.items():
        with open(os.path.join(d, rel), "w", encoding="utf-8") as f:
            f.write(text)

with tempfile.TemporaryDirectory() as d:
    make_project(d, {"inv.py": INV, "test_inv.py": TINV})
    Q.update(editor=[EDIT_OK], fixer=[], qa=[])
    n, s = len(calls), len(seen)
    res = pipeline.run("add a count method to inv", auto=True, project=d)
    files, roles = projectmap.load_dir(d), calls[n:]
    check("project: change applied and saved back into the folder",
          res.status == "ok" and "def count" in files["inv.py"] and "test_count.py" in files)
    check("project: untouched file is unchanged", files["test_inv.py"] == TINV)
    check("project: Research received the project context",
          any(r == "research" and "EXISTING PROJECT (iteration)" in u for r, u in seen[s:]))
    check("project: the editor worked and classic Dev did not", "editor" in roles and "dev" not in roles)

with tempfile.TemporaryDirectory() as d:
    make_project(d, {"inv.py": INV, "test_inv.py": TINV})
    Q.update(editor=[EDIT_BREAK], fixer=[FIX_BACK], qa=["FAIL\n1. broke the existing test"])
    n = len(calls)
    res = pipeline.run("change the storage type", auto=True, project=d)
    files, roles = projectmap.load_dir(d), calls[n:]
    check("project: a change that breaks an existing test is repaired by the fixer, then saved",
          res.status == "ok" and "self.d = {}" in files["inv.py"] and roles.count("fixer") == 1 and "dev" not in roles)

with tempfile.TemporaryDirectory() as d:
    new = os.path.join(d, "new")
    Q.update(editor=[], fixer=[], qa=[])
    n = len(calls)
    res = pipeline.run("build inv", auto=True, project=new)
    files = projectmap.load_dir(new)
    check("project: an empty folder means a normal build whose result is saved into it",
          res.status == "ok" and set(files) == {"inv.py", "test_inv.py"} and "dev" in calls[n:])

with tempfile.TemporaryDirectory() as d:
    make_project(d, {"inv.py": INV, "test_inv.py": TINV})
    Q.update(editor=[EDIT_BAD, EDIT_BAD], fixer=[], qa=[])
    res = pipeline.run("do something", auto=True, project=d)
    check("project: when no edit applies the run fails and the folder is untouched",
          res.status == "failed" and projectmap.load_dir(d) == {"inv.py": INV, "test_inv.py": TINV})

print(f"\n{sum(results)}/{len(results)} passed")
