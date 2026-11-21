"""Find the files that tell a coding agent what to do."""
from __future__ import annotations

NAMES = {
    "CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md", "CONVENTIONS.md",
    ".cursorrules", ".windsurfrules",
}


def instruction_files(facts) -> list:
    """Repo-relative paths of every instruction file, root-level ones first."""
    found = []
    for rel in sorted(facts.files):
        name = rel.rsplit("/", 1)[-1]
        if name in NAMES:
            found.append(rel)
        elif rel == ".github/copilot-instructions.md":
            found.append(rel)
        elif rel.startswith(".cursor/rules/") and name.endswith((".mdc", ".md")):
            found.append(rel)
        elif rel.startswith(".github/instructions/") and name.endswith(".md"):
            found.append(rel)
    return sorted(found, key=lambda r: (r.count("/"), r))
