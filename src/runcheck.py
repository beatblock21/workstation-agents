import os, re, subprocess, sys, tempfile
import shipper

DANGEROUS = re.compile(r"\b(os\.remove|os\.unlink|os\.rmdir|os\.system|shutil\.rmtree|shutil\.move|rmtree|removedirs|subprocess|socket|requests|urllib|http\.client|ftplib|smtplib|eval|exec|__import__|ctypes|winreg)\b|open\([^)]*['\"][wax]")

def blocks(text):
    return [b.strip("\n") for b in re.findall(r"```(?:python|py)\s*\n(.*?)```", text, re.S | re.I)]

def check(text, timeout=15):
    files = shipper.parse_files(text)
    py = {k: v for k, v in files.items() if k.endswith(".py")}
    if py:
        return check_files(py, timeout)
    code = "\n\n".join(blocks(text))
    if not code.strip():
        return None, "NOT RUN: no Python code block found."
    bad = sorted(set(m.group(0) for m in DANGEROUS.finditer(code)))
    if bad:
        return None, "NOT RUN: flagged for owner review: " + ", ".join(bad)
    env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if k in os.environ}
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "check.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            p = subprocess.run([sys.executable, path], cwd=d, env=env,
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, f"TIMED OUT after {timeout}s"
    out = ((p.stdout or "") + (p.stderr or "")).strip()[-1200:]
    if p.returncode == 0:
        return True, "RAN OK (exit 0)\n" + out
    return False, f"RAN WITH ERRORS (exit {p.returncode})\n" + out


def check_files(py, timeout=15):
    allcode = "\n".join(py.values())
    bad = sorted(set(m.group(0) for m in DANGEROUS.finditer(allcode)))
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
            try:
                p = subprocess.run([sys.executable, os.path.join(d, *rel.split("/"))], cwd=d, env=env,
                                   capture_output=True, text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                lines.append(f"[{rel}] TIMED OUT after {timeout}s")
                worst = worst or 124
                continue
            out = ((p.stdout or "") + (p.stderr or "")).strip()[-600:]
            lines.append(f"[{rel}] exit {p.returncode}" + (f"\n{out}" if out else ""))
            worst = worst or p.returncode
    head = "RAN OK (exit 0)" if worst == 0 else f"RAN WITH ERRORS (exit {worst})"
    return worst == 0, head + "\n" + "\n".join(lines)
