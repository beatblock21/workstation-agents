import bench, bench_goals, llm

BT = chr(96) * 3
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

SLUG_REF = 'import re\n\ndef slugify(text):\n    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")\n'
SLUG_BAD = "def slugify(text):\n    return text.lower()\n"

LRU_REF = r'''from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.d = OrderedDict()

    def get(self, key):
        if key not in self.d:
            return None
        self.d.move_to_end(key)
        return self.d[key]

    def put(self, key, value):
        if key in self.d:
            self.d.move_to_end(key)
        self.d[key] = value
        if len(self.d) > self.cap:
            self.d.popitem(last=False)
'''
LRU_BAD = r'''class LRUCache:
    def __init__(self, capacity):
        self.d = {}

    def get(self, key):
        return self.d.get(key)

    def put(self, key, value):
        self.d[key] = value
'''

RENAME_REF = r'''import argparse, os, re
from datetime import datetime

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    for name in sorted(os.listdir(a.folder)):
        p = os.path.join(a.folder, name)
        if not os.path.isfile(p) or re.match(r"\d{4}-\d{2}-\d{2}_", name):
            continue
        d = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d")
        new = os.path.join(a.folder, d + "_" + name)
        print(("renaming " if a.execute else "would rename ") + name + " -> " + os.path.basename(new))
        if a.execute:
            os.rename(p, new)

if __name__ == "__main__":
    main()
'''
RENAME_BAD = RENAME_REF.replace(' or re.match(r"\\d{4}-\\d{2}-\\d{2}_", name)', "")

# the hidden tests themselves must pass on a correct solution and catch a broken one
for goal, ref, bad, filename, n in (("slugify", SLUG_REF, SLUG_BAD, "slugify.py", 6),
                                    ("lru", LRU_REF, LRU_BAD, "lru.py", 5),
                                    ("rename", RENAME_REF, RENAME_BAD, "rename_by_date.py", 4)):
    p, f, d = bench.grade_files(goal, {filename: ref, "test_x.py": "assert False"})
    check(f"hidden {goal}: correct solution passes all {n} checks (delivered tests ignored)", f == 0 and p == n)
    p, f, d = bench.grade_files(goal, {filename: bad})
    check(f"hidden {goal}: broken solution is caught", f >= 1)

check("grade: flagged code is reported as not run",
      bench.grade_files("slugify", {"slugify.py": "import socket\n" + SLUG_REF})[2].startswith("not run"))
check("grade: tests only means no code delivered", bench.grade_files("slugify", {"test_x.py": "x = 1"}) == (0, 0, "no code delivered"))

check("auto answers: decision, dispute, approval, free text",
      bench.auto_human("decision", "research", "q", ["A: x", "B: y", "let Research decide"]) == "let Research decide"
      and bench.auto_human("dispute", "qa vs dev", "q", ["ship anyway", "send back to dev once more", "abort"]) == "abort"
      and bench.auto_human("approval", "qa", "q", ["run in sandbox", "abort"]) == "abort"
      and bench.auto_human("dispute", "research", "q") == "use your best judgment")

# end to end through the real pipeline with a fake model (solo scale)
CASE = {"code": SLUG_REF, "test": "from slugify import slugify\nassert slugify('ab') == 'ab'\nprint('ok')"}
def fake_ask(provider, messages, max_tokens=300, dept="misc"):
    if dept == "dev":
        return ("### FILE: slugify.py\n" + BT + "python\n" + CASE["code"] + BT + "\n\n### FILE: test_slugify.py\n"
                + BT + "python\n" + CASE["test"] + "\n" + BT)
    if dept == "qa":
        return "PASS\n1. ok"
    if dept == "shipping":
        return "COMMIT: demo\n### FILE: README.md\n# Demo"
    return "OPTION A: x\nRECOMMENDATION: OPTION A - y"
llm.ask = fake_ask
llm.RETRY_WAIT = False

row = bench.run_case("slugify", bench_goals.GOALS["slugify"]["goal"], "solo", "test")
check("run_case: finished run is graded by the hidden test", row["status"] == "ok" and row["passed"] == 6 and row["failed"] == 0)
CASE["code"] = SLUG_BAD
row = bench.run_case("slugify", bench_goals.GOALS["slugify"]["goal"], "solo", "test")
check("run_case: a run that passes its own tests but is wrong is exposed",
      row["status"] == "ok" and row["failed"] >= 1)

print(f"\n{sum(results)}/{len(results)} passed")
