"""Test each claim against what the project really has."""
from __future__ import annotations

import posixpath
from dataclasses import dataclass, field, asdict

from .claims import GENERATED, extract
from .facts import load_facts
from .find import instruction_files

ERROR = "error"
WARN = "warn"


@dataclass
class Finding:
    level: str
    file: str
    line: int
    code: str
    said: str       # the words in the file
    message: str    # what is actually true, in plain words


@dataclass
class Result:
    root: str
    files: list
    findings: list = field(default_factory=list)
    unchecked: dict = field(default_factory=dict)   # reason -> how many claims were left alone
    copies: dict = field(default_factory=dict)      # a file that is word for word the same as another in its folder

    def counts(self):
        return (sum(f.level == ERROR for f in self.findings), sum(f.level == WARN for f in self.findings))

    def to_dict(self):
        errors, warnings = self.counts()
        return {"root": self.root, "files": self.files, "errors": errors, "warnings": warnings,
                "findings": [asdict(f) for f in self.findings], "not_checked": self.unchecked, "copies": self.copies}


def _skip_path(path, facts):
    parts = [p for p in path.strip("/").split("/") if p not in ("", ".", "..")]
    if not parts:
        return True
    if any(p in GENERATED or p in facts.ignored for p in parts):
        return True
    if parts[-1].startswith(".env") or parts[-1].endswith(".log"):
        return True
    return False


def _candidates(path, base_dir):
    """Where a path could point: from the project root, or from the folder the instruction file is in."""
    p = path[2:] if path.startswith("./") else path
    found = {posixpath.normpath(p)}
    if base_dir:
        found.add(posixpath.normpath(posixpath.join(base_dir, p)))
    return {c for c in found if not c.startswith("..")}


def _exists(path, base_dir, facts):
    """True when the path points at something real, allowing for the habit of writing paths from a sub-folder."""
    wants_dir = path.endswith("/")
    bare = "/" not in path.strip("/")
    for candidate in _candidates(path, base_dir):
        if candidate == "." or candidate in facts.files or candidate in facts.dirs:
            return True
        if wants_dir and any(d.endswith("/" + candidate) for d in facts.dirs):
            return True
        if not wants_dir:
            if any(f.endswith("/" + candidate) for f in facts.files):
                return True  # written from a sub-folder, for example components/a.tsx for src/components/a.tsx
            if bare and any(n for n in facts.by_name if n == candidate):
                return True
            stem = candidate + "."
            if "." not in candidate.rsplit("/", 1)[-1] and any(f.startswith(stem) or ("/" + stem) in f for f in facts.files):
                return True  # src/be/db for src/be/db.ts
    return False


def _list(names, limit=6):
    names = sorted(names)
    shown = ", ".join(names[:limit])
    return shown + (f" and {len(names) - limit} more" if len(names) > limit else "") if names else "none"


def check_file(rel, text, facts, result, seen):
    base_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
    scope = facts.at(base_dir)
    claims = extract(text.splitlines(), facts)
    used_managers = {}
    tests = set()
    for c in claims:
        here = (rel, c.line, c.kind, c.text)
        if here in seen:
            continue
        seen.add(here)
        add = lambda level, code, msg: result.findings.append(Finding(level, rel, c.line, code, c.text, msg))
        skip = lambda why: result.unchecked.__setitem__(why, result.unchecked.get(why, 0) + 1)

        if c.kind == "skipped":
            skip(f"commands that {c.data['why']}")
        elif c.kind == "manager":
            used_managers.setdefault(c.data["manager"], (c.line, c.text))
        elif c.kind == "test":
            tests.add(c.data["command"])
        elif c.kind == "script":
            if scope.scripts is None:
                skip("package commands (there is no package.json at the project root)")
            elif c.data["script"] not in scope.scripts and c.data["script"] not in facts.scripts_above(base_dir):
                if scope.has_workspaces:
                    skip("package commands in a project with workspaces (the script may live in a sub-package)")
                else:
                    have = _list(scope.scripts) if scope.scripts else "no scripts at all"
                    add(ERROR, "script-missing", f"package.json has no \"{c.data['script']}\" script. It has: {have}.")
        elif c.kind == "make":
            if scope.make_targets is None:
                skip("make commands (there is no Makefile at the project root)")
            elif c.data["target"] not in scope.make_targets:
                add(ERROR, "make-missing", f"the Makefile has no \"{c.data['target']}\" target. It has: {_list(scope.make_targets)}.")
        elif c.kind in ("path", "import"):
            path = c.data["path"]
            if _skip_path(path, facts) or path.startswith("~"):
                continue
            if _exists(path, base_dir, facts):
                continue
            name = path.rstrip("/").rsplit("/", 1)[-1]
            elsewhere = [p for p in facts.by_name.get(name, []) if not _skip_path(p, facts)] if not path.endswith("/") else \
                [d for d in facts.dirs if d.endswith("/" + name) and not _skip_path(d, facts)]
            if c.kind == "import":
                add(ERROR, "import-missing", "this file is imported but it is not there, so the agent never sees it."
                    + (f" A file with that name is at {elsewhere[0]}." if len(elsewhere) == 1 else ""))
            elif len(elsewhere) == 1:
                add(WARN, "path-moved", f"that is not there any more. {'A folder' if path.endswith('/') else 'A file'} with that name is at {elsewhere[0]}.")
            elif len(elsewhere) > 1:
                add(WARN, "path-moved", f"that is not there. {len(elsewhere)} with that name exist elsewhere, for example {sorted(elsewhere)[0]}.")
            else:
                add(WARN, "path-missing", "that is not in the project.")
        elif c.kind == "node":
            major, floor = c.data["major"], c.data["floor"]
            if scope.node_exact is not None and not floor and major != scope.node_exact:
                add(ERROR, "node-mismatch", f"the project pins Node {scope.node_exact} (in .nvmrc or .node-version).")
            elif scope.node_floor is not None and not floor and major < scope.node_floor:
                add(ERROR, "node-too-old", f"package.json says it needs Node {scope.node_floor} or newer.")
        elif c.kind == "python":
            version, floor = c.data["version"], c.data["floor"]
            if scope.python_exact is not None and not floor and version != scope.python_exact:
                add(ERROR, "python-mismatch", f"the project pins Python {scope.python_exact[0]}.{scope.python_exact[1]}.")
            elif scope.python_floor is not None and not floor and version < scope.python_floor:
                add(ERROR, "python-too-old", f"pyproject.toml says it needs Python {scope.python_floor[0]}.{scope.python_floor[1]} or newer.")
    return used_managers, tests


def check_project(root) -> Result:
    facts = load_facts(root)
    files = instruction_files(facts)
    result = Result(root=str(facts.root), files=files)
    seen = set()
    by_file = {}
    texts = {}
    for rel in files:
        try:
            text = (facts.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        key = (rel.rsplit("/", 1)[0] if "/" in rel else "", text)
        if key in texts:
            result.copies[rel] = texts[key]  # the same words in the same folder: say it once
            continue
        texts[key] = rel
        by_file[rel] = check_file(rel, text, facts, result, seen)

    def project_managers(rel):
        scope = facts.at(rel.rsplit("/", 1)[0] if "/" in rel else "")
        return {scope.package_manager} if scope.package_manager else set(scope.lockfile_managers)

    for rel, (managers, _) in by_file.items():
        project = project_managers(rel)
        if project:
            for manager, (line, said) in managers.items():
                if manager not in project:
                    result.findings.append(Finding(
                        WARN, rel, line, "manager-mismatch", said,
                        f"the project uses {_list(project)} (see its lock file{'s' if len(project) > 1 else ''}), not {manager}."))
    names = sorted(by_file)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ma, mb = set(by_file[a][0]), set(by_file[b][0])
            if ma and mb and not (ma & mb) and not project_managers(a) and not project_managers(b):
                result.findings.append(Finding(WARN, b, min(v[0] for v in by_file[b][0].values()), "files-disagree-manager", _list(mb),
                                               f"{a} uses {_list(ma)}, but this file uses {_list(mb)}."))
            ta, tb = by_file[a][1], by_file[b][1]
            if ta and tb and not (ta & tb):
                result.findings.append(Finding(WARN, b, 1, "files-disagree-test", _list(tb),
                                               f"{a} runs tests with {_list(ta)}, but this file says {_list(tb)}."))
    result.findings.sort(key=lambda f: (f.file, f.line, f.level != ERROR, f.code))
    return result
