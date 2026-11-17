import json, os, time
from handoff import ROOT, Handoff
import journal

LOG = os.path.join(ROOT, "state", "decisions.local.jsonl")

def log_decision(rec):
    if journal.J.last_replayed:
        return
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    rec["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

def ask_human(kind, dept, question, options=None):
    hit = journal.J.replay("human")
    if hit is not None:
        print(f"[resume] reusing your earlier answer to {question[:60]!r}: {hit}")
        return hit
    ans = _ask_human(kind, dept, question, options)
    journal.J.record("human", ans)
    return ans

def _ask_human(kind, dept, question, options=None):
    print(f"\n=== OWNER INPUT NEEDED [{kind.upper()}] from {dept} ===")
    print(question)
    if options:
        for i, o in enumerate(options, 1):
            print(f"  {i}. {o}")
        print("  (type a number, or type your own answer)")
    ans = ""
    while not ans:
        ans = input("> ").strip()
    if options and ans.isdigit() and 1 <= int(ans) <= len(options):
        ans = options[int(ans) - 1]
    return ans

def escalate(h, kind, dept, question, options=None):
    h.status = "needs_human"
    if question not in h.open_questions:
        h.open_questions.append(question)
    h.save()  # saved before asking, so a crash while waiting is resumable
    ans = ask_human(kind, dept, question, options)
    h.decisions.append({"kind": kind, "question": question, "answer": ans})
    h.open_questions.remove(question)
    h.status = "ok"
    h.save()
    log_decision({"handoff": h.id, "kind": kind, "dept": dept, "question": question, "answer": ans})
    return ans

def dispute(h, dept_a, view_a, dept_b, view_b):
    q = f"{dept_a} says: {view_a}\n{dept_b} says: {view_b}\nWhich do you side with?"
    return escalate(h, "dispute", f"{dept_a} vs {dept_b}", q, [dept_a, dept_b])

def resume(path):
    h = Handoff.load(path)
    if h.status == "needs_human" and h.open_questions:
        escalate(h, "resume", h.to_dept, h.open_questions[0])
    return h

def ask_text(dept, question, kind="question"):
    hit = journal.J.replay("text")
    if hit is not None:
        print(f"[resume] reusing your earlier answer to {question[:60]!r}: {hit}")
        return hit
    ans = _ask_text(dept, question, kind)
    journal.J.record("text", ans)
    return ans

def _ask_text(dept, question, kind="question"):
    print(f"\n=== {dept.upper()} ASKS ({kind}) ===")
    print(question)
    ans = input("> (Enter = use your judgment) ").strip()
    log_decision({"kind": kind, "dept": dept, "question": question, "answer": ans or "(use your judgment)"})
    return ans or "(use your judgment)"
