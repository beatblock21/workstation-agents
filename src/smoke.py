from llm import PROVIDERS, ask
for name in PROVIDERS:
    try:
        print(name,"OK:", ask(name, [{"role": "user", "content": "Reply with the word pong."}]))
    except Exception as e:
        print(name,"FAIL:", str(e)[:200])