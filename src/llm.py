import os
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

PROVIDERS = {
    "groq": dict(base_url="https://api.groq.com/openai/v1", key="GROQ_API_KEY",model="openai/gpt-oss-120b"),
    "gemini": dict(base_url="https://generativelanguage.googleapis.com/v1beta/openai/", key="GEMINI_API_KEY", model="gemini-3.5-flash-lite"),
    "openrouter":dict(base_url="https://openrouter.ai/api/v1", key="OPENROUTER_API_KEY", model="nvidia/nemotron-3-ultra-550b-a55b:free"),
}

def ask(provider, messages, max_tokens=300):
    p = PROVIDERS[provider]
    client = OpenAI(base_url=p["base_url"], api_key=os.environ[p["key"]], timeout=20, max_retries=0)
    r = client.chat.completions.create(model=p["model"], messages= messages, max_tokens= max_tokens)
    return r.choices[0].message.content

def chat(messages, chain):
    errors = []
    for name in chain:
        try:
            return name, ask(name, messages)
        except Exception as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError("|".join(errors))
