import runcheck
F = chr(96) * 3
def blk(code):
    return f"{F}python\n{code}\n{F}"
print(runcheck.check(blk("assert 1 + 1 == 2")))
print(runcheck.check(blk("assert 1 == 2"))[0])
print(runcheck.check(blk("import shutil\nshutil.rmtree('x')")))
print(runcheck.check("no code here"))
