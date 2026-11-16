import os, re, subprocess, sys, tempfile

DANGEROUS = re.compile(r"\b(os\.remove|os\.unlink|os\.rmdir|os\.system|shutil\.rmtree|shutil\.move|rmtree|removedirs|subprocess|socket|requests|urllib|http\.client|ftplib|smtplib|eval|exec|__import__|ctypes|winreg)\b|open\([^)]*['\"][wax]")

def blocks(text):
    return [b.strip("\n") for b in re.findall(r"```(?:python|py)\s*\n(.*?)```", text, re.S | re.I)]

def check(text, timeout=15):
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
