import edits, shipper

BT = chr(96) * 3
results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

def blk(path, search, replace):
    return f"### EDIT: {path}\n<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n"

E1 = blk("a.py", "x = 1", "x = 2")
check("parse: one edit", edits.parse_edits(E1) == [("a.py", "x = 1", "x = 2")])

E2 = (E1 + "<<<<<<< SEARCH\ny = 1\n=======\ny = 2\n>>>>>>> REPLACE\n\n### EDIT: `pkg/b.py`\n"
      + BT + "\n<<<<<<< SEARCH\nz\n=======\nzz\n>>>>>>> REPLACE\n" + BT + "\n")
check("parse: several blocks, several files, fenced, backticked path",
      edits.parse_edits(E2) == [("a.py", "x = 1", "x = 2"), ("a.py", "y = 1", "y = 2"), ("pkg/b.py", "z", "zz")])

new, ok, bad = edits.apply_edits({"a.py": "x = 1\ny = 1\n"}, [("a.py", "x = 1", "x = 2")])
check("apply: exact unique match", new["a.py"] == "x = 2\ny = 1\n" and len(ok) == 1 and not bad)

orig = {"a.py": "def foo():\n    return 1\n"}
new, ok, bad = edits.apply_edits(orig, [("a.py", "def fooo():\n    return 1", "x")])
check("apply: not found is rejected, file untouched, hint given",
      new == orig and len(bad) == 1 and "not found" in bad[0][2] and "closest existing line" in bad[0][2])

new, ok, bad = edits.apply_edits({"a.py": "x = 1\nx = 1\n"}, [("a.py", "x = 1", "x = 2")])
check("apply: ambiguous match is rejected", len(bad) == 1 and "2 places" in bad[0][2] and new["a.py"] == "x = 1\nx = 1\n")

new, ok, bad = edits.apply_edits({"a.py": "if a:   \n    b = 1\n"}, [("a.py", "if a:\n    b = 1", "if a:\n    b = 2")])
check("apply: trailing-whitespace tolerant fallback", new["a.py"] == "if a:\n    b = 2\n" and len(ok) == 1)

new, ok, bad = edits.apply_edits({"a.py": "x = 1\n"}, [("a.py", "x = 1", "x = 2"), ("a.py", "x = 2", "x = 3")])
check("apply: sequential edits on one file", new["a.py"] == "x = 3\n" and len(ok) == 2)

new, ok, bad = edits.apply_edits({"a.py": "x = 1\ny = 1\n"},
                                 [("a.py", "x = 1", "x = 2"), ("a.py", "q = 9", "q = 0"), ("a.py", "y = 1", "y = 2")])
check("apply: partial success keeps good edits and names the bad one",
      new["a.py"] == "x = 2\ny = 2\n" and len(ok) == 2 and len(bad) == 1 and bad[0][0] == 2)

new, ok, bad = edits.apply_edits({"a.py": "a"}, [("../x.py", "a", "b")])
check("apply: unsafe path rejected", len(bad) == 1 and new == {"a.py": "a"})

new, ok, bad = edits.apply_edits({}, [("new.py", "", "print(1)")])
check("apply: empty SEARCH creates a new file", new == {"new.py": "print(1)\n"} and len(ok) == 1)

new, ok, bad = edits.apply_edits({"a.py": "x"}, [("a.py", "", "y")])
check("apply: empty SEARCH on an existing file is rejected", len(bad) == 1 and new == {"a.py": "x"})

new, ok, bad = edits.apply_edits({"a.py": "a\nb\nc\n"}, [("a.py", "b", "")])
check("apply: empty replacement deletes the lines", new["a.py"] == "a\nc\n")

new, ok, bad = edits.apply_edits({"a.py": "def f():\n    return 1\n"}, [("a.py", "    return 1", "    x = 2\n    return x")])
check("apply: multi-line replacement keeps indentation", new["a.py"] == "def f():\n    x = 2\n    return x\n")

files = {"a.py": "print(1)", "README.md": BT + "bash\nrun\n" + BT}
check("to_deliverable round-trips through shipper.parse_files (even with ``` inside)",
      shipper.parse_files(edits.to_deliverable(files)) == files)

d, rep, ok, bad = edits.apply_to_deliverable(edits.to_deliverable({"a.py": "x = 1"}), E1)
check("apply_to_deliverable end to end", shipper.parse_files(d) == {"a.py": "x = 2"} and "1 applied, 0 rejected" in rep)

print(f"\n{sum(results)}/{len(results)} passed")
