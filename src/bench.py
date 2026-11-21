"""Benchmark the pipeline: fixed goals x scales, every owner prompt answered automatically, results graded by
hidden acceptance tests that the models never see (not by the tests the Dev team wrote for itself).
Usage: python src\\bench.py [--goals slugify,lru,rename] [--scales solo,small] [--repeat 1]
It spends free-tier calls and takes a while. Per-run logs: state\\bench-<stamp>-<goal>-<scale>.local.log,
summary: state\\bench-<stamp>.local.json."""
import contextlib, io, json, os, re, sys, time
import bench_goals, bench_goals_hard, edits, human, pipeline, runcheck, runstats, shipper
from handoff import ROOT


def auto_human(kind, dept, question, options=None):
    """Unattended answers: let Research decide, never ship, never run flagged code, give up on a QA/Dev dispute."""
    if not options:
        return "use your best judgment"
    for o in options:
        if o.startswith("let Research"):
            return o
    return "abort" if "abort" in options else options[-1]


def grade_files(name, files):
    """Run the hidden acceptance test for goal `name` against delivered files -> (passed, failed, detail)."""
    code = {k: v for k, v in files.items()
            if not (os.path.basename(k).startswith("test_") or k.startswith("tests/"))}
    if not code:
        return 0, 0, "no code delivered"
    ok, rep = runcheck.check(edits.to_deliverable({**code, "test_hidden.py": bench_goals.GOALS[name]["hidden"]}))
    if ok is None:
        return 0, 0, "not run: " + rep.splitlines()[0]
    passed = len(re.findall(r"(?m)^CHECK PASS: ", rep))
    fails = re.findall(r"(?m)^CHECK FAIL: (.+)$", rep)
    if not passed and not fails:
        return 0, 0, "hidden test crashed: " + rep[-300:].replace("\n", " | ")
    return passed, len(fails), "; ".join(f[:80] for f in fails)


def delivered_files(out):
    """The code files of a finished run, read back from the result file the pipeline saved."""
    m = re.search(r"Result saved: (.+)", out)
    if not m:
        return {}
    try:
        with open(m.group(1).strip(), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return {}
    d = re.search(r"# Deliverable\n(.*?)\n\n# QA\n", text, re.S)
    return shipper.parse_files(d.group(1)) if d else {}


def run_case(name, goal, scale, stamp):
    runstats.R.by.clear()
    runstats.R.qa_fails = 0
    t0 = time.time()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            res = pipeline.run(goal, auto=True, scale=scale)
        status = res.status
    except Exception as e:
        status = f"crash: {type(e).__name__}: {e}"[:100]
    out = buf.getvalue()
    secs = time.time() - t0
    calls = sum(d["calls"] for d in runstats.R.by.values())
    tokens = sum(d["tokens"] for d in runstats.R.by.values())
    files = delivered_files(out)
    if files:
        passed, failed, note = grade_files(name, files)
    else:
        passed, failed, note = 0, 0, "nothing delivered"
    log = os.path.join(ROOT, "state", f"bench-{stamp}-{name}-{scale}.local.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write(out)
    return {"goal": name, "scale": scale, "status": status, "calls": calls, "tokens": tokens, "secs": round(secs),
            "qa_fails": runstats.R.qa_fails, "passed": passed, "failed": failed, "note": note, "log": log}


def main(argv):
    def opt(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else default
    goals = opt("--goals", ",".join(bench_goals.GOALS)).split(",")
    scales = opt("--scales", "solo,small").split(",")
    repeat = int(opt("--repeat", "1"))
    for g in goals:
        if g not in bench_goals.GOALS:
            sys.exit(f"unknown goal {g!r}; choose from {', '.join(bench_goals.GOALS)}")
    human.ask_human = auto_human
    human.log_decision = lambda rec: None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    rows = []
    for g in goals:
        for _ in range(repeat):
            for s in scales:
                print(f"running {g} / {s} ...", flush=True)
                row = run_case(g, bench_goals.GOALS[g]["goal"], s, stamp)
                rows.append(row)
                total = row["passed"] + row["failed"]
                print(f"  {row['status']:<8} calls {row['calls']:>3}  tokens {row['tokens']:>6}  {row['secs']:>4}s  "
                      f"QA fails {row['qa_fails']}  hidden {row['passed']}/{total}  {row['note'][:70]}", flush=True)
    print("\n=== SUMMARY ===")
    for s in scales:
        rs = [r for r in rows if r["scale"] == s]
        if not rs:
            continue
        ok = sum(1 for r in rs if r["status"] == "ok")
        hp = sum(r["passed"] for r in rs)
        ht = sum(r["passed"] + r["failed"] for r in rs)
        full = sum(1 for r in rs if r["status"] == "ok" and r["failed"] == 0 and r["passed"] > 0)
        print(f"{s:<6} runs {len(rs)} | finished {ok} | fully correct {full} | hidden checks {hp}/{ht} | "
              f"avg calls {sum(r['calls'] for r in rs) / len(rs):.1f} | avg tokens {sum(r['tokens'] for r in rs) / len(rs):.0f}")
    path = os.path.join(ROOT, "state", f"bench-{stamp}.local.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)
    print("saved:", path)
    runstats.R.by.clear()  # keep the exit-time run report quiet


if __name__ == "__main__":
    main(sys.argv[1:])
