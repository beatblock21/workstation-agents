import os, tempfile
import projectmap as pm

results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

INV = '''"""Inventory core."""
LIMIT = 5

class Inventory(dict):
    """Stock levels by item name."""
    def add_item(self, name: str, qty: int = 1) -> None:
        """Add stock."""
        self[name] = self.get(name, 0) + qty

    async def sync(self, *, force=False):
        pass

def total(inv) -> int:
    return sum(inv.values())
'''
STO = 'import json\n\ndef save_json(inv, path):\n    """Write the inventory as JSON."""\n    pass\n\ndef load_json(path):\n    pass\n'
ALR = 'def low_stock(inv, limit=3):\n    return [k for k, v in inv.items() if v < limit]\n'
TST = "def test_add():\n    pass\n\ndef test_total():\n    pass\n\ndef helper():\n    pass\n"
FILES = {"inventory.py": INV, "storage.py": STO, "alerts.py": ALR, "test_storage.py": TST,
         "test_inventory.py": TST, "README.md": "# Inv\nnotes\n", "broken.py": "def (:\n"}

m = pm.build_map(FILES)
check("map: class, bases, method signature with annotations and defaults, docstring",
      "class Inventory(dict)  # Stock levels by item name." in m
      and "def add_item(self, name: str, qty: int" in m and "-> None  # Add stock." in m)
check("map: async method with keyword-only argument", "async def sync(self, *, force=False)" in m)
check("map: function with return annotation, module docstring and names",
      "def total(inv) -> int" in m and "Inventory core." in m and "names: LIMIT" in m)
check("map: test files list only test function names", "tests: test_add, test_total" in m and "helper" not in m)
check("map: unparseable file is reported, others still mapped", "broken.py (1 lines) UNPARSEABLE" in m and "def low_stock(inv, limit=3)" in m)
check("map: non-python file is listed with its line count", "README.md (2 lines)" in m)

with tempfile.TemporaryDirectory() as d:
    for rel, text in {"pkg/mod.py": "x = 1\n", ".hidden/h.py": "x = 2\n", "__pycache__/c.py": "x = 3\n",
                      "notes.md": "hi\n", "data.bin": "zz"}.items():
        full = os.path.join(d, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
    check("load_dir: text files only, hidden and cache folders skipped", sorted(pm.load_dir(d)) == ["notes.md", "pkg/mod.py"])

sel = pm.select_files(FILES, "Add JSON export to storage", max_chars=400)
check("select: module named in the request is chosen with its test", "storage.py" in sel and "test_storage.py" in sel)
check("select: unrelated module is left out", "alerts.py" not in sel)

vague = pm.select_files({"big.py": "x" * 500, "small.py": "y = 1\n"}, "make it better", max_chars=100)
check("select: vague request falls back to the smallest files that fit", "small.py" in vague and "big.py" not in vague)

short = pm.select_files({"a.py": "def go():\n    pass\n", "report.py": "def make_report():\n    pass\n"}, "add a header to the report")
check("select: a short file name such as a.py does not match every request", "report.py" in short and "a.py" not in short)

print(f"\n{sum(results)}/{len(results)} passed")
