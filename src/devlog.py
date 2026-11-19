"""Running task log of the Dev team for the current run: state/devlog-<run id>.local.md.
Each entry records the attempt, files, execution head, error line, root cause and edit results,
so the fixer can trace a problem instead of repeating a failed approach."""
import os, re, time
from handoff import ROOT

_path = None
_sigs = []
_n = 0
_fresh = True


def reset():
    global _path, _sigs, _n, _fresh
    _path, _sigs, _n, _fresh = None, [], 0, True


def path():
    global _path
    if _path is None:
        import journal
        if journal.J.path:
            rid = os.path.basename(journal.J.path)[len("run-"):-len(".local.json")]
        else:
            rid = time.strftime("%Y%m%d-%H%M%S")
        _path = os.path.join(ROOT, "state", f"devlog-{rid}.local.md")
    return _path


def add(role, kind, files=None, execution=None, error=None, root_cause=None, edits=None, note=None):
    global _n, _fresh
    _n += 1
    lines = [f"## {_n}. {kind} ({role}) {time.strftime('%H:%M:%S')}"]
    if files:
        lines.append("files: " + ", ".join(files))
    if execution:
        lines.append("execution: " + execution)
    if error:
        lines.append("error: " + error)
    if root_cause:
        lines.append("root cause: " + root_cause)
    if edits:
        lines.append("edits: " + edits)
    if note:
        lines.append(note)
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    # first write of a run truncates, so a --resume replay rewrites the same log instead of duplicating it
    with open(path(), "w" if _fresh else "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n\n")
    _fresh = False


def tail(n=3):
    try:
        with open(path(), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    parts = [p for p in re.split(r"(?m)^(?=## )", text) if p.strip()]
    return "".join(parts[-n:]).strip()


def repeats(sig):
    """How many consecutive earlier attempts ended with this same error signature."""
    n = 0
    for s in reversed(_sigs):
        if s != sig:
            break
        n += 1
    return n


def note_sig(sig):
    _sigs.append(sig)
