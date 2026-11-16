import os, sys
from handoff import Handoff, ROOT
from department import Department
import human

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

def run(goal):
    h = Handoff(goal=goal, from_dept="owner", to_dept="research")
    research = step("research", h, "dev")
    if research.status == "failed":
        return research
    work = step("dev", research, "qa")
    if work.status == "failed":
        return work
    rounds = 0
    while True:
        qa = step("qa", work, "shipping")
        if qa.status == "failed":
            return qa
        if passed(qa.deliverable):
            print("-> QA: PASS")
            break
        rounds += 1
        print(f"-> QA: FAIL (round {rounds}/{MAX_QA_ROUNDS})")
        note = ""
        if rounds >= MAX_QA_ROUNDS:
            q = f"QA has failed the work {rounds} times. Latest findings:\n{qa.deliverable[:600]}"
            ans = human.escalate(qa, "dispute", "qa vs dev", q, ["ship anyway", "send back to dev once more", "abort"])
            if ans == "ship anyway":
                break
            if ans == "abort":
                qa.status = "failed"
                qa.save()
                return qa
            if ans != "send back to dev once more":
                note = f"\n\nOWNER GUIDANCE:\n{ans}"
            rounds = MAX_QA_ROUNDS - 1
        fix = Handoff(goal=goal, from_dept="qa", to_dept="dev",
                      deliverable=f"PREVIOUS DELIVERABLE:\n{work.deliverable}\n\nQA FINDINGS:\n{qa.deliverable}{note}")
        work = step("dev", fix, "qa")
    final = Handoff(goal=goal, from_dept="qa", to_dept="shipping",
                    deliverable=f"{work.deliverable}\n\nQA VERDICT:\n{qa.deliverable}")
    ship = step("shipping", final, "owner")
    out = os.path.join(ROOT, "state", f"result-{ship.id}.local.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# Goal\n{goal}\n\n# Deliverable\n{work.deliverable}\n\n# QA\n{qa.deliverable}\n\n# Shipping notes\n{ship.deliverable}\n")
    print("Result saved:", out)
    return ship

if __name__ == "__main__":
    arg = " ".join(sys.argv[1:]).strip()
    if not arg:
        sys.exit('usage: python src\\pipeline.py "goal text"  (or a path to a goals file)')
    if os.path.isfile(arg):
        with open(arg, encoding="utf-8") as f:
            arg = f.read()
    res = run(arg)
    print("Final status:", res.status)
