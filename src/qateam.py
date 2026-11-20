"""QA team (scale small/full). After the execution check passes, specialists gather evidence for the
QA lead (the normal QA prompt, which alone gives the verdict):
  - auditor: line-by-line constraint checklist read from the code (once per run)
  - prober: writes extra edge-case probes, which the system runs in the sandbox runner (every round);
            the probe file is never part of the deliverable
  - reviewer (full only): weak or tautological tests (once per run)
Evidence is skipped when the code already failed or was not executed (QA has what it needs then).
Flagged probe code is reported as not run and never prompts the owner. Any failure here returns
what was collected so far, so the team can never block a run."""
import json, os, re
import department, devlog, edits, runcheck, shipper
from handoff import ROOT
from llm import chat

with open(os.path.join(ROOT, "agents", "qateam.json"), encoding="utf-8") as f:
    CFG = json.load(f)
CAP = dict(CFG["max_calls"])
_calls = 0
_audited = False
_reviewed = False


def reset():
    global _calls, _audited, _reviewed
    _calls, _audited, _reviewed = 0, False, False


def calls_left(scale):
    return CAP.get(scale, 0) - _calls


def _is_test(path):
    return os.path.basename(path).startswith("test_") or path.startswith("tests/")


def _ask(role, user):
    global _calls
    cfg = CFG["roles"][role]
    msgs = [{"role": "system", "content": cfg["prompt"]}, {"role": "user", "content": user}]
    _calls += 1
    provider, text = chat(msgs, department.CFG["qa"]["chain"], dept="qa", max_tokens=cfg.get("max_tokens", 1500))
    print(f"   [qa:{role}] answered via {provider}")
    return text


def _probe(goal, code):
    out = _ask("prober", f"GOAL:\n{goal}\n\nCURRENT FILES (tests excluded):\n{edits.to_deliverable(code)}")
    pf = shipper.parse_files(out)
    src = next((v for k, v in pf.items() if os.path.basename(k).startswith("test_") or "probe" in k), None)
    if src is None:
        return "PROBES NOT RUN: the prober produced no probe file."
    ok, rep = runcheck.check(edits.to_deliverable({**code, "test_qa_probe.py": src}))
    if ok is None:
        return "PROBES NOT RUN: " + rep.splitlines()[0]
    passed = re.findall(r"(?m)^PROBE PASS: (.+)$", rep)
    failed = re.findall(r"(?m)^PROBE FAIL: (.+)$", rep)
    if not passed and not failed:
        return ("PROBES INVALID: the probe file crashed before reporting any probe "
                "(a probe bug, not evidence about the code):\n" + rep[-600:])
    lines = [f"{len(passed) + len(failed)} probes ran: {len(passed)} passed, {len(failed)} failed"]
    lines += [f"PROBE FAIL: {x}" for x in failed]
    return "\n".join(lines)


def evidence(goal, work, report, scale):
    """Text block to append to the QA input, or '' when there is nothing to add."""
    global _audited, _reviewed
    if scale == "solo" or calls_left(scale) < 1:
        return ""
    if not (report or "").startswith("RAN OK"):
        return ""
    files = shipper.parse_files(work.deliverable)
    if not files:
        return ""
    code = {k: v for k, v in files.items() if not _is_test(k)}
    has_tests = any(_is_test(k) for k in files)
    parts = []
    try:
        if not _audited and calls_left(scale) >= 1:
            _audited = True
            parts.append("[constraint auditor]\n" + _ask(
                "auditor", f"GOAL:\n{goal}\n\nCURRENT FILES:\n{edits.to_deliverable(files)}").strip())
        if scale == "full" and has_tests and not _reviewed and calls_left(scale) >= 1:
            _reviewed = True
            parts.append("[test reviewer]\n" + _ask(
                "reviewer", f"GOAL:\n{goal}\n\nCURRENT FILES:\n{edits.to_deliverable(files)}").strip())
        if code and calls_left(scale) >= 1:
            parts.append("[probe results]\n" + _probe(goal, code))
    except Exception as e:
        print(f"   [qa team] failed ({str(e)[:80]}); the QA lead continues with what was collected")
    if not parts:
        return ""
    for p in parts:
        print("   [qa team] " + " | ".join(p.splitlines()[:2])[:160])
    body = "\n\n".join(parts)
    devlog.add("qa team", "evidence", note=body[:1200])
    return ("\n\nQA TEAM EVIDENCE (collected by the system; probes are extra tests and are not part of the "
            "deliverable):\n" + body)
