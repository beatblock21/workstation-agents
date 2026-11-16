from handoff import Handoff
import human
h = Handoff(goal="Demo escalation", from_dept="research", to_dept="dev", deliverable="draft brief")
a = human.escalate(h, "decision", "research", "Cache in memory or on disk?", ["memory", "disk"])
print("answer:", a, "| status:", h.status, "| decisions:", h.decisions)
b = human.dispute(h, "dev", "use sqlite", "qa", "use json file")
print("dispute ->", b, "| decisions logged:", len(h.decisions))
