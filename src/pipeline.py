import os, re, sys, time
from handoff import Handoff, ROOT
from department import Department
import human
import runcheck
import journal
import shipper
import team
import owner
import runstats
import devteam
import qateam
import iterate
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
                  "First check the goal for contradictory or impossible constraints; if there are any, your first question must name the conflict and ask which constraint to relax. "
"If the goal is already clear and consistent, reply NONE. Do not ask about anything the OWNER STANDING DEFAULTS in the goal already answer.")

def clarify(goal, notes=""):
    raw = Department("research")._ask(f"GOAL:\n{goal}{notes}", CLARIFY_PROMPT)
    qs = [l.strip()[2:].strip() for l in raw.splitlines() if l.strip().upper().startswith("Q:")][:MAX_QUESTIONS]
    if not qs:
        return ""
    pairs = [(q, human.ask_text("research", q)) for q in qs]
    return "\n\nOWNER CLARIFICATIONS:\n" + "\n".join(f"- Q: {q}\n  A: {a}" for q, a in pairs)

def choose_option(h, ask=True):
    seen = {}
    for l, n in re.findall(r"^[\s*#_-]*OPTION\s+([A-C])\b[\s:*\-]*(.+)$", h.deliverable, re.M | re.I):
        seen.setdefault(l.upper(), n)
    if len(seen) < 2:
        return
    rec = re.search(r"RECOMMENDATION\W*[A-C]?\W*OPTION\s+([A-C])\b", h.deliverable, re.I) or re.search(r"RECOMMENDATION\W*\s*([A-C])\b", h.deliverable, re.I)
    if not ask and re.search(r"^\W*CONFLICT:", h.deliverable, re.M | re.I):
        ask = True
    if not ask:
        if rec:
            h.deliverable += f"\n\nOWNER DECISION (auto): follow Research's recommendation, option {rec.group(1).upper()}"
            h.save()
        return
    q = "Research proposes these approaches (details in its brief). " + (f"It recommends {rec.group(1).upper()}. " if rec else "") + "Which should Dev take?"
    labels = [f"{l}: {n.strip().strip('*')[:120]}" for l, n in seen.items()]
    m = re.search(r"^[\s*#_-]*OPTION\s+A\b", h.deliverable, re.M | re.I)
    print("\n--- RESEARCH BRIEF (options) ---\n" + h.deliverable[(m.start() if m else 0):][:2500] + "\n--- end ---")
    ans = human.escalate(h, "decision", "research", q, labels + ["let Research decide"])
    if ans.startswith("let Research") and rec:
        ans = f"Research's recommendation, option {rec.group(1).upper()}"
    if not ans.startswith("let Research"):
        h.deliverable += f"\n\nOWNER DECISION: proceed with {ans}"
        h.save()

def dev_step(h):
    out = step("dev", h, "qa")
    tries = 0
    while out.status != "failed" and (not shipper.parse_files(out.deliverable) or "[TRUNCATED" in out.deliverable) and tries < 2:
        tries += 1
        print("-> format gate: Dev output was malformed or truncated; asking Dev to redo")
        note = ("FORMAT ERROR: your last answer was cut off or had no '### FILE: path' blocks. Keep files shorter and reply again with every file as a line "
                "'### FILE: relative/path' followed by a fenced code block.\n\nYOUR LAST ANSWER:\n" + out.deliverable)
        fix = Handoff(goal=h.goal, from_dept="owner", to_dept="dev", deliverable=h.deliverable + "\n\n" + note)
        out = step("dev", fix, "qa")
    return out

def split_scale(scale):
    """'small' -> all three teams; 'small:dev' or 'full:research+qa' -> only those teams; 'solo' -> none.
    Returns (research_scale, dev_scale, qa_scale); a team that is off gets 'solo'."""
    base, _, only = scale.partition(":")
    if base == "solo":
        return "solo", "solo", "solo"
    teams = set(only.split("+")) if only else {"research", "dev", "qa"}
    bad = teams - {"research", "dev", "qa"}
    if bad:
        raise ValueError(f"unknown team(s) {sorted(bad)}; use research, dev, qa")
    return tuple(base if t in teams else "solo" for t in ("research", "dev", "qa"))


def run(goal, auto=False, repo=None, scale="solo", profile="default", project=None):
    devteam.reset()
    qateam.reset()
    goal += owner.defaults()
    pfiles, pctx = {}, ""
    if project:
        os.makedirs(project, exist_ok=True)
        pfiles, pctx = iterate.prepare(project, goal)
        if pfiles:
            goal += "\n\nCHANGE REQUEST on an existing project: all existing behaviour and all existing tests must keep working."
    rs, ds, qs = split_scale(scale)
    notes = team.notes(goal, rs, profile)
    if not auto:
        goal += clarify(goal, notes)
    h = Handoff(goal=goal, from_dept="owner", to_dept="research", deliverable=notes + (pctx if pfiles else ""))
    research = step("research", h, "dev")
    if research.status != "failed":
        if auto:
            print("\n--- RESEARCH BRIEF (auto) ---\n" + research.deliverable[:1800] + "\n--- end ---")
        dm = re.search(r"^\W*DISPUTE:\s*(.+)$", research.deliverable, re.M | re.I)
        if dm and not dm.group(1).strip().lower().startswith("none"):
            if auto:
                print("-> Research team flagged an unresolved DISPUTE (auto mode, not asking):", dm.group(1)[:200])
            else:
                dans = human.ask_human("dispute", "research", "Research's team could not settle this: " + dm.group(1)[:400] + "\nHow should Research proceed?")
                research.deliverable += f"\n\nOWNER DECISION: {dans}"
                research.save()
        if re.search(r"^\W*CONFLICT:", notes, re.M | re.I) and not re.search(r"^\W*CONFLICT:", research.deliverable, re.M | re.I):
            research.deliverable = "CONFLICT: flagged by the Research team (see specialist notes)\n" + research.deliverable
        choose_option(research, ask=not auto)
        dec = re.findall(r"^OWNER DECISION.*$", research.deliverable, re.M)
        if dec:
            goal += "\n\n" + "\n".join(dec) + "\nThe owner's decision overrides any conflicting constraint above; judge against it."
            research.goal = goal
    if research.status == "failed":
        return research
    work = iterate.edit_step(research, goal, pfiles, pctx) if pfiles else ((devteam.build(research, goal, ds) if ds != "solo" else None) or dev_step(research))
    if work.status == "failed":
        return work
    rounds = 0
    override = ""
    sandbox_ok = False
    while True:
        ok, report = runcheck.check(work.deliverable)
        if report.startswith("NOT RUN: flagged"):
            if not sandbox_ok:
                q = "The code was flagged and not executed:\n" + report + "\nRun it anyway in the sandbox (temp folder, stripped environment, timeout) so QA can grade real results?"
                ans = human.escalate(work, "approval", "qa", q, ["run in sandbox", "abort"])
                if ans != "run in sandbox":
                    work.status = "failed"
                    work.save()
                    return work
                sandbox_ok = True
            ok, report = runcheck.check(work.deliverable, force=True)
        print("-> execution check:", report.splitlines()[0])
        extra = qateam.evidence(goal, work, report, qs) if qs != "solo" else ""
        qa_in = replace(work, deliverable=work.deliverable + "\n\nEXECUTION RESULT (run by the system, not by you):\n" + report + extra)
        qa = step("qa", qa_in, "shipping")
        if qa.status == "failed":
            return qa
        if passed(qa.deliverable) and ok is not False:
            print("-> QA: PASS")
            break
        rounds += 1
        print(f"-> QA: FAIL (round {rounds}/{MAX_QA_ROUNDS})")
        runstats.R.qa_fails += 1
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
        team_work = devteam.fix(goal, work, qa.deliverable, report, ds if ds != "solo" else "small", note) if (ds != "solo" or pfiles) else None
        if team_work is not None:
            work = team_work
            continue
        fix = Handoff(goal=goal, from_dept="qa", to_dept="dev",
                      deliverable=f"PREVIOUS DELIVERABLE:\n{work.deliverable}\n\nQA FINDINGS:\n{qa.deliverable}\n\nEXECUTION RESULT:\n{report}{note}\n\nFIX INSTRUCTIONS: first state ROOT CAUSE in one line from the EXECUTION RESULT, then change only the code that causes the failure and keep every other line as it is. If a test expectation is wrong fix the test, otherwise fix the code. Still reply with every file in full as ### FILE blocks, then the ROOT CAUSE line.")
        work = dev_step(fix)
    if report.startswith("NOT RUN: flagged"):
        gate_q = "The code was NOT executed (flagged patterns), so QA judged it by reading only.\n" + report
        gate = human.escalate(qa, "approval", "qa", gate_q, ["ship unverified", "abort"])
        if gate != "ship unverified":
            qa.status = "failed"
            qa.save()
            return qa
    if project and not override:
        iterate.save(project, work.deliverable)
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
        f.write(f"# Goal\n{goal}\n\n{notes.strip() or 'SPECIALIST NOTES: (none)'}\n\n# Research brief\n{research.deliverable}\n\n# Deliverable\n{work.deliverable}\n\n# QA\n{qa.deliverable}\n\n# Shipping notes\n{ship.deliverable}\n\n# Run report\n{runstats.R.summary()}\n")
    print("Result saved:", out)
    return ship

if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--resume" in argv:
        rid = argv[argv.index("--resume") + 1]
        journal.J.start(rid)
        if not journal.J.meta:
            sys.exit(f"no saved run {rid}")
        if journal.J.meta.get("done"):
            sys.exit(f"run {rid} already finished")
        m = journal.J.meta
        print(f"Resuming run {rid} ({len(journal.J.entries)} steps already saved)")
        res = run(m["goal"], m["auto"], m["repo"], m.get("scale", "solo"), m.get("profile", "default"), m.get("project"))
        journal.J.finish()
        print("Final status:", res.status)
        sys.exit(0)
    project = None
    if "--project" in argv:
        i = argv.index("--project")
        project = argv[i + 1]
        del argv[i:i + 2]
    repo = None
    if "--repo" in argv:
        i = argv.index("--repo")
        repo = argv[i + 1]
        del argv[i:i + 2]
    auto = "--auto" in argv
    scale, profile = "solo", "default"
    for flag in ("--scale", "--profile"):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 >= len(argv):
                sys.exit(f"{flag} needs a value")
            val = argv[i + 1]
            del argv[i:i + 2]
            if flag == "--scale":
                scale = val
            else:
                profile = val
    if scale.split(":")[0] not in ("solo", "small", "full"):
        sys.exit("--scale must be solo, small or full, optionally with teams such as small:dev or full:research+qa")
    try:
        split_scale(scale)
    except ValueError as e:
        sys.exit(str(e))
    arg = " ".join(a for a in argv if a != "--auto").strip()
    if not arg:
        sys.exit('usage: python src\\pipeline.py "goal text"  (or a path to a goals file)')
    if os.path.isfile(arg):
        with open(arg, encoding="utf-8") as f:
            arg = f.read()
    rid = time.strftime("%Y%m%d-%H%M%S")
    journal.J.start(rid, {"goal": arg, "auto": auto, "repo": repo, "scale": scale, "profile": profile, "project": project})
    print(f"Run id: {rid}  (if it crashes: python src\\pipeline.py --resume {rid})")
    res = run(arg, auto, repo, scale, profile, project)
    journal.J.finish()
    print("Final status:", res.status)
