import json, os, re
from department import Department
from handoff import ROOT

with open(os.path.join(ROOT, "agents", "profiles.json"), encoding="utf-8") as f:
    CFG = json.load(f)


VERIFY_PROMPT = ("You are a strict logic checker. You get a GOAL and a claimed CONFLICT between two of its constraints. "
                 "Answer YES only if no single design could satisfy both constraints at the same time. "
                 "Answer NO if a design choice (a default plus a flag that overrides it, a mode switch, an option) satisfies both. "
                 "Start your reply with YES or NO, then one short sentence.")


def verify_conflicts(goal, dept, text):
    """Second opinion on each CONFLICT: line (at most 3). A clear NO demotes it to TENSION: so it does not
    force an owner question; anything else (YES, unclear, error) keeps it, so a real conflict is never lost."""
    out, checked = [], 0
    for line in text.splitlines():
        m = re.match(r"^(\W*)CONFLICT:\s*(.+)$", line)
        if m and checked < 3:
            checked += 1
            try:
                ans = dept._ask(f"GOAL:\n{goal}\n\nCLAIMED CONFLICT:\n{m.group(2)}", VERIFY_PROMPT).strip()
            except Exception:
                ans = ""
            if re.match(r"NO\b", ans.upper()):
                print(f"   [conflict check] demoted to TENSION: {m.group(2)[:100]}")
                line = f"{m.group(1)}TENSION: {m.group(2)} (checked: one design satisfies both)"
        out.append(line)
    return "\n".join(out)


def notes(goal, scale="solo", profile="default"):
    """Run the Research specialists in sequence and return a notes block for the
    Research admin (the normal Research prompt). Returns '' for solo, so solo
    behaviour is unchanged. Calls go through llm.chat: budget, rate guard and
    journal all apply. A failed specialist is skipped, never fatal."""
    if scale == "solo":
        return ""
    prof = CFG["profiles"].get(profile) or CFG["profiles"]["default"]
    names = prof.get(scale)
    if names is None:
        raise ValueError(f"unknown scale {scale!r} (use solo, small or full)")
    cap = CFG.get("max_calls", {}).get(scale, len(names))
    dept = Department("research")
    done = []
    for n in names[:cap]:
        prior = "".join(f"\n\n[{k} notes]\n{v}" for k, v in done)
        try:
            text = dept._ask(f"GOAL:\n{goal}{prior}", CFG["specialists"][n])
        except Exception as e:
            print(f"   [research] specialist {n} failed ({str(e)[:80]}); continuing without it")
            continue
        if n == "conflicts":
            text = verify_conflicts(goal, dept, text)
        done.append((n, text.strip()))
        print(f"   [{n}] " + " ".join(text.split())[:300])
    if not done:
        return ""
    body = "\n\n".join(f"[{n}]\n{t}" for n, t in done)
    return "\n\nSPECIALIST NOTES (from the Research team; you are the admin, merge them):\n" + body
