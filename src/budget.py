import json, os, datetime, time

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

def check(provider, dept, est_tokens=0):
    _check_rate(provider, est_tokens)
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
    _WINDOW.setdefault(provider, []).append((time.time(), int(tokens or 0)))
    data = _load()
    d = data["usage"].setdefault(f"{provider}|{dept}", {"requests": 0, "tokens": 0})
    d["requests"] += 1
    d["tokens"] += int(tokens or 0)
    _save(data)


class RateLimited(BudgetExceeded):
    def __init__(self, msg, retry_after):
        super().__init__(msg)
        self.retry_after = retry_after

RATE = {  # per-minute limits (groq: docs; gemini: AI Studio chart; openrouter: unverified)
    "groq": {"rpm": 30, "tpm": 8000},
    "gemini": {"rpm": 15, "tpm": 250000},
    "openrouter": {"rpm": 20, "tpm": None},
}
_WINDOW = {}

def _check_rate(provider, est_tokens=0):
    r = RATE.get(provider, {})
    now = time.time()
    w = [(t, k) for t, k in _WINDOW.get(provider, []) if now - t < 60]
    _WINDOW[provider] = w
    if r.get("rpm") and len(w) >= r["rpm"]:
        raise RateLimited(f"{provider}: per-minute request limit", max(1.0, 61 - (now - w[0][0])))
    if r.get("tpm") and w and sum(k for _, k in w) + est_tokens > r["tpm"]:
        raise RateLimited(f"{provider}: per-minute token limit", max(1.0, 61 - (now - w[0][0])))
