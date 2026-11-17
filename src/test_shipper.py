import shipper
B3 = chr(96) * 3
B4 = chr(96) * 4
txt = f"intro\n### FILE: a/b.py\n{B3}python\nprint(1)\n{B3}\n\n### FILE: README.md\n{B4}markdown\n# T\n{B3}bash\nrun\n{B3}\n{B4}\n"
print(shipper.parse_files(txt))
for bad in ["../x.py", "C:/x.py", ".git/config", "a/../../b"]:
    try:
        shipper.safe_rel(bad); print("ALLOWED?!", bad)
    except ValueError:
        print("blocked", bad)
for rel, content in [("sub/.env", "x=1"), ("k.py", "key = 'gsk_" + "a" * 30 + "'")]:
    try:
        shipper.check_secrets(rel, content); print("NOT CAUGHT", rel)
    except ValueError:
        print("blocked", rel)

B2 = chr(96) * 2
bad = f"COMMIT: x\n### FILE: README.md\n{B2} trasladar\n# T\n{B3}bash\nrun\n{B3}\n{B2}\n"
print(repr(shipper.extract_readme(bad)))
print(repr(shipper.extract_readme("COMMIT: x\n### FILE: README.md\n# Plain\nhello\n")))
