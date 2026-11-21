"""Harder, edge-rich benchmark goals. Importing this module adds them to bench_goals.GOALS.
Hidden tests are never shown to any model."""
from bench_goals import GOALS, _HEAD, _TAIL

_RAISES = r'''
def raises(f):
    try:
        f()
    except ValueError:
        return
    except BaseException as e:
        raise AssertionError("wrong exception " + repr(e))
    raise AssertionError("no ValueError raised")
'''

_DURATION = r'''
try:
    from duration import parse_duration
except BaseException as e:
    print("CHECK FAIL: import: " + repr(e)[:150])
    sys.exit(1)
check("hours and minutes", lambda: eq(parse_duration("1h30m"), 5400))
check("days", lambda: eq(parse_duration("2d"), 172800))
check("seconds", lambda: eq(parse_duration("45s"), 45))
check("all four parts with spaces", lambda: eq(parse_duration("1d 2h 3m 4s"), 93784))
check("case and whitespace ignored", lambda: eq(parse_duration("  10M  "), 600))
check("zero", lambda: eq(parse_duration("0s"), 0))
check("repeated unit rejected", lambda: raises(lambda: parse_duration("1h 1h")))
check("out of order rejected", lambda: raises(lambda: parse_duration("30m1h")))
check("empty rejected", lambda: raises(lambda: parse_duration("")))
check("bare number rejected", lambda: raises(lambda: parse_duration("5")))
check("missing number rejected", lambda: raises(lambda: parse_duration("h")))
check("negative rejected", lambda: raises(lambda: parse_duration("-5s")))
check("unknown unit rejected", lambda: raises(lambda: parse_duration("1x")))
check("trailing number rejected", lambda: raises(lambda: parse_duration("1h30")))
'''

_CSV = r'''
try:
    from csvline import parse_line
except BaseException as e:
    print("CHECK FAIL: import: " + repr(e)[:150])
    sys.exit(1)
check("simple", lambda: eq(parse_line("a,b,c"), ["a", "b", "c"]))
check("single field", lambda: eq(parse_line("abc"), ["abc"]))
check("quoted comma", lambda: eq(parse_line('"a,b",c'), ["a,b", "c"]))
check("escaped quote", lambda: eq(parse_line('"he said ""hi""",x'), ['he said "hi"', "x"]))
check("empty line", lambda: eq(parse_line(""), [""]))
check("trailing comma", lambda: eq(parse_line("a,b,"), ["a", "b", ""]))
check("empty fields", lambda: eq(parse_line(",,"), ["", "", ""]))
check("whitespace preserved", lambda: eq(parse_line(" a , b "), [" a ", " b "]))
check("empty quoted field", lambda: eq(parse_line('"",x'), ["", "x"]))
check("lone escaped quote", lambda: eq(parse_line('""""'), ['"']))
check("unterminated quote", lambda: raises(lambda: parse_line('"abc')))
'''

GOALS.update({
    "duration": {
        "goal": ("Write a Python module duration.py with a function parse_duration(text) that converts a duration string into a "
                 "whole number of seconds. Accepted: one or more number+unit parts, written together or separated by spaces, with "
                 "units d (days), h (hours), m (minutes), s (seconds), for example 1h30m, 2d, 45s, 1d 2h 3m 4s. Units must appear "
                 "in the order d, h, m, s and each at most once. Matching is case-insensitive and surrounding whitespace is ignored. "
                 "Anything else (empty string, unknown unit, missing number, repeated or out-of-order units, negative numbers, a "
                 "bare number without a unit) raises ValueError. Standard library only. Put plain-assert tests in a separate test file."),
        "hidden": _HEAD + _RAISES + _DURATION + _TAIL,
    },
    "csv": {
        "goal": ("Write a Python module csvline.py with a function parse_line(line) that splits one CSV line into a list of string "
                 "fields. Fields are separated by commas. A field may be wrapped in double quotes, in which case commas inside it do "
                 "not split it, and two double quotes inside a quoted field mean one literal double quote. Quotes are removed from "
                 "the output. An empty line gives a list with one empty string, and a trailing comma gives a final empty field. "
                 "Whitespace is preserved exactly. A quoted field that is never closed raises ValueError. Do not use the csv module. "
                 "Standard library only. Put plain-assert tests in a separate test file."),
        "hidden": _HEAD + _RAISES + _CSV + _TAIL,
    },
})
