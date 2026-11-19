import os, subprocess, sys, tempfile
import shipper
from runcheck import DANGEROUS

def check_files(py, timeout=15, force=False):
    allcode = "\n".join(py.values())
    bad = [] if force else sorted(set(m.group(0) for m in DANGEROUS.finditer(allcode)))
    if bad:
        return None, "NOT RUN: flagged for owner review: " + ", ".join(bad)
    try:
        rels = {shipper.safe_rel(k): v for k, v in py.items()}
    except ValueError as e:
        return False, f"RAN WITH ERRORS (exit 1)\n{e}"
    tests = [k for k in rels if os.path.basename(k).startswith("test_") or k.startswith("tests/")]
    targets = tests or list(rels)[:6]
    lines, worst = [], 0
    with tempfile.TemporaryDirectory() as d:
        for rel, code in rels.items():
            path = os.path.join(d, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if k in os.environ}
        env["PYTHONPATH"] = d
        for rel in targets:
            gui = "tkinter" in rels[rel]
            t = 6 if gui else timeout
            cmd = [sys.executable, os.path.join(d, *rel.split("/"))]
            try:
                p = subprocess.run(cmd, cwd=d, env=env, capture_output=True, text=True,
                                   timeout=t, stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                if gui:
                    lines.append(f"[{rel}] GUI stayed open {t}s without crashing (stopped by the check) - OK")
                    continue
                lines.append(f"[{rel}] TIMED OUT after {t}s")
                worst = worst or 124
                continue
            out = ((p.stdout or "") + (p.stderr or "")).strip()[-2000:]
            if p.returncode != 0 and "EOFError: EOF when reading a line" in out:
                lines.append(f"[{rel}] reached an input() prompt (interactive program) - OK")
                continue
            lines.append(f"[{rel}] exit {p.returncode}" + (f"\n{out}" if out else ""))
            worst = worst or p.returncode
    head = "RAN OK (exit 0)" if worst == 0 else f"RAN WITH ERRORS (exit {worst})"
    return worst == 0, head + "\n" + "\n".join(lines)
