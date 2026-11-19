import json, os
from handoff import ROOT

PATH = os.path.join(ROOT, "state", "owner.local.json")  # gitignored via state/*.local.*


def defaults():
    """The owner's standing defaults as a suffix for the goal, or '' when none are set.
    File format: {"language": "Python 3.12 on Windows", "notes": ["short rule", ...]}
    Scalar values render as '- key: value', list items as '- item'."""
    try:
        with open(PATH, encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception:
        return ""
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines += [f"- {x}" for x in v if str(x).strip()]
        elif str(v).strip():
            lines.append(f"- {k}: {v}")
    if not lines:
        return ""
    return "\n\nOWNER STANDING DEFAULTS (apply unless the goal says otherwise):\n" + "\n".join(lines)
