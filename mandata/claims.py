"""Pull out the things an instruction file says that can be tested against the project.

Only three kinds of text are read as claims, because that is where precise statements live:
commands in code, file paths in inline code or links, and version numbers. Ordinary prose is left alone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

KNOWN_EXT = {
    "ts", "tsx", "js", "jsx", "mjs", "cjs", "py", "md", "mdx", "mdc", "json", "yml", "yaml", "toml", "sh",
    "go", "rs", "rb", "java", "kt", "swift", "css", "scss", "html", "txt", "cfg", "ini", "sql", "vue", "svelte",
    "lock", "xml", "ipynb", "tf", "c", "h", "cpp",
}
BUILTINS = {
    "npm": {"install", "i", "ci", "init", "publish", "pack", "audit", "update", "up", "uninstall", "un", "remove",
            "link", "exec", "x", "version", "view", "ls", "list", "outdated", "prune", "rebuild", "cache", "config",
            "help", "login", "logout", "whoami", "pkg", "doctor", "fund", "dedupe", "explain", "search", "set",
            "get", "unlink", "access", "adduser", "bugs", "completion", "deprecate", "diff", "dist-tag", "docs",
            "edit", "hook", "org", "owner", "ping", "prefix", "profile", "query", "repo", "root", "sbom",
            "shrinkwrap", "star", "stars", "team", "token", "unpublish", "run-script", "stop", "restart", "start"},
    "pnpm": {"install", "i", "add", "remove", "rm", "update", "up", "upgrade", "run", "exec", "dlx", "link",
             "unlink", "list", "ls", "outdated", "prune", "publish", "pack", "audit", "init", "config", "store",
             "why", "create", "import", "rebuild", "patch", "licenses", "env", "fetch", "deploy", "setup", "self-update",
             "start", "test", "t", "help", "root", "bin", "dedupe", "doctor", "recursive", "multi", "m"},
    "yarn": {"install", "add", "remove", "upgrade", "up", "run", "exec", "dlx", "link", "unlink", "list", "outdated",
             "publish", "pack", "audit", "init", "config", "cache", "why", "create", "import", "version", "info",
             "workspace", "workspaces", "global", "bin", "help", "set", "plugin", "node", "dedupe", "constraints",
             "start", "test"},
    "bun": {"install", "i", "add", "remove", "rm", "update", "run", "x", "link", "unlink", "pm", "init", "create",
            "build", "test", "upgrade", "repl", "dev", "start", "outdated", "publish", "patch", "help", "audit", "why"},
}
WORKSPACE_HINTS = re.compile(r"(--filter|--workspace|-w\s|--prefix|-C\s|--cwd|--dir|\bcd\s)")
GENERATED = {"node_modules", "dist", "build", "out", "coverage", ".venv", "venv", "__pycache__", "target", ".next",
             ".cache", "tmp", ".git"}
NOT_A_PATH = {"and/or", "either/or", "yes/no", "true/false", "input/output", "read/write", "client/server", "ci/cd", "i/o",
              "tcp/ip", "w/o", "n/a", "24/7", "on/off", "pass/fail", "start/stop", "add/remove", "before/after",
              "requests/responses", "he/she", "s/he", "key/value", "src/dest", "os/arch", "date/time"}

CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
IMPORT = re.compile(r"(?:^|(?<=\s))@([A-Za-z0-9_./~-]+\.(?:md|mdx|txt|json|ya?ml|mdc))(?=$|[\s.,;:)])")
NODE = re.compile(r"\bnode(?:\.js)?\s*(?:v|version\s*)?(\d{1,2})(?:\.\d+)*(\s*\+|\s*or\s+(?:newer|later|higher))?", re.I)
PYTHON = re.compile(r"\bpython\s*(?:v|version\s*)?(3)\.(\d{1,2})(?:\.\d+)*(\s*\+|\s*or\s+(?:newer|later|higher))?", re.I)
NODE_CMD = re.compile(r"\b(npm|pnpm|yarn|bun)\s+(run(?:-script)?\s+)?([A-Za-z0-9][A-Za-z0-9:_.\-]*)")
MAKE_CMD = re.compile(r"(?:^|[\s;&|(])make\s+((?:-\S+\s+)*)([A-Za-z0-9_][A-Za-z0-9_.\-]*)(?![=\w])")
TEST_CMD = re.compile(
    r"\b(pytest|unittest|jest|vitest|cargo test|go test|deno test|(?:npm|pnpm|yarn|bun)(?: run)? test|make test)\b")


@dataclass
class Claim:
    kind: str            # script | make | path | import | node | python | manager | test
    line: int
    text: str            # the words as written, for the report
    data: dict = field(default_factory=dict)


def _segments(lines):
    """Yield (line_number, code_text, in_fence, prose_text) for each line."""
    fenced = False
    for n, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            yield n, stripped, True, ""
        else:
            spans = CODE_SPAN.findall(raw)
            yield n, "\n".join(spans), False, CODE_SPAN.sub(" ", raw)


def _clean_command(code):
    return re.sub(r"^\s*(?:\$|>|#)\s*", "", code)


def _path_like(token, facts):
    token = token.strip().strip("\"'").rstrip(".,;:)")
    token = re.sub(r":\d+(?:-\d+)?$", "", token)
    if not token or token.startswith(("-", "~", "/", "http", "#")) or "://" in token or "\\" in token:
        return None
    if token.startswith("@") or re.search(r"N{3,}|X{3,}|Y{4}", token):
        return None
    if re.search(r"[<>{}$*?|=\s]|\.\.\.", token) or token.lower() in NOT_A_PATH or token.startswith("path/to"):
        return None
    if re.match(r"^\d+(\.\d+)+$", token):
        return None
    if not re.match(r"^[\w@.+\-]+(?:/[\w@.+\-]+)*/?$", token):
        return None
    ext = token.rsplit(".", 1)[-1].lower() if "." in token.rsplit("/", 1)[-1] else ""
    if token.endswith("/"):
        return token
    if ext in KNOWN_EXT:
        return token
    if "/" in token:
        first = token.split("/", 1)[0]
        if first in facts.dirs or first == "..":
            return token
    return None


def extract(lines, facts) -> list:
    claims = []
    for n, code, fenced, prose in _segments(lines):
        for part in code.split("\n"):
            command = _clean_command(part)
            if not command:
                continue
            _commands(claims, n, command, facts)
        if fenced:
            continue
        for part in code.split("\n"):
            tokens = part.split()
            for token in tokens:
                if len(tokens) > 1 and "/" not in token:
                    continue  # in a longer snippet a bare word like "bar.ts" is too often not a file
                path = _path_like(token, facts)
                if path:
                    claims.append(Claim("path", n, token.strip("\"'").rstrip(".,;:)"), {"path": path}))
        raw = prose
        for m in LINK.finditer(raw):
            path = _path_like(m.group(1), facts)
            if path:
                claims.append(Claim("path", n, m.group(1), {"path": path}))
        for m in IMPORT.finditer(raw):
            claims.append(Claim("import", n, "@" + m.group(1), {"path": m.group(1)}))
        _versions(claims, n, prose + " " + code)
    return claims


def _commands(claims, n, command, facts):
    aimed_elsewhere = WORKSPACE_HINTS.search(command)
    first = re.search(r"\b(npm|pnpm|yarn|bun)\s+\S", command)
    if aimed_elsewhere and first:
        claims.append(Claim("skipped", n, command.strip()[:60], {"why": "point at a different folder or workspace"}))
    for m in ([] if aimed_elsewhere else NODE_CMD.finditer(command)):
        manager, run, name = m.group(1), m.group(2), m.group(3)
        following = command[m.end():m.end() + 1]
        if following in ("/", "*", "<", ">", "{", "}", "$") or name.rsplit(".", 1)[-1].lower() in {"ts", "js", "mjs", "cjs", "py", "sh", "tsx", "jsx"}:
            continue  # a pattern, a placeholder or a file being run, not a script name
        text = f"{manager} {'run ' if run else ''}{name}"
        if name.endswith("."):
            name = name.rstrip(".")
        installs = (not run) and name in {"install", "i", "ci", "add"}
        claims.append(Claim("manager", n, text, {"manager": manager}))
        is_test = (not run) and (name == "test" and manager != "bun" or (name in {"t", "tst"} and manager == "npm"))
        bare_script = (not run) and manager in ("pnpm", "yarn") and name not in BUILTINS[manager]
        if run or is_test or bare_script:
            claims.append(Claim("script", n, text, {"manager": manager, "script": "test" if is_test else name}))
    for m in MAKE_CMD.finditer(command):
        claims.append(Claim("make", n, f"make {m.group(2)}", {"target": m.group(2)}))
    t = TEST_CMD.search(command)
    if t:
        claims.append(Claim("test", n, t.group(1), {"command": t.group(1)}))


def _versions(claims, n, text):
    for m in NODE.finditer(text):
        claims.append(Claim("node", n, m.group(0).strip(), {"major": int(m.group(1)), "floor": bool(m.group(2))}))
    for m in PYTHON.finditer(text):
        claims.append(Claim("python", n, m.group(0).strip(), {"version": (int(m.group(1)), int(m.group(2))), "floor": bool(m.group(3))}))
