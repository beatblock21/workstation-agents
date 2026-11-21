"""Fixed benchmark goals with hidden acceptance tests that no model ever sees.
Each hidden test prints 'CHECK PASS: name' or 'CHECK FAIL: name: reason' per check and exits 1 if any failed.
The goals pin exact file and function names so the hidden tests can import what gets delivered."""

_HEAD = r'''
import sys
failed = 0
def check(name, fn):
    global failed
    try:
        fn()
        print("CHECK PASS: " + name)
    except BaseException as e:
        failed += 1
        print("CHECK FAIL: " + name + ": " + repr(e)[:150])
def eq(a, b):
    assert a == b, f"{a!r} != {b!r}"
'''
_TAIL = "\nsys.exit(1 if failed else 0)\n"

_SLUGIFY = r'''
try:
    from slugify import slugify
except BaseException as e:
    print("CHECK FAIL: import: " + repr(e)[:150])
    sys.exit(1)
check("basic", lambda: eq(slugify("Hello, World!"), "hello-world"))
check("runs collapse", lambda: eq(slugify("a   b---c"), "a-b-c"))
check("ends stripped", lambda: eq(slugify("  --Hi--  "), "hi"))
check("empty", lambda: eq(slugify(""), ""))
check("only symbols", lambda: eq(slugify("!!!"), ""))
check("digits kept", lambda: eq(slugify("Python 3.12 rocks"), "python-3-12-rocks"))
'''

_LRU = r'''
try:
    from lru import LRUCache
except BaseException as e:
    print("CHECK FAIL: import: " + repr(e)[:150])
    sys.exit(1)
def t_basic():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    eq(c.get("a"), 1)
def t_missing():
    eq(LRUCache(1).get("x"), None)
def t_evict():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")
    c.put("c", 3)
    eq(c.get("b"), None)
    eq(c.get("a"), 1)
    eq(c.get("c"), 3)
def t_update():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)
    c.put("c", 3)
    eq(c.get("a"), 10)
    eq(c.get("b"), None)
def t_cap1():
    c = LRUCache(1)
    c.put("a", 1)
    c.put("b", 2)
    eq(c.get("a"), None)
    eq(c.get("b"), 2)
check("get after put", t_basic)
check("missing key gives None", t_missing)
check("least recently used is evicted", t_evict)
check("updating a key refreshes it", t_update)
check("capacity one", t_cap1)
'''

_RENAME = r'''
import os, pathlib, runpy, tempfile, time
TS = time.mktime((2022, 1, 1, 12, 0, 0, 0, 0, -1))
def make(names):
    d = tempfile.mkdtemp()
    for n in names:
        p = pathlib.Path(d) / n
        p.write_text("x")
        os.utime(str(p), (TS, TS))
    return d
def run_cli(folder, execute):
    old = sys.argv
    sys.argv = ["rename_by_date.py", folder] + (["--execute"] if execute else [])
    try:
        runpy.run_path("rename_by_date.py", run_name="__main__")
    except SystemExit:
        pass
    finally:
        sys.argv = old
def listing(d):
    return sorted(os.listdir(d))
def t_dry():
    d = make(["a.txt", "b.txt"])
    run_cli(d, False)
    eq(listing(d), ["a.txt", "b.txt"])
def t_exec():
    d = make(["a.txt", "b.txt"])
    run_cli(d, True)
    eq(listing(d), ["2022-01-01_a.txt", "2022-01-01_b.txt"])
def t_twice():
    d = make(["a.txt"])
    run_cli(d, True)
    run_cli(d, True)
    eq(listing(d), ["2022-01-01_a.txt"])
def t_prefixed():
    d = make(["2020-05-05_x.txt", "y.txt"])
    run_cli(d, True)
    eq(listing(d), ["2020-05-05_x.txt", "2022-01-01_y.txt"])
check("dry run changes nothing", t_dry)
check("execute prefixes the date", t_exec)
check("second execute is a no-op", t_twice)
check("already prefixed file is left alone", t_prefixed)
'''

GOALS = {
    "slugify": {
        "goal": ("Write a Python module slugify.py with a function slugify(text) that lowercases the text, replaces every run of "
                 "non-alphanumeric characters with a single hyphen, and strips hyphens from both ends. Standard library only. "
                 "Put plain-assert tests in a separate test file."),
        "hidden": _HEAD + _SLUGIFY + _TAIL,
    },
    "lru": {
        "goal": ("Write a Python module lru.py with a class LRUCache(capacity). get(key) returns the value, or None when the key is "
                 "missing, and marks the key as most recently used. put(key, value) stores the value, marks the key as most recently "
                 "used, and evicts the least recently used key when the cache is over capacity. Standard library only. "
                 "Put plain-assert tests in a separate test file."),
        "hidden": _HEAD + _LRU + _TAIL,
    },
    "rename": {
        "goal": ("Build a command line tool whose entry point is the file rename_by_date.py (it may import other modules). "
                 "Usage: python rename_by_date.py FOLDER [--execute]. It prefixes every file in FOLDER (not subfolders) with the "
                 "file's modification date as YYYY-MM-DD_ , for example report.txt becomes 2022-01-01_report.txt. Without --execute "
                 "it only prints what it would do and changes nothing. Running it again must never rename a file that already has "
                 "a YYYY-MM-DD_ prefix. Standard library only. Put plain-assert tests in a separate test file."),
        "hidden": _HEAD + _RENAME + _TAIL,
    },
}
