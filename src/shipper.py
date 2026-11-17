import os, re, subprocess
from handoff import ROOT
import human

FILE_RE = re.compile(r"^#{2,4}[ \t]*FILE:[ \t]*`?([^\n`]+?)`?[ \t]*\n+(`{3,})[^\n]*\n(.*?)\n\2[ \t]*$", re.M | re.S)
SECRET = re.compile(r"(gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|sk-or-[A-Za-z0-9\-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")
URL_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+?(\.git)?$")

def parse_files(text):
    return {m.group(1).strip(): m.group(3) for m in FILE_RE.finditer(text)}

def safe_rel(path):
    p = path.replace("\\", "/").lstrip("/")
    parts = p.split("/")
    if not p or ".." in parts or ".git" in parts or ":" in p:
        raise ValueError(f"unsafe path: {path}")
    return p

def check_secrets(rel, content):
    base = os.path.basename(rel)
    if base.startswith(".env") and not base.endswith(".example"):
        raise ValueError(f"refusing to ship env file: {rel}")
    if SECRET.search(content):
        raise ValueError(f"possible API key in {rel}; refusing to ship")

def git(args, cwd):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()

def prepare_clone(repo_url):
    name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
    base = os.path.abspath(os.path.join(ROOT, "..", "ships"))
    os.makedirs(base, exist_ok=True)
    dest = os.path.join(base, name)
    if not os.path.isdir(os.path.join(dest, ".git")):
        rc, out = git(["clone", repo_url, dest], base)
        if rc:
            raise RuntimeError("clone failed: " + out)
    else:
        git(["pull", "--ff-only"], dest)
    rc, _ = git(["rev-parse", "--verify", "HEAD"], dest)
    if rc != 0:  # empty repo: make sure the first branch is main
        git(["symbolic-ref", "HEAD", "refs/heads/main"], dest)
    return dest

def ship(deliverable, shipping_text, repo_url):
    if not URL_RE.match(repo_url):
        raise ValueError("repo must look like https://github.com/owner/name.git")
    files = parse_files(deliverable)
    extra = parse_files(shipping_text)
    if "README.md" in extra and "README.md" not in files:
        files["README.md"] = extra["README.md"]
    m = re.search(r"^COMMIT:\s*(.+)$", shipping_text, re.M)
    msg = (m.group(1).strip() if m else "Add project built by workstation-agents")[:200]
    if not files:
        raise RuntimeError("no '### FILE:' blocks found in Dev output; nothing to ship")
    clean = {}
    for k, v in files.items():
        rel = safe_rel(k)
        check_secrets(rel, v)
        clean[rel] = v
    dest = prepare_clone(repo_url)
    print(f"\nShipping to {repo_url}\nLocal clone: {dest}\nCommit message: {msg}\nFiles:")
    for rel, v in clean.items():
        print(f"  {rel}  ({len(v.splitlines())} lines)")
    ans = human.ask_human("approval", "shipping", "Commit and push these files?", ["push", "cancel"])
    human.log_decision({"kind": "approval", "dept": "shipping", "question": f"push to {repo_url}: {', '.join(clean)}", "answer": ans})
    if ans != "push":
        print("Cancelled. Nothing was written.")
        return False
    for rel, v in clean.items():
        path = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(v.rstrip("\n") + "\n")
    git(["add", "--"] + list(clean), dest)
    rc, out = git(["commit", "-m", msg], dest)
    print(out)
    rc, out = git(["push", "-u", "origin", "main"], dest)
    print(out)
    if rc:
        raise RuntimeError("push failed (see output above)")
    return True
