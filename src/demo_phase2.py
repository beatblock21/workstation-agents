from handoff import Handoff
from department import Department
h = Handoff(goal="Give a 5-line plan to cache API responses in a small Python script", from_dept="owner", to_dept="research")
r = Department("research").run(h, "dev", subtasks=["List 2 caching approaches, one line each"])
print(r.status, r.from_dept, "->", r.to_dept, r.id)
print(r.deliverable[:300])
