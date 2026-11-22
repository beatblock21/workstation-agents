import os, tempfile
import edits, iterate, llm, projectmap, shipper
from handoff import Handoff

BT = chr(96) * 3
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

FILES = {"inv.py": "class Inv:\n    def __init__(self):\n        self.d = {}\n",
         "test_inv.py": "from inv import Inv\n\ndef test_new():\n    assert Inv().d == {}\n"}
H = Handoff(goal="g", from_dept="research", to_dept="dev", deliverable="brief")

GOOD = ("PLAN: inv.py add count\n### EDIT: inv.py\n<<<<<<< SEARCH\n        self.d = {}\n=======\n        self.d = {}\n\n"
        "    def count(self):\n        return len(self.d)\n>>>>>>> REPLACE\n### FILE: extra.py\n" + BT + "python\nX = 1\n" + BT + "\n")
BAD = ("PLAN: x\n### EDIT: inv.py\n<<<<<<< SEARCH\n        self.dd = {}\n=======\n        self.d = {1: 1}\n>>>>>>> REPLACE\n")
FIX = ("### EDIT: inv.py\n<<<<<<< SEARCH\n        self.d = {}\n=======\n        self.d = {}\n\n"
       "    def count(self):\n        return len(self.d)\n>>>>>>> REPLACE\n")

REPLIES, SEEN = [], []
def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    SEEN.append(messages[-1]["content"])
    return REPLIES.pop(0)
llm.ask = fake_ask
llm.RETRY_WAIT = False

with tempfile.TemporaryDirectory() as d:
    for rel, text in FILES.items():
        with open(os.path.join(d, rel), "w", encoding="utf-8") as f:
            f.write(text)
    files, ctx = iterate.prepare(d, "add a count method to inv")
    check("prepare: loads the project and builds map plus relevant files",
          set(files) == set(FILES) and "PROJECT MAP" in ctx and "RELEVANT FILES" in ctx and "### FILE: inv.py" in ctx)

REPLIES[:] = [GOOD]
nh = iterate.edit_step(H, "add count", FILES, "ctx")
out = shipper.parse_files(nh.deliverable)
check("edit_step: edit applied and new file added", nh.status == "ok" and "def count" in out["inv.py"] and out.get("extra.py") == "X = 1")
check("edit_step: untouched files stay exactly as they were", out["test_inv.py"] == FILES["test_inv.py"].rstrip("\n"))
check("edit_step: whole project comes back (so every test can run)", set(out) == {"inv.py", "test_inv.py", "extra.py"})

REPLIES[:] = [BAD, FIX]
SEEN.clear()
nh = iterate.edit_step(H, "add count", FILES, "ctx")
check("edit_step: rejected edit gets one corrective retry that lands",
      nh.status == "ok" and "def count" in shipper.parse_files(nh.deliverable)["inv.py"] and len(SEEN) == 2
      and "PARTLY FAILED" in SEEN[1])

REPLIES[:] = [BAD, BAD]
nh = iterate.edit_step(H, "add count", FILES, "ctx")
check("edit_step: nothing applicable -> failed handoff", nh.status == "failed" and nh.deliverable.startswith("ERROR"))

REPLIES[:] = ["### FILE: ../evil.py\n" + BT + "python\nX = 1\n" + BT + "\n"]
nh = iterate.edit_step(H, "add count", FILES, "ctx")
check("edit_step: unsafe path -> failed handoff", nh.status == "failed")

REPLIES[:] = ["### FILE: inv.py\n" + BT + "python\nclass Inv:\n    pass\n" + BT + "\n"]
nh = iterate.edit_step(H, "rewrite", FILES, "ctx")
check("edit_step: a whole-file replacement is accepted",
      nh.status == "ok" and shipper.parse_files(nh.deliverable)["inv.py"] == "class Inv:\n    pass")

with tempfile.TemporaryDirectory() as d:
    written = iterate.save(d, edits.to_deliverable(FILES))
    check("save: writes the files and load_dir reads the same project back",
          sorted(written) == sorted(FILES) and projectmap.load_dir(d) == {k: v.rstrip("\n") + "\n" for k, v in FILES.items()})
    try:
        iterate.save(d, "### FILE: ../x.py\n" + BT + "python\nx = 1\n" + BT + "\n")
        check("save: unsafe path raises", False)
    except ValueError:
        check("save: unsafe path raises", True)

print(f"\n{sum(results)}/{len(results)} passed")
