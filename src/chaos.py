import os
os.environ["GROQ_API_KEY"] = "bad-key"  # dotenv does not override existing env vars
import budget, llm, pipeline, department
from handoff import Handoff
from department import Department

results = []
def check(name, cond):
    results.append(bool(cond))
    print("PASS" if cond else "FAIL", "-", name)

# 1. bad key falls through (one real, tiny call)
try:
    prov, _ = llm.chat([{"role": "user", "content": "Reply with the word pong."}], ["groq", "gemini"], dept="chaos", max_tokens=50)
    check("bad groq key falls through to gemini", prov == "gemini")
except Exception as e:
    check(f"bad key fallthrough raised: {e}", False)

# 2. every provider over budget -> failed handoff, no crash
saved = {k: dict(v) for k, v in budget.LIMITS.items()}
for v in budget.LIMITS.values():
    v["requests"] = 0
out = Department("research").run(Handoff(goal="x", from_dept="owner", to_dept="research"), "dev")
check("all providers exhausted gives status failed, no crash", out.status == "failed")
for k, v in saved.items():
    budget.LIMITS[k] = v

# 3-5. QA verdict parsing
check("malformed QA verdict counts as FAIL", not pipeline.passed("Looks good to me!"))
check("empty QA verdict counts as FAIL", not pipeline.passed(""))
check("markdown PASS accepted", pipeline.passed("**PASS**\n1. ok"))

# 6. corrupt usage file
os.makedirs(os.path.dirname(budget.PATH), exist_ok=True)
backup = open(budget.PATH).read() if os.path.exists(budget.PATH) else None
with open(budget.PATH, "w") as f:
    f.write("{not json")
try:
    budget.check("gemini", "dev")
    ok = True
except Exception:
    ok = False
check("corrupt usage file does not crash budget check", ok)
if backup is not None:
    with open(budget.PATH, "w") as f:
        f.write(backup)

# 7. truncation retry doubles max_tokens
calls = []
def fake(msgs, chain, dept="x", max_tokens=300):
    calls.append(max_tokens)
    return "p", ("partial [TRUNCATED: x]" if len(calls) == 1 else "complete")
real_chat = department.chat
department.chat = fake
res = Department("dev")._ask("hi")
department.chat = real_chat
check("truncated output retried once with doubled max_tokens", res == "complete" and calls == [4000, 8000])

# 8. simulated 429 on every provider
def boom(*a, **k):
    raise RuntimeError("429 simulated")
llm.RETRY_WAIT = False
real_ask = llm.ask
llm.ask = boom
try:
    llm.chat([{"role": "user", "content": "x"}], ["groq", "gemini", "openrouter"], dept="chaos")
    check("simulated 429 on all providers raises a clear error", False)
except RuntimeError as e:
    check("simulated 429 on all providers raises a clear error", all(n in str(e) for n in ["groq", "gemini", "openrouter"]))
llm.ask = real_ask

import time
budget.RATE["groq"] = {"rpm": 2, "tpm": 1000}
budget._WINDOW["groq"] = [(time.time(), 400), (time.time(), 400)]
try:
    budget.check("groq", "chaos")
    check("per-minute guard blocks a provider at its RPM", False)
except budget.RateLimited as e:
    check("per-minute guard blocks a provider at its RPM", e.retry_after > 0)
budget.RATE["groq"] = {"rpm": 30, "tpm": 1000}
budget._WINDOW["groq"] = [(time.time(), 900)]
try:
    budget.check("groq", "chaos", est_tokens=200)
    check("per-minute guard blocks a provider near its TPM", False)
except budget.RateLimited:
    check("per-minute guard blocks a provider near its TPM", True)
budget._WINDOW["groq"] = []
budget.RATE["groq"] = {"rpm": 30, "tpm": 8000}

# 11. wait-once retry waits and then succeeds (waits were never attached before the llm.py fix)
slept = []
real_sleep = llm.time.sleep
llm.time.sleep = lambda s: slept.append(s)
llm.RETRY_WAIT = True
cnt = {"n": 0}
def flaky(provider, messages, max_tokens=300, dept="misc"):
    cnt["n"] += 1
    if cnt["n"] <= 3:
        raise budget.RateLimited("simulated", 5)
    return "ok"
llm.ask = flaky
try:
    got = llm.chat([{"role": "user", "content": "x"}], ["groq", "gemini", "openrouter"], dept="chaos")
except Exception as e:
    got = ("error", str(e))
llm.ask = real_ask
llm.time.sleep = real_sleep
check("wait-once retry sleeps once and recovers", slept == [6.0] and got == ("groq", "ok"))

print(f"\n{sum(results)}/{len(results)} passed")
