"""Iteration mode: change an existing Python project with anchored edits instead of rebuilding it.
prepare() builds the context (project map + the files relevant to the change request), edit_step() asks the Dev editor
for edit blocks and applies them with edits.py, save() writes the result back to the project folder.
The editor's result is the WHOLE updated project as ### FILE blocks, so the execution check runs every test."""
import os, re
import department, devlog, edits, projectmap, shipper
from handoff import Handoff
from llm import chat

EDITOR_PROMPT = (
    "You are the Dev editor. You get a CHANGE REQUEST, a RESEARCH BRIEF, a PROJECT MAP and the RELEVANT FILES of an existing "
    "Python project. Implement the change by editing the existing code, never by rewriting files. Use edit blocks: a line "
    "### EDIT: relative/path, then a line <<<<<<< SEARCH, then the exact existing lines to replace (enough context to match "
    "exactly once), then a line =======, then the replacement lines, then a line >>>>>>> REPLACE. To add a new file use a line "
    "### FILE: relative/path followed by a fenced code block with the full content. Keep every existing behaviour and every "
    "existing test working. Add or extend plain-assert tests for the new behaviour in the project's test files: each test is a "
    "function test_<what>, and the test file ends with a runner that prints 'TEST PASS: <name>' or 'TEST FAIL: <name>: <reason>' "
    "per test, prints All tests passed. only if none failed and calls sys.exit(1) otherwise; if the runner lists the tests "
    "explicitly, add the new tests to that list. Tests must pass on Windows and Linux. Print only plain ASCII characters. "
    "First write one line PLAN: naming the files and functions you will change.")


def prepare(project, request, max_chars=12000):
    """(files, context text) for a change request on a project folder."""
    files = projectmap.load_dir(project)
    ctx = ("EXISTING PROJECT (iteration): the goal is a change request on this code.\n" + projectmap.build_map(files)
           + "\n\nRELEVANT FILES:\n" + edits.to_deliverable(projectmap.select_files(files, request, max_chars)))
    return files, ctx


def _ask(user):
    msgs = [{"role": "system", "content": EDITOR_PROMPT}, {"role": "user", "content": user}]
    mt, text = 4000, ""
    for _ in range(2):
        provider, text = chat(msgs, department.CFG["dev"]["chain"], dept="dev", max_tokens=mt)
        print(f"   [dev:editor] answered via {provider}")
        if "[TRUNCATED" not in text:
            break
        mt *= 2
        print(f"   [dev:editor] output was truncated; retrying with max_tokens={mt}")
    return text


def _apply(files, text):
    """Edit blocks first, then any ### FILE blocks (new files, or whole-file replacements)."""
    new, applied, rejected = edits.apply_edits(files, edits.parse_edits(text))
    for rel, body in shipper.parse_files(text).items():
        new[shipper.safe_rel(rel)] = body
        applied.append((0, rel))
    return new, applied, rejected


def _failed(h, msg):
    nh = Handoff(goal=h.goal, from_dept="dev", to_dept="qa", deliverable="ERROR: " + msg, status="failed")
    nh.save()
    return nh


def edit_step(h, goal, files, ctx):
    """One Dev editor round (with one corrective retry for rejected edits). Returns a Handoff with the whole updated
    project, or a Handoff with status 'failed' when nothing could be applied."""
    user = f"CHANGE REQUEST:\n{goal}\n\nRESEARCH BRIEF:\n{h.deliverable}\n\n{ctx}"
    try:
        out = _ask(user)
        new_files, applied, rejected = _apply(files, out)
        rep = edits.report(applied, rejected)
        if rejected:
            user2 = (f"CHANGE REQUEST:\n{goal}\n\nCURRENT FILES (after the edits that applied):\n{edits.to_deliverable(new_files)}\n\n"
                     f"YOUR PREVIOUS EDITS PARTLY FAILED:\n{rep}\n\nResend ONLY corrected edit blocks for the rejected edits, same format.")
            new_files, applied2, rejected = _apply(new_files, _ask(user2))
            applied = applied + applied2
            rep += "\nRETRY: " + edits.report(applied2, rejected)
    except Exception as e:
        return _failed(h, f"editor failed: {e}")
    m = re.search(r"PLAN:\s*(.+)", out)
    devlog.add("editor", "change", files=sorted(new_files), edits=rep.replace("\n", " | "), note=("PLAN: " + m.group(1)[:200]) if m else None)
    if not applied:
        return _failed(h, "no edit could be applied. " + rep)
    nh = Handoff(goal=h.goal, from_dept="dev", to_dept="qa", deliverable=edits.to_deliverable(new_files), status="ok")
    nh.save()
    print("   [dev:editor] " + rep.splitlines()[0])
    return nh


def save(project, deliverable):
    """Write the files of a deliverable into the project folder (relative paths only); returns the names written."""
    written = []
    for rel, text in shipper.parse_files(deliverable).items():
        rel = shipper.safe_rel(rel)
        path = os.path.join(project, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text.rstrip("\n") + "\n")
        written.append(rel)
    return written
