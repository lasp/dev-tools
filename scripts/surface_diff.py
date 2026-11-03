#!/usr/bin/env python3
"""List what a change removes or renames from a repository's public surface.

Run inside the repository, with the base the change is diffed against. The change is
the diff from the base's merge base with HEAD to the working tree, or, with `--head <rev>`, from
the merge base of the base and `<rev>` to `<rev>` as committed, which reads no working tree. Renames
are detected. A rename removes the old name, so each is listed as the name that is gone. One line
each, `kind · name · file`, with the file at the base, and nothing else; nothing at all when
nothing is removed.

- `name`: in a Python module outside the tests, a public module-level function, class or
  assigned name, including one defined under a module-level `if` or `try` but not under `if
  TYPE_CHECKING:` or `if __name__ == "__main__":`; a public method or class-body attribute (a
  pydantic field, a class constant) of a public class, as `Class.name`, an enum's methods and
  properties included; each string in a module's `__all__`; and the re-exports: in a module that
  defines `__all__`, each name a module-level `import` or `from ... import` binds that `__all__`
  lists, and in a package's `__init__.py` with no `__all__`, each public name such an import
  binds. A name is public when it does not start with `_`.
- `module`: a public Python module deleted or moved, as its dotted path.
- `enum`: a member of a class derived from an `Enum`, `Flag` or `IntFlag` type, as `Class.MEMBER`.
  A member whose value is a string literal carries it as a fourth field, `kind · name · file ·
  value`, since a consumer can use the member by its value; a member whose value changes is
  listed with the old one.
- `identifier`: a member of an enum class the `surface.identifiers` of the repository's standard,
  or of the default profile, names, the same way.
- `option`: a command-line option, a string starting with `-` given to `add_argument` or `option`,
  or a subcommand, the first string given to `add_parser` or `command`.
- `variable`, `attribute`, `dimension`: from a YAML product-definition file, one that matches a
  `--product-defs` glob, by default the profile's `depth.deep`. A file with a top-level
  `variables` or `coordinates` map gives its variables, its global `attributes` and each
  variable's attributes (`VAR.attr`), and the dimensions its variables use; any other such file
  gives its top-level keys as dimensions when its name holds `dimension`, as attributes when it
  holds `attribute`, and nothing otherwise. A removed variable is listed alone, not its
  attributes. With no globs, from the option or the profile, no product definition is read, and
  stderr says so.

It runs from anywhere in the repository; the paths are the top level's.

Exits 1 naming the cause when git fails, the profile is refused, or a Python module, its `__all__`
or a YAML file on either side cannot be read. Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ENUM_BASES = re.compile(r"(Enum|Flag)$")


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SurfaceError(Exception):
    """A file on either side of the diff that cannot be read."""


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True)
    if done.returncode:
        raise SurfaceError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def is_test(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(p in ("tests", "test") for p in parts[:-1]) or parts[-1].startswith("test_") or parts[-1] == "conftest.py"


def public(name: str) -> bool:
    return not name.startswith("_")


def base_name(node: ast.expr) -> str:
    return node.attr if isinstance(node, ast.Attribute) else node.id if isinstance(node, ast.Name) else ""


def assigned(body: list[ast.stmt]) -> list[str]:
    names = []
    for node in body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        names += [t.id for t in targets if isinstance(t, ast.Name)]
    return names


def guard_only(test: ast.expr) -> bool:
    """An `if TYPE_CHECKING:` or `if __name__ == "__main__":` test, whose body is not the surface."""
    if base_name(test) == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Compare) and base_name(test.left) == "__name__"


def module_level(body: list[ast.stmt]) -> list[ast.stmt]:
    """The statements of a module's top level, with those under a module-level `if` or `try`,
    leaving out the bodies of `if TYPE_CHECKING:` and `if __name__ == "__main__":`."""
    out = []
    for node in body:
        if isinstance(node, ast.If) and guard_only(node.test):
            out += module_level(node.orelse)
        elif isinstance(node, ast.If):
            out += module_level(node.body + node.orelse)
        elif isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            out += module_level(node.body + [s for h in node.handlers for s in h.body] + node.orelse + node.finalbody)
        else:
            out.append(node)
    return out


def string_value(node: ast.stmt) -> str:
    value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else ""


def all_entries(node: ast.stmt, where: str) -> list[str]:
    """The strings an `__all__` assignment lists; one that is not a literal list or tuple of
    strings cannot be read."""
    listed = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else None
    if listed is None or not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in listed):
        raise SurfaceError(f"{where}:{node.lineno}: an __all__ that is not a literal list of strings")
    return [e.value for e in listed]


def python_surface(text: str, where: str, identifiers: frozenset[str]) -> set[tuple[str, str, str]]:
    """The (kind, name, value) triples a module exposes: names, enum members with their string
    values, re-exports, and command-line options and subcommands. The value is empty but for an
    enum member whose value is a string literal."""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise SurfaceError(f"{where}: {e}") from e
    out: set[tuple[str, str, str]] = set()
    top = module_level(tree.body)
    listed = None
    for node in top:
        target = node.target if isinstance(node, ast.AugAssign) else None
        if "__all__" in assigned([node]) or (isinstance(target, ast.Name) and target.id == "__all__"):
            listed = (listed or set()) | set(all_entries(node, where))
    out |= {("name", n, "") for n in listed or ()}
    package = PurePosixPath(where).name == "__init__.py"
    for node in top:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and public(node.name):
            out.add(("name", node.name, ""))
        elif isinstance(node, ast.ClassDef) and public(node.name):
            out.add(("name", node.name, ""))
            if any(ENUM_BASES.search(base_name(b)) for b in node.bases):
                kind = "identifier" if node.name in identifiers else "enum"
                out |= {(kind, f"{node.name}.{m}", string_value(item)) for item in node.body for m in assigned([item]) if public(m)}
            else:
                out |= {("name", f"{node.name}.{m}", "") for m in assigned(node.body) if public(m)}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and public(item.name):
                    out.add(("name", f"{node.name}.{item.name}", ""))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound = [a.asname or a.name.split(".")[0] for a in node.names if a.name != "*"]
            out |= {("name", n, "") for n in bound if (n in listed if listed is not None else package and public(n) and n != "TYPE_CHECKING")}
        else:
            out |= {("name", n, "") for n in assigned([node]) if public(n)}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        named = [k.value for k in node.keywords if k.arg == "name"]
        strings = [a.value for a in [*node.args, *named] if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if base_name(node.func) in ("add_argument", "option"):
            out |= {("option", a, "") for a in strings if a.startswith("-")}
        elif base_name(node.func) in ("add_parser", "command") and strings:
            out.add(("option", strings[0], ""))
    return out


def yaml_keys(text: str, where: str, strip_comment) -> dict:
    """The block-mapping keys of a YAML file as nested dicts; a flow or block list as a list of
    strings, and any other value as its text. Enough of YAML for a product definition."""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    last: tuple[dict, str] | None = None
    scalar = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = strip_comment(raw).rstrip()
        if not line.strip() or line.strip() in ("---", "..."):
            continue
        indent, body = len(line) - len(line.lstrip(" ")), line.strip()
        # The lines of a `|` or `>` block scalar are its text, not keys.
        if scalar is not None and indent > scalar:
            continue
        scalar = None
        if body.startswith("- "):
            if last is None or not (last[0][last[1]] == {} or isinstance(last[0][last[1]], list)):
                raise SurfaceError(f"{where}:{n}: a list item with no key above it")
            if last[0][last[1]] == {}:
                last[0][last[1]] = []
            last[0][last[1]].append(body[2:].strip().strip("'\""))
            continue
        m = re.match(r"""(['"]?)([^'":]+)\1:(?:\s+(.*))?$""", body)
        if not m:
            raise SurfaceError(f"{where}:{n}: a line the reader does not read: {body!r}")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        key, rest = m.group(2).strip(), (m.group(3) or "").strip()
        if rest.startswith("["):
            parent[key] = [v.strip().strip("'\"") for v in rest.strip("[]").split(",") if v.strip()]
        elif rest:
            parent[key] = rest
            if re.fullmatch(r"[|>][-+]?", rest):
                scalar = indent
        else:
            parent[key] = {}
            stack.append((indent, parent[key]))
        last = (parent, key)
    return root


def yaml_surface(text: str, path: str, strip_comment) -> set[tuple[str, str]]:
    name = PurePosixPath(path).name
    defines = re.search(r"^(variables|coordinates):", text, re.M)
    if not (defines or "dimension" in name or "attribute" in name):
        return set()
    data = yaml_keys(text, path, strip_comment)
    out: set[tuple[str, str]] = set()
    if defines:
        if isinstance(data.get("attributes"), dict):
            out |= {("attribute", a) for a in data["attributes"]}
        for section in ("variables", "coordinates"):
            for var, spec in (data.get(section) or {}).items():
                out.add(("variable", var))
                if isinstance(spec, dict):
                    if isinstance(spec.get("attributes"), dict):
                        out |= {("attribute", f"{var}.{a}") for a in spec["attributes"]}
                    if isinstance(spec.get("dimensions"), list):
                        out |= {("dimension", d) for d in spec["dimensions"]}
    elif "dimension" in name:
        out |= {("dimension", k) for k in data}
    elif "attribute" in name:
        out |= {("attribute", k) for k in data}
    return out


def module_name(path: str) -> str:
    p = PurePosixPath(path)
    parts = p.parent.parts if p.name == "__init__.py" else (*p.parent.parts, p.stem)
    return ".".join(parts)


def removed(base: str, globs: list[str], identifiers: frozenset[str], head: str | None = None) -> list[tuple[str, str, str, str]]:
    floor, profile = load("depth_floor"), load("profile")
    mb = git("merge-base", base, head or "HEAD").strip()
    # git names the paths from the top level, wherever this runs.
    top = Path(git("rev-parse", "--show-toplevel").strip())
    patterns = [floor.glob_regex(g) for g in globs]
    out: list[tuple[str, str, str, str]] = []
    # depth_floor's flags, with renames detected, and -z so a path comes back unquoted.
    diff = [f for f in floor.DIFF if f != "--no-renames"]
    fields = git(*diff, "-M", "--name-status", "-z", mb, *([head] if head else [])).split("\0")[:-1]
    while fields:
        status = fields.pop(0)
        paths = [fields.pop(0) for _ in range(2 if status[0] in "RC" else 1)]
        if status[0] not in "DMR":
            continue
        old, new = paths[0], paths[-1]
        if old.endswith(".py") and not is_test(old):
            kind = "python"
        elif old.endswith((".yml", ".yaml")) and any(p.match(old) for p in patterns):
            kind = "yaml"
        else:
            continue
        before = git("show", f"{mb}:{old}")
        if status[0] == "D":
            after = ""
        elif head:
            after = git("show", f"{head}:{new}")
        elif (top / new).is_file():
            after = (top / new).read_text()
        else:
            raise SurfaceError(f"{new}: in the diff but not in the working tree")
        if kind == "python":
            if (status[0] == "D" or old != new) and all(public(p) or p == "__init__.py" for p in PurePosixPath(old).parts):
                out.append(("module", module_name(old), old, ""))
            gone = python_surface(before, old, identifiers) - python_surface(after, new, identifiers)
        else:
            gone = yaml_surface(before, old, profile.strip_comment) - yaml_surface(after, new, profile.strip_comment)
            dropped = {n for k, n in gone if k == "variable"}
            gone = {(k, n, "") for k, n in gone if not (k == "attribute" and n.split(".")[0] in dropped)}
        out += [(k, n, old, v) for k, n, v in gone]
    return sorted(set(out), key=lambda t: (t[2], t[0], t[1], t[3]))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("base", help="the commit or branch the change is diffed against")
    p.add_argument("--product-defs", action="append", metavar="GLOB", help="a product-definition glob; by default the profile's depth.deep")
    p.add_argument("--repo", help="owner/repo; by default the origin remote's")
    p.add_argument("--head", metavar="REV", help="diff to this commit as committed, not to the working tree")
    args = p.parse_args(argv)
    profile = load("profile")
    try:
        globs, repo = args.product_defs, args.repo
        if globs is None:
            repo = repo or re.sub(r"\.git$", "", git("remote", "get-url", "origin").strip()).replace(":", "/")
            deep = profile.resolve(repo, ROOT)["depth"]
            globs = [] if deep == "not yet recorded" or deep["deep"] == "not yet recorded" else deep["deep"]
        if not globs:
            print("surface_diff.py: product definitions not read: the profile names no depth.deep globs", file=sys.stderr)
        identifiers = frozenset(profile.defaults(ROOT, repo)["surface"]["identifiers"])
        lines = removed(args.base, globs, identifiers, args.head)
    except (SurfaceError, OSError, profile.ProfileError) as e:
        print(f"surface_diff.py: {e}", file=sys.stderr)
        return 1
    for kind, name, path, value in lines:
        print(f"{kind} · {name} · {path}" + (f" · {value}" if value else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
