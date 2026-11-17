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
