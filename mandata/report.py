"""Say what was found, in plain words."""
from __future__ import annotations

import json

from .check import ERROR


def _plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def as_json(result) -> str:
    return json.dumps(result.to_dict(), indent=2)


def text(result) -> str:
    lines = []
    count = len(result.files)
    if not count:
        return ("No agent instruction files found (CLAUDE.md, AGENTS.md, GEMINI.md, .cursorrules and the like) in "
                f"{result.root}. Nothing to check.")
    lines.append(f"mandata checked {_plural(count, 'instruction file')} in {result.root}")
    current = None
    for f in result.findings:
        if f.file != current:
            current = f.file
            lines += ["", current]
        tag = "PROBLEM" if f.level == ERROR else "CHECK  "
        lines.append(f"  line {f.line:<4} {tag}  {f.said}: {f.message}")
    errors, warnings = result.counts()
    lines.append("")
    if not result.findings:
        lines.append("Everything it could test is still true.")
    else:
        lines.append(f"{_plural(errors, 'problem')} (wrong now), {_plural(warnings, 'thing')} to check (probably stale).")
    for copy, original in sorted(result.copies.items()):
        lines.append(f"{copy} says the same as {original}, so it was only checked once.")
    if result.unchecked:
        left = ", ".join(f"{why} ({n})" for why, n in sorted(result.unchecked.items()))
        lines.append(f"Left alone because it could not tell: {left}.")
    lines.append("It only tests claims it can check against your files: commands, file paths, imports and versions. "
                 "It cannot judge advice such as \"write clean code\".")
    return "\n".join(lines)
