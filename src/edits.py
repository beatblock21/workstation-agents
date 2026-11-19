"""Targeted edits for the Dev fixer: anchored SEARCH/REPLACE blocks instead of whole-file rewrites.

Format the fixer writes:

    ### EDIT: path/to/file.py
    <<<<<<< SEARCH
    exact existing lines
    =======
    replacement lines
    >>>>>>> REPLACE

A SEARCH must match exactly once (trailing whitespace is ignored as a fallback).
Empty SEARCH creates a new file; empty replacement deletes the matched lines.
Each edit is applied independently: good ones land, bad ones are rejected with a reason
so the fixer can retry just those."""
import difflib, os, re
import shipper

HEAD_RE = re.compile(r"^#{2,4}[ \t]*EDIT:[ \t]*`?([^\n`]+?)`?[ \t]*$", re.M)
BLOCK_RE = re.compile(r"<<<<<<< SEARCH[ \t]*\n(.*?)^=======[ \t]*\n(.*?)^>>>>>>> REPLACE", re.S | re.M)
LANG = {".py": "python", ".md": "markdown", ".json": "json", ".toml": "toml", ".html": "html", ".cfg": "ini"}


def _trim(s):
    return s[:-1] if s.endswith("\n") else s


def parse_edits(text):
    """-> list of (path, search, replace), in order of appearance."""
    heads = list(HEAD_RE.finditer(text))
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        for b in BLOCK_RE.finditer(text[h.end():end]):
            out.append((h.group(1).strip(), _trim(b.group(1)), _trim(b.group(2))))
    return out


def _find(lines, s_lines):
    n = len(s_lines)
    if n == 0:
        return []
    ls = [l.rstrip() for l in lines]
    ss = [l.rstrip() for l in s_lines]
    return [i for i in range(len(ls) - n + 1) if ls[i:i + n] == ss]


def apply_edits(files, edits):
    """files: {relpath: text}. Returns (new_files, applied, rejected).
    applied: [(edit_no, relpath)]; rejected: [(edit_no, path, reason)]. Input dict is not modified."""
    files = dict(files)
    applied, rejected = [], []
    for no, (path, search, replace) in enumerate(edits, 1):
        try:
            rel = shipper.safe_rel(path)
        except ValueError as e:
            rejected.append((no, path, str(e)))
            continue
        cur = files.get(rel)
        if search == "":
            if cur is None:
                files[rel] = replace + ("\n" if replace and not replace.endswith("\n") else "")
                applied.append((no, rel))
            else:
                rejected.append((no, rel, "empty SEARCH is only for creating a new file, and this file already exists"))
            continue
        if cur is None:
            rejected.append((no, rel, "file does not exist (use an empty SEARCH to create it)"))
            continue
        n = cur.count(search)
        if n == 1:
            if replace == "" and cur.count(search + "\n") == 1:
                files[rel] = cur.replace(search + "\n", "", 1)
            else:
                files[rel] = cur.replace(search, replace, 1)
            applied.append((no, rel))
            continue
        if n > 1:
            rejected.append((no, rel, f"SEARCH text matches {n} places; include more surrounding lines so it is unique"))
            continue
        lines = cur.split("\n")
        s_lines = search.split("\n")
        hits = _find(lines, s_lines)
        if len(hits) == 1:
            lines[hits[0]:hits[0] + len(s_lines)] = replace.split("\n") if replace != "" else []
            files[rel] = "\n".join(lines)
            applied.append((no, rel))
        elif len(hits) > 1:
            rejected.append((no, rel, f"SEARCH text matches {len(hits)} places (ignoring trailing whitespace); make it unique"))
        else:
            first = next((l.strip() for l in s_lines if l.strip()), "")
            close = difflib.get_close_matches(first, [l.strip() for l in lines if l.strip()], n=1, cutoff=0.6)
            hint = f"; closest existing line: {close[0]!r}" if close else ""
            rejected.append((no, rel, "SEARCH text not found" + hint))
    return files, applied, rejected


def report(applied, rejected):
    lines = [f"EDIT RESULTS: {len(applied)} applied, {len(rejected)} rejected"]
    lines += [f"- edit {no} OK: {rel}" for no, rel in applied]
    lines += [f"- edit {no} REJECTED: {rel}: {why}" for no, rel, why in rejected]
    return "\n".join(lines)


def to_deliverable(files):
    """Render {relpath: text} as '### FILE:' blocks that shipper.parse_files reads back."""
    parts = []
    for rel, content in files.items():
        fence = "```"
        while fence in content:
            fence += "`"
        lang = LANG.get(os.path.splitext(rel)[1].lower(), "")
        parts.append(f"### FILE: {rel}\n{fence}{lang}\n{content.rstrip(chr(10))}\n{fence}")
    return "\n\n".join(parts) + "\n"


def apply_to_deliverable(deliverable, edit_text):
    """Convenience for the pipeline: -> (new_deliverable, report_text, applied, rejected)."""
    files = shipper.parse_files(deliverable)
    new, applied, rejected = apply_edits(files, parse_edits(edit_text))
    return to_deliverable(new), report(applied, rejected), applied, rejected
