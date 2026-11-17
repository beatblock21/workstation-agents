import os, re, sys
from handoff import Handoff, ROOT
from department import Department
import human
import runcheck
import shipper
from dataclasses import replace

MAX_QA_ROUNDS = 2

def passed(text):
    lines = text.strip().splitlines()
    first = lines[0].lstrip("*#_ ").upper() if lines else ""
    return first.startswith("PASS")

def step(dept, h, nxt):
    while True:
        print(f"-> {dept} working...")
        out = Department(dept).run(h, nxt)
        if out.status != "failed":
            return out
        ans = human.escalate(out, "failed", dept, f"{dept} failed: {out.deliverable[:300]}", ["retry", "abort"])
        if ans != "retry":
            out.status = "failed"
            out.save()
            return out

MAX_QUESTIONS = 5
CLARIFY_PROMPT = ("You are the Research department. Read the goal and list the questions you must ask the owner "
                  "before researching, only ones whose answers would change the approach (scope, scale, users, "
                  "constraints, preferred tools, deadline). Max 5. One per line, each starting with 'Q:'. "
                  "If the goal is already clear, reply NONE.")

def clarify(goal):
    raw = Department("research")._ask(f"GOAL:\n{goal}", CLARIFY_PROMPT)
    qs = [l.strip()[2:].strip() for l in raw.splitlines() if l.strip().upper().startswith("Q:")][:MAX_QUESTIONS]
    if not qs:
        return ""
    pairs = [(q, human.ask_text("research", q)) for q in qs]
    return "\n\nOWNER CLARIFICATIONS:\n" + "\n".join(f"- Q: {q}\n  A: {a}" for q, a in pairs)

def choose_option(h):
    seen = {}
    for l, n in re.findall(r"^[\s*#_-]*OPTION\s+([A-C])\b[\s:*\-]*(.+)$", h.deliverable, re.M | re.I):
        seen.setdefault(l.upper(), n)
    if len(seen) < 2:
        return
    rec = re.search(r"RECOMMENDATION\W*\s*([A-C])\b", h.deliverable, re.I)
    q = "Research proposes these approaches (details in its brief). " + (f"It recommends {rec.group(1).upper()}. " if rec else "") + "Which should Dev take?"
    labels = [f"{l}: {n.strip().strip('*')[:120]}" for l, n in seen.items()]
    m = re.search(r"^[\s*#_-]*OPTION\s+A\b", h.deliverable, re.M | re.I)
    print("\n--- RESEARCH BRIEF (options) ---\n" + h.deliverable[(m.start() if m else 0):][:2500] + "\n--- end ---")
    ans = human.escalate(h, "decision", "research", q, labels + ["let Research decide"])
    if not ans.startswith("let Research"):
        h.deliverable += f"\n\nOWNER DECISION: proceed with {ans}"
        h.save()

def dev_step(h):
    out = step("dev", h, "qa")
    tries = 0
    while out.status != "failed" and not shipper.parse_files(out.deliverable) and tries < 2:
        tries += 1
        print("-> format gate: Dev output had no '### FILE:' blocks; asking Dev to redo")
        note = ("FORMAT ERROR: your last answer had no '### FILE: path' blocks. Reply again with every file as a line "
                "'### FILE: relative/path' followed by a fenced code block.\n\nYOUR LAST ANSWER:\n" + out.deliverable)
        fix = Handoff(goal=h.goal, from_dept="owner", to_dept="dev", deliverable=h.deliverable + "\n\n" + note)
        out = step("dev", fix, "qa")
    return out

def run(goal, auto=False, repo=None):
    if not auto:
        goal += clarify(goal)
    h = Handoff(goal=goal, from_dept="owner", to_dept="research")
    research = step("research", h, "dev")
    if not auto and research.status != "failed":
        choose_option(research)
    if research.status == "failed":
        return research
    work = dev_step(research)
    if work.status == "failed":
        return work
    rounds = 0
    override = ""
    while True:
        ok, report = runcheck.check(work.deliverable)
        print("-> execution check:", report.splitlines()[0])
        qa_in = replace(work, deliverable=work.deliverable + "\n\nEXECUTION RESULT (run by the system, not by you):\n" + report)
        qa = step("qa", qa_in, "shipping")
        if qa.status == "failed":
            return qa
        if passed(qa.deliverable) and ok is not False:
            print("-> QA: PASS")
            break
        rounds += 1
        print(f"-> QA: FAIL (round {rounds}/{MAX_QA_ROUNDS})")
        note = ""
        if rounds >= MAX_QA_ROUNDS:
            q = f"QA has failed the work {rounds} times. Latest findings:\n{qa.deliverable[:600]}"
            ans = human.escalate(qa, "dispute", "qa vs dev", q, ["ship anyway", "send back to dev once more", "abort"])
            if ans == "ship anyway":
                override = "\n\nOWNER NOTE: owner approved shipping despite a QA FAIL."
                break
            if ans == "abort":
                qa.status = "failed"
                qa.save()
                return qa
            if ans != "send back to dev once more":
                note = f"\n\nOWNER GUIDANCE:\n{ans}"
            rounds = MAX_QA_ROUNDS - 1
        fix = Handoff(goal=goal, from_dept="qa", to_dept="dev",
                      deliverable=f"PREVIOUS DELIVERABLE:\n{work.deliverable}\n\nQA FINDINGS:\n{qa.deliverable}\n\nEXECUTION RESULT:\n{report}{note}")
        work = dev_step(fix)
    final = Handoff(goal=goal, from_dept="qa", to_dept="shipping",
                    deliverable=f"{work.deliverable}\n\nQA VERDICT:\n{qa.deliverable}{override}")
    ship = step("shipping", final, "owner")
    if repo and ship.status != "failed":
        try:
            shipper.ship(work.deliverable, ship.deliverable, repo)
        except Exception as e:
            print("SHIPPING ERROR:", e)
    out = os.path.join(ROOT, "state", f"result-{ship.id}.local.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Goal\n{goal}\n\n# Deliverable\n{work.deliverable}\n\n# QA\n{qa.deliverable}\n\n# Shipping notes\n{ship.deliverable}\n")
    print("Result saved:", out)
    return ship

if __name__ == "__main__":
    argv = sys.argv[1:]
    repo = None
    if "--repo" in argv:
        i = argv.index("--repo")
        repo = argv[i + 1]
        del argv[i:i + 2]
    auto = "--auto" in argv
    arg = " ".join(a for a in argv if a != "--auto").strip()
    if not arg:
        sys.exit('usage: python src\\pipeline.py "goal text"  (or a path to a goals file)')
    if os.path.isfile(arg):
        with open(arg, encoding="utf-8") as f:
            arg = f.read()
    res = run(arg, auto, repo)
    print("Final status:", res.status)
