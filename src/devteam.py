"""Dev team (scale small/full): lead writes an interface contract, an author writes the code,
an independent tester writes the tests from the contract only. On a failure a fixer emits
anchored SEARCH/REPLACE edits (applied by edits.py) and reads the per-run devlog.
Every function returns None when the team cannot deliver, and the pipeline then falls back
to the classic single Dev call, so the team can never leave a run worse off than solo."""
import json, os, re
import department, devlog, edits, shipper
from handoff import Handoff, ROOT
from llm import chat

with open(os.path.join(ROOT, "agents", "devteam.json"), encoding="utf-8") as f:
    CFG = json.load(f)
CAP = dict(CFG["max_calls"])
_calls = 0


def reset():
    global _calls
    _calls = 0
    devlog.reset()


def calls_left(scale):
    return CAP.get(scale, 0) - _calls


def _ask(role, user, chain=None):
    global _calls
    cfg = CFG["roles"][role]
    msgs = [{"role": "system", "content": cfg["prompt"]}, {"role": "user", "content": user}]
    mt = cfg.get("max_tokens", 3000)
    ch = chain or department.CFG["dev"]["chain"]
    text = ""
    for _ in range(2):
        _calls += 1
        provider, text = chat(msgs, ch, dept="dev", max_tokens=mt)
        print(f"   [dev:{role}] answered via {provider}")
        if "[TRUNCATED" not in text:
            break
        mt *= 2
        print(f"   [dev:{role}] output was truncated; retrying with max_tokens={mt}")
    return text


def signature(report):
    """A stable fingerprint of the failure (numbers removed) to spot the same error twice."""
    lines = [l.strip() for l in (report or "").splitlines() if l.strip()]
    err = [l for l in lines if re.search(r"(Error|Exception|FAIL|assert)", l)]
    line = err[-1] if err else (lines[-1] if lines else "")
    frames = [m.group(1) for l in lines for m in [re.match(r'File ".*", line \d+, in (\S+)', l)] if m]
    where = f"{frames[-1]}: " if frames else ""
    return re.sub(r"\d+", "N", where + line)[:120]


def build(h, goal, scale):
    """Initial Dev deliverable from the team, or None to fall back to one Dev call."""
    if scale == "solo" or CAP.get(scale, 0) < 3:
        return None
    brief = f"GOAL:\n{goal}\n\nRESEARCH BRIEF:\n{h.deliverable}"
    try:
        contract = _ask("lead", brief)
        code_out = _ask("author", f"{brief}\n\nINTERFACE CONTRACT:\n{contract}")
        test_out = _ask("tester", f"GOAL:\n{goal}\n\nINTERFACE CONTRACT:\n{contract}")
    except Exception as e:
        print(f"   [dev team] failed ({str(e)[:80]}); falling back to one Dev call")
        return None
    if any("[TRUNCATED" in t for t in (contract, code_out, test_out)):
        print("   [dev team] output still truncated; falling back to one Dev call")
        return None
    code, tests = shipper.parse_files(code_out), shipper.parse_files(test_out)
    test_files = {k: v for k, v in tests.items() if os.path.basename(k).startswith("test_") or k.startswith("tests/")}
    code = {k: v for k, v in code.items() if k not in test_files}  # the tester owns the tests
    if not code or not test_files:
        print("   [dev team] missing code or test files; falling back to one Dev call")
        return None
    files = {**code, **test_files}
    nh = Handoff(goal=h.goal, from_dept="dev", to_dept="qa", deliverable=edits.to_deliverable(files), status="ok")
    nh.save()
    devlog.add("team", "build", files=list(files), note="contract:\n" + contract.strip()[:1500])
    return nh


def fix(goal, work, qa_text, report, scale, guidance=""):
    """One fixer round with anchored edits. New Handoff, or None to fall back to a whole-file Dev call."""
    if calls_left(scale) < 1:
        return None
    files = shipper.parse_files(work.deliverable)
    if not files:
        return None
    sig = signature(report)
    repeat = devlog.repeats(sig)
    chain = list(department.CFG["dev"]["chain"])
    k = repeat % len(chain)
    chain = chain[k:] + chain[:k]
    if repeat:
        print(f"   [dev:fixer] same error as the previous attempt; trying {chain[0]} first")
    user = (f"GOAL:\n{goal}\n\nCURRENT FILES:\n{edits.to_deliverable(files)}\n\nQA FINDINGS:\n{qa_text}\n\n"
            f"EXECUTION RESULT:\n{report}\n\nDEV LOG (earlier attempts):\n{devlog.tail(3) or '(none)'}"
            + (f"\n\n{guidance.strip()}" if guidance.strip() else ""))
    try:
        out = _ask("fixer", user, chain)
        new_deliv, rep, applied, rejected = edits.apply_to_deliverable(work.deliverable, out)
        if rejected and calls_left(scale) >= 1:
            user2 = (f"GOAL:\n{goal}\n\nCURRENT FILES (after the edits that applied):\n{new_deliv}\n\n"
                     f"YOUR PREVIOUS EDITS PARTLY FAILED:\n{rep}\n\nEXECUTION RESULT:\n{report}\n\n"
                     "Resend ONLY corrected edit blocks for the rejected edits, same format.")
            out2 = _ask("fixer", user2, chain)
            new_deliv, rep2, applied2, rejected2 = edits.apply_to_deliverable(new_deliv, out2)
            rep += "\nRETRY: " + rep2
            applied, rejected = applied + applied2, rejected2
    except Exception as e:
        print(f"   [dev:fixer] failed ({str(e)[:80]}); falling back to a whole-file Dev call")
        return None
    m = re.search(r"ROOT CAUSE:\s*(.+)", out)
    cause = m.group(1).strip()[:200] if m else ""
    devlog.add("fixer", "fix attempt", files=list(files), execution=(report.splitlines() or [""])[0], error=sig,
               root_cause=cause, edits=rep.replace("\n", " | "))
    devlog.note_sig(sig)
    if not applied:
        print("   [dev:fixer] no edit could be applied; falling back to a whole-file Dev call")
        return None
    nh = Handoff(goal=work.goal, from_dept="dev", to_dept="qa", deliverable=new_deliv, status="ok")
    nh.save()
    print(f"   [dev:fixer] {rep.splitlines()[0]}" + (f" | {cause[:100]}" if cause else ""))
    return nh
