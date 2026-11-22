"""Run every offline suite. Add --live to include chaos.py (one real API call).
Usage: python src\\test_all.py [--live]    Exit code 0 only if every suite is clean."""
import os, re, subprocess, sys, time

SRC = os.path.dirname(os.path.abspath(__file__))
SUITES = ["test_team", "test_resume", "test_runcheck", "test_shipper", "test_edits", "test_devteam", "test_qateam", "test_bench", "test_bench_hard", "test_scale", "test_projectmap", "test_iterate"]
LIVE = ["chaos"]
BAD_WORDS = ("ALLOWED?!", "NOT CAUGHT")


def judge(out, rc):
    problems = []
    if rc != 0:
        problems.append(f"exit code {rc}")
    if re.search(r"(?m)^FAIL", out):
        problems.append("a FAIL line")
    for w in BAD_WORDS:
        if w in out:
            problems.append(w)
    for m in re.finditer(r"(?m)^[A-Za-z][^:\n]*: False[ \t]*$", out):
        problems.append(m.group(0).strip())
    m = re.search(r"(\d+)/(\d+) passed", out)
    if m and m.group(1) != m.group(2):
        problems.append(f"{m.group(1)}/{m.group(2)} passed")
    return problems, (m.group(0) if m else "")


def run_suite(name):
    t = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, os.path.join(SRC, name + ".py")], cwd=SRC, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    problems, counts = judge(out, p.returncode)
    return problems, counts, out, time.time() - t


def main():
    live = "--live" in sys.argv
    names = SUITES + (LIVE if live else [])
    bad = 0
    for n in names:
        problems, counts, out, secs = run_suite(n)
        head = "FAIL" if problems else "ok  "
        print(f"{head} {n:<14} {counts:<14} {secs:5.1f}s" + (f"  <- {'; '.join(problems)}" if problems else ""))
        if problems:
            bad += 1
            print("\n".join("     | " + line for line in out.strip().splitlines()[-12:]))
    if bad:
        print(f"{bad} suite(s) failed")
    else:
        print(f"ALL OK ({len(names)} suites)" + ("" if live else "; add --live to include chaos"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
