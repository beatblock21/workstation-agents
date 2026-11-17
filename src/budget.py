import json, os, datetime

LIMITS = {  # per provider per UTC day; placeholders, tune later
    "groq": {"requests": 900, "tokens": 180000},
    "gemini": {"requests": 450, "tokens": 2000000},
    "openrouter": {"requests": 40, "tokens": 150000},
}
DEPT_SHARE = {"research": 0.25, "dev": 0.35, "qa": 0.25, "shipping": 0.15}
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state", "usage.local.json")

class BudgetExceeded(Exception):
    pass

def _load():
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    try:
        with open(PATH) as f:
            data = json.load(f)
        if data.get("date") == today:
            return data
    except Exception:
        pass
    return {"date": today, "usage": {}}

def _save(data):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w") as f:
        json.dump(data, f, indent=1)

def check(provider, dept):
    u = _load()["usage"]
    lim = LIMITS[provider]
    share = DEPT_SHARE.get(dept, 1.0)
    tot_req = sum(v["requests"] for k, v in u.items() if k.startswith(provider + "|"))
    tot_tok = sum(v["tokens"] for k, v in u.items() if k.startswith(provider + "|"))
    d = u.get(f"{provider}|{dept}", {"requests": 0, "tokens": 0})
    if tot_req >= lim["requests"] or tot_tok >= lim["tokens"]:
        raise BudgetExceeded(f"{provider}: provider daily limit reached")
    if d["requests"] >= lim["requests"] * share or d["tokens"] >= lim["tokens"] * share:
        raise BudgetExceeded(f"{provider}: {dept} daily share reached")

def record(provider, dept, tokens):
    data = _load()
    d = data["usage"].setdefault(f"{provider}|{dept}", {"requests": 0, "tokens": 0})
    d["requests"] += 1
    d["tokens"] += int(tokens or 0)
    _save(data)
