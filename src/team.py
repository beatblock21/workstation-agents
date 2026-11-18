import json, os
from department import Department
from handoff import ROOT

with open(os.path.join(ROOT, "agents", "profiles.json"), encoding="utf-8") as f:
    CFG = json.load(f)


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
        done.append((n, text.strip()))
        print(f"   [{n}] " + " ".join(text.split())[:300])
    if not done:
        return ""
    body = "\n\n".join(f"[{n}]\n{t}" for n, t in done)
    return "\n\nSPECIALIST NOTES (from the Research team; you are the admin, merge them):\n" + body
