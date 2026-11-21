"""What is actually true about a project, read from its own files. No guessing, nothing is run."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target",
    ".tox", "coverage", ".mypy_cache", ".pytest_cache", ".cache", ".turbo", ".idea",
}
MAX_FILES = 30000
MAX_DEPTH = 8

LOCKFILES = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lock": "bun",
    "bun.lockb": "bun",
}


@dataclass
class Facts:
    root: Path
    files: set = field(default_factory=set)        # repo-relative, forward slashes
    dirs: set = field(default_factory=set)
    by_name: dict = field(default_factory=dict)    # file name -> [relative paths]
    scripts: object = None                          # dict of package.json scripts, or None when there is no package.json
    has_workspaces: bool = False
    package_manager: object = None                  # from the "packageManager" field, e.g. "pnpm"
    lockfile_managers: set = field(default_factory=set)
    make_targets: object = None                     # set of Makefile targets, or None when there is no Makefile
    node_floor: object = None                       # lowest Node major the project says it needs
    node_exact: object = None                       # the one Node major pinned by .nvmrc and friends
    python_floor: object = None                     # (major, minor)
    python_exact: object = None
    ignored: set = field(default_factory=set)       # plain names from .gitignore
    scopes: dict = field(default_factory=dict)      # folder -> Scope, for each folder with its own package.json, Makefile and so on

    def scripts_above(self, rel_dir: str) -> set:
        """Every script name defined in this folder's package.json or in any folder above it."""
        parts = rel_dir.split("/") if rel_dir else []
        out = set()
        for folder in ["/".join(parts[:i]) for i in range(len(parts), 0, -1)] + [""]:
            scope = self.scopes.get(folder)
            if scope is not None and isinstance(scope.scripts, dict):
                out.update(scope.scripts)
        return out

    def at(self, rel_dir: str) -> "Scope":
        """What applies in a folder: each setting comes from the nearest folder at or above it that has one."""
        merged = Scope()
        parts = rel_dir.split("/") if rel_dir else []
        folders = ["/".join(parts[:i]) for i in range(len(parts), 0, -1)] + [""]
        for attr in ("scripts", "make_targets", "node_floor", "node_exact", "python_floor", "python_exact", "package_manager"):
            for folder in folders:
                scope = self.scopes.get(folder)
                if scope is not None and getattr(scope, attr) is not None:
                    setattr(merged, attr, getattr(scope, attr))
                    if attr == "scripts":
                        merged.has_workspaces = scope.has_workspaces
                    break
        for folder in folders:
            scope = self.scopes.get(folder)
            if scope is not None and scope.lockfile_managers:
                merged.lockfile_managers = set(scope.lockfile_managers)
                break
        return merged


def _read(path: Path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _json(path: Path):
    text = _read(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _major(text):
    m = re.match(r"^\s*v?(\d{1,3})", text or "")
    return int(m.group(1)) if m else None


def _node_floor(spec):
    if not isinstance(spec, str):
        return None
    m = re.search(r"(?:>=|\^|~|>)\s*v?(\d{1,3})", spec) or re.match(r"^\s*v?(\d{1,3})(?:\.|\s|$)", spec)
    return int(m.group(1)) if m else None


def _py_version(text):
    m = re.search(r"(\d)\.(\d{1,2})", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


SCOPE_FILES = {"package.json", "Makefile", "makefile", "GNUmakefile", ".nvmrc", ".node-version", ".tool-versions",
               "pyproject.toml", ".python-version"}


@dataclass
class Scope:
    """What one folder says about itself: its scripts, its lock file, the versions it pins."""
    scripts: object = None
    has_workspaces: bool = False
    package_manager: object = None
    lockfile_managers: set = field(default_factory=set)
    make_targets: object = None
    node_floor: object = None
    node_exact: object = None
    python_floor: object = None
    python_exact: object = None


def _scope(root: Path, rel_dir: str, names) -> Scope:
    here = root / rel_dir if rel_dir else root
    scope = Scope()
    for name, manager in LOCKFILES.items():
        if name in names:
            scope.lockfile_managers.add(manager)

    pkg = _json(here / "package.json") if "package.json" in names else None
    if pkg is not None:
        scripts = pkg.get("scripts")
        scope.scripts = scripts if isinstance(scripts, dict) else {}
        scope.has_workspaces = bool(pkg.get("workspaces"))
        pm = pkg.get("packageManager")
        if isinstance(pm, str):
            scope.package_manager = pm.split("@")[0]
        engines = pkg.get("engines")
        if isinstance(engines, dict):
            scope.node_floor = _node_floor(engines.get("node"))

    for name in (".nvmrc", ".node-version"):
        if name in names:
            scope.node_exact = _major(_read(here / name))
            break

    tool_versions = _read(here / ".tool-versions") if ".tool-versions" in names else None
    for line in (tool_versions or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("nodejs", "node") and scope.node_exact is None:
            scope.node_exact = _major(parts[1])
        if len(parts) >= 2 and parts[0] == "python" and scope.python_exact is None:
            scope.python_exact = _py_version(parts[1])

    if "pyproject.toml" in names:
        m = re.search(r'requires-python\s*=\s*"([^"]+)"', _read(here / "pyproject.toml") or "")
        if m and re.search(r">=?\s*\d", m.group(1)):
            scope.python_floor = _py_version(m.group(1))
    if ".python-version" in names and scope.python_exact is None:
        scope.python_exact = _py_version(_read(here / ".python-version"))

    for name in ("Makefile", "makefile", "GNUmakefile"):
        if name in names:
            targets = set()
            for line in (_read(here / name) or "").splitlines():
                m = re.match(r"^([A-Za-z0-9_%.][A-Za-z0-9_.%\- ]*?)\s*:(?![=:])", line)
                if m and not m.group(1).startswith("."):
                    targets.update(t for t in m.group(1).split() if "%" not in t)
            scope.make_targets = targets
            break
    return scope


def load_facts(root) -> Facts:
    root = Path(root).resolve()
    facts = Facts(root=root)
    count = 0
    for dirpath, dirs, names in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        depth = 0 if rel_dir == "." else rel_dir.count("/") + 1
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (depth >= MAX_DEPTH))
        if rel_dir != ".":
            facts.dirs.add(rel_dir)
        for name in sorted(names):
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            facts.files.add(rel)
            facts.by_name.setdefault(name, []).append(rel)
            count += 1
        if count >= MAX_FILES:
            break

    for rel_dir in sorted({r.rsplit("/", 1)[0] if "/" in r else "" for r in facts.files}):
        names = {r.rsplit("/", 1)[-1] for r in facts.files if (r.rsplit("/", 1)[0] if "/" in r else "") == rel_dir}
        if names & SCOPE_FILES or names & set(LOCKFILES):
            facts.scopes[rel_dir] = _scope(root, rel_dir, names)
    top = facts.scopes.get("")
    if top is not None:
        for attr in ("scripts", "has_workspaces", "package_manager", "lockfile_managers", "make_targets",
                     "node_floor", "node_exact", "python_floor", "python_exact"):
            setattr(facts, attr, getattr(top, attr))

    for line in (_read(root / ".gitignore") or "").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "!")) and not re.search(r"[*?\[]", line):
            facts.ignored.add(line.strip("/"))
    return facts
