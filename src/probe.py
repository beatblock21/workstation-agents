import sys, time, os
from openai import OpenAI
from llm import PROVIDERS
n, model = sys.argv[1], sys.argv[2]
p = PROVIDERS[n]
c = OpenAI(base_url=p["base_url"], api_key=os.environ[p["key"]], timeout=60, max_retries=0)
t = time.time()
try:
    r = c.chat.completions.create(model=model, messages=[{"role": "user", "content": "Reply with the word pong."}], max_tokens=200)
    print(n, model, "OK", round(time.time() - t, 1), "s:", r.choices[0].message.content)
except Exception as e:
    print(n, model, "FAIL", round(time.time() - t, 1), "s:", str(e)[:150])
