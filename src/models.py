import os
from openai import OpenAI
from llm import PROVIDERS
for n, p in PROVIDERS.items():
    try:
        c = OpenAI(base_url=p["base_url"], api_key=os.environ[p["key"]])
        ids = sorted(m.id for m in c.models.list().data)
        if n == "openrouter": ids = [i for i in ids if i.endswith(":free")]
        if n == "gemini": ids = [i for i in ids if "flash" in i]
        print(f"\n== {n} ({len(ids)}) =="); print("\n".join(ids))
    except Exception as e:
        print(n, "FAIL:", str(e)[:200])
