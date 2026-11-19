import runcheck
F = chr(96) * 3
def blk(code):
    return f"{F}python\n{code}\n{F}"
print(runcheck.check(blk("assert 1 + 1 == 2")))
print(runcheck.check(blk("assert 1 == 2"))[0])
print(runcheck.check(blk("import shutil\nshutil.rmtree('x')")))
print(runcheck.check("no code here"))

multi = f"### FILE: pkg/m.py\n{F}python\ndef f():\n    return 2\n{F}\n\n### FILE: tests/test_m.py\n{F}python\nfrom pkg.m import f\nassert f() == 2\nprint('ok')\n{F}\n"
print("multi ok:", runcheck.check(multi)[0])
print("multi bad caught:", runcheck.check(multi.replace("== 2", "== 3"))[0] is False)

inter = f"### FILE: app.py\n{F}python\nname = input('x')\nprint(name)\n{F}\n"
print("interactive ok:", runcheck.check(inter)[0])
crash = f"### FILE: app.py\n{F}python\nraise ValueError('boom')\n{F}\n"
print("real crash still caught:", runcheck.check(crash)[0] is False)

inter = f"### FILE: app.py\n{F}python\nname = input('x')\nprint(name)\n{F}\n"
print("interactive ok:", runcheck.check(inter)[0])
crash = f"### FILE: app.py\n{F}python\nraise ValueError('boom')\n{F}\n"
print("real crash still caught:", runcheck.check(crash)[0] is False)

safe = f"### FILE: calc.py\n{F}python\nimport ast\nprint(ast.dump(ast.parse('1+1', mode='eval')) != '')\n{F}\n"
print("ast mode=eval not flagged:", runcheck.check(safe)[0] is True)
evil = f"### FILE: calc.py\n{F}python\nprint(eval('1+1'))\n{F}\n"
print("real eval() still flagged:", runcheck.check(evil)[0] is None)

w = f"### FILE: app.py\n{F}python\nwith open('out.txt', 'w') as fh:\n    fh.write('x')\nprint('wrote')\n{F}\n"
print("relative write now runs:", runcheck.check(w)[0] is True)
rd = f"### FILE: app.py\n{F}python\ntry:\n    open('warc.txt')\nexcept FileNotFoundError:\n    print('ok')\n{F}\n"
print("read-mode open not flagged:", runcheck.check(rd)[0] is True)
ab = f"### FILE: app.py\n{F}python\nopen('C:/x.txt', 'w')\n{F}\n"
print("absolute-path write still flagged:", runcheck.check(ab)[0] is None)
up = f"### FILE: app.py\n{F}python\nopen('../x.txt', 'w')\n{F}\n"
print("parent-dir write still flagged:", runcheck.check(up)[0] is None)
print("force=True runs flagged code:", runcheck.check(evil, force=True)[0] is True)
