"""Compact map of a Python project for long-project work: files, classes, function signatures, docstring first lines.
Agents get the map plus only the relevant full files (select_files), so the context stays small as projects grow."""
import ast, os, re

TEXT_EXT = {".py", ".md", ".json", ".toml", ".txt", ".cfg"}
SKIP_DIRS = {"__pycache__", "node_modules"}
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def load_dir(path, max_bytes=200_000):
    """{relative/path: text} for the text files of a project folder (hidden and cache folders skipped)."""
    files = {}
    for root, dirs, names in os.walk(path):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS)
        for n in sorted(names):
            full = os.path.join(root, n)
            if os.path.splitext(n)[1].lower() in TEXT_EXT and os.path.getsize(full) <= max_bytes:
                try:
                    with open(full, encoding="utf-8") as f:
                        files[os.path.relpath(full, path).replace(os.sep, "/")] = f.read()
                except (OSError, UnicodeDecodeError):
                    pass
    return files


def _is_test(path):
    return os.path.basename(path).startswith("test_") or path.startswith("tests/")


def _first_line(doc):
    lines = (doc or "").strip().splitlines()
    return lines[0][:100] if lines else ""


def _doc_suffix(node):
    d = _first_line(ast.get_docstring(node))
    return f"  # {d}" if d else ""


def _sig(node):
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix}{node.name}({ast.unparse(node.args)}){ret}"


def build_map(files):
    """Text map of {path: source}: one line per class and function (signature plus docstring first line)."""
    lines = [f"PROJECT MAP ({len(files)} files)"]
    for path in sorted(files):
        src = files[path]
        head = f"{path} ({len(src.splitlines())} lines)"
        if not path.endswith(".py"):
            lines.append(head)
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            lines.append(f"{head} UNPARSEABLE: {e.msg} at line {e.lineno}")
            continue
        lines.append(head)
        doc = _first_line(ast.get_docstring(tree))
        if doc:
            lines.append(f"  {doc}")
        if _is_test(path):
            names = [x.name for x in tree.body if isinstance(x, FUNCS) and x.name.startswith("test")]
            extra = f" (+{len(names) - 12} more)" if len(names) > 12 else ""
            lines.append("  tests: " + (", ".join(names[:12]) + extra if names else "(none found)"))
            continue
        consts = [t.id for x in tree.body if isinstance(x, ast.Assign) for t in x.targets if isinstance(t, ast.Name)]
        if consts:
            lines.append("  names: " + ", ".join(consts[:10]))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = f"({', '.join(ast.unparse(b) for b in node.bases)})" if node.bases else ""
                lines.append(f"  class {node.name}{bases}" + _doc_suffix(node))
                lines += [f"    {_sig(sub)}" + _doc_suffix(sub) for sub in node.body if isinstance(sub, FUNCS)]
            elif isinstance(node, FUNCS):
                lines.append(f"  {_sig(node)}" + _doc_suffix(node))
    return "\n".join(lines)


def _words(text):
    out = set()
    for p in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", text.replace("_", " ")):
        w = p.lower()
        if len(w) > 2:
            out.add(w)
            if w.endswith("s") and len(w) > 3:
                out.add(w[:-1])
    return out


def _identifiers(src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    return [n.name for n in ast.walk(tree) if isinstance(n, (ast.ClassDef,) + FUNCS)]


def select_files(files, request, max_chars=12000):
    """The files worth sending in full for a change request: those whose path or identifiers match the request
    (a file named in the request scores extra), plus the tests of the chosen modules. A vague request that matches
    nothing falls back to the smallest files that fit."""
    req = _words(request)
    scores = {}
    for p, src in files.items():
        s = len(req & _words(p + " " + " ".join(_identifiers(src))))
        stem = os.path.splitext(os.path.basename(p))[0].lower()
        if os.path.basename(p) in request or (len(stem) >= 4 and re.search(r"\b" + re.escape(stem) + r"\b", request.lower())):
            s += 5
        scores[p] = s
    chosen, used = {}, 0
    if max(scores.values(), default=0) == 0:
        order = sorted(files, key=lambda p: len(files[p]))
    else:
        order = sorted(files, key=lambda p: (-scores[p], len(files[p])))
    for p in order:
        if chosen and (scores[p] == 0 and max(scores.values()) > 0):
            break
        if chosen and used + len(files[p]) > max_chars:
            continue
        chosen[p] = files[p]
        used += len(files[p])
    for p in list(chosen):
        stem = os.path.splitext(os.path.basename(p))[0]
        for q in files:
            if os.path.basename(q) == f"test_{stem}.py" and q not in chosen and used + len(files[q]) <= max_chars * 1.5:
                chosen[q] = files[q]
                used += len(files[q])
    return chosen
