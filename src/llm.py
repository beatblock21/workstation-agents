import os
from dotenv import load_dotenv
from openai import OpenAI
import budget
import journal
import time
load_dotenv()

PROVIDERS = {
    "groq": dict(base_url="https://api.groq.com/openai/v1", key="GROQ_API_KEY",model="openai/gpt-oss-120b"),
    "gemini": dict(base_url="https://generativelanguage.googleapis.com/v1beta/openai/", key="GEMINI_API_KEY", model="gemini-3.5-flash-lite"),
    "openrouter":dict(base_url="https://openrouter.ai/api/v1", key="OPENROUTER_API_KEY", model="nvidia/nemotron-3-ultra-550b-a55b:free"),
}

def ask(provider, messages, max_tokens=300, dept="misc"):
    p = PROVIDERS[provider]
    budget.check(provider, dept, est_tokens=sum(len(m["content"]) for m in messages) // 4)
    client = OpenAI(base_url=p["base_url"], api_key=os.environ[p["key"]], timeout=20, max_retries=0)
    r = client.chat.completions.create(model=p["model"], messages= messages, max_tokens= max_tokens)
    budget.record(provider, dept, getattr(r.usage, 'total_tokens', 0))
    text = r.choices[0].message.content or ""
    if r.choices[0].finish_reason == "length":
        text += "\n\n[TRUNCATED: output hit the token limit]"
    return text

def _chat_once(messages, chain, dept="misc", max_tokens=300):
    hit = journal.J.replay("chat")
    if hit:
        return hit[0], hit[1]
    errors, waits = [], []
    for name in chain:
        try:
            text = ask(name, messages, max_tokens=max_tokens, dept=dept)
            journal.J.record("chat", [name, text])
            return name, text
        except Exception as e:
            errors.append(f"{name}: {e}")
            if isinstance(e, budget.RateLimited):
                waits.append(e.retry_after)
            elif "429" in str(e):
                waits.append(20)
    err = RuntimeError("|".join(errors))
    err.waits = waits
    raise err


RETRY_WAIT = True

def chat(messages, chain, dept="misc", max_tokens=300):
    for attempt in range(2):
        try:
            return _chat_once(messages, chain, dept, max_tokens)
        except RuntimeError as e:
            waits = getattr(e, "waits", [])
            if attempt == 0 and waits and RETRY_WAIT:
                w = min(waits) + 1
                print(f"   all providers busy; waiting {w:.0f}s for a rate-limit window...")
                time.sleep(w)
                continue
            raise
