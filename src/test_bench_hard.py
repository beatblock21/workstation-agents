import bench, bench_goals

results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

DUR_REF = r"""import re

def parse_duration(text):
    m = re.fullmatch(r"\s*(?:(\d+)d)?\s*(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?\s*", text, re.I)
    if not m or not any(g is not None for g in m.groups()):
        raise ValueError("bad duration")
    d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s
"""
DUR_BAD = r"""import re

def parse_duration(text):
    total = 0
    for n, u in re.findall(r"(\d+)\s*([dhms])", text.lower()):
        total += int(n) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u]
    return total
"""

CSV_REF = r"""def parse_line(line):
    fields, cur, i, n = [], [], 0, len(line)
    in_q = False
    while i < n:
        c = line[i]
        if in_q:
            if c == '"':
                if i + 1 < n and line[i + 1] == '"':
                    cur.append('"')
                    i += 1
                else:
                    in_q = False
            else:
                cur.append(c)
        elif c == '"':
            in_q = True
        elif c == ",":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    if in_q:
        raise ValueError("unterminated quote")
    fields.append("".join(cur))
    return fields
"""
CSV_BAD = 'def parse_line(line):\n    return line.split(",")\n'

check("new goals are registered", "duration" in bench_goals.GOALS and "csv" in bench_goals.GOALS)

p, f, d = bench.grade_files("duration", {"duration.py": DUR_REF, "test_x.py": "assert False"})
check("hidden duration: correct solution passes all 14 checks", f == 0 and p == 14)
p, f, d = bench.grade_files("duration", {"duration.py": DUR_BAD})
check("hidden duration: lenient solution is caught", f >= 1)

p, f, d = bench.grade_files("csv", {"csvline.py": CSV_REF, "test_x.py": "assert False"})
check("hidden csv: correct solution passes all 11 checks", f == 0 and p == 11)
p, f, d = bench.grade_files("csv", {"csvline.py": CSV_BAD})
check("hidden csv: naive split is caught", f >= 1)

print(f"\n{sum(results)}/{len(results)} passed")
