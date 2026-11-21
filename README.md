# mandata

*Latin: "orders, instructions."*

[![ci](https://github.com/patkusch/mandata/actions/workflows/ci.yml/badge.svg)](https://github.com/patkusch/mandata/actions/workflows/ci.yml)

Checks that what your coding-agent instruction files say is still true.

Files like `CLAUDE.md` and `AGENTS.md` tell an AI agent how to work in your project: which command runs the tests, where things live, which version to use. The agent follows them without asking questions. When a line goes out of date, the agent quietly does the wrong thing, and nobody notices.

mandata reads those files and tests each claim against your project. It tells you which lines are wrong now and which are probably stale. It runs on your computer, uses no AI model and sends nothing anywhere.

## What it looks like

```
mandata checked 1 instruction file in ./examples/drifted

CLAUDE.md
  line 3    PROBLEM  make verify: the Makefile has no "verify" target. It has: build, test.
  line 3    PROBLEM  npm run check: package.json has no "check" script. It has: build, lint, test.
  line 3    CHECK    npm install: the project uses pnpm (see its lock file), not npm.
  line 4    CHECK    docs/rules.md: that is not in the project.
  line 4    CHECK    src/server/api.ts: that is not there any more. A file with that name is at src/api.ts.
  line 5    PROBLEM  Node 18: package.json says it needs Node 22 or newer.
  line 7    PROBLEM  @docs/style.md: this file is imported but it is not there, so the agent never sees it.

4 problems (wrong now), 3 things to check (probably stale).
It only tests claims it can check against your files: commands, file paths, imports and versions. It cannot judge advice such as "write clean code".
```

"Problem" means the project plainly says otherwise, so the agent will fail or be misled. "Check" means it is probably stale, but only you can tell.

## What it checks

| The file says | mandata looks at |
|---|---|
| `npm run lint`, `pnpm build`, `yarn test`, `bun run dev` | the scripts in the project's `package.json` |
| `make test` | the targets in the `Makefile` |
| `src/api.ts`, `docs/`, a link to `docs/guide.md` | whether that file or folder exists, and where it went if it moved |
| `@docs/rules.md` on its own line | whether the imported file exists (if not, the agent never reads it) |
| "Node 18", "Python 3.9" | `engines`, `.nvmrc`, `requires-python`, `.python-version` |
| `npm install` in a project with a `pnpm-lock.yaml` | which package manager the project really uses |
| two instruction files | whether they disagree about the package manager or the test command |

It reads `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CONVENTIONS.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md` and the rule files under `.cursor/rules/`, in the project folder and in sub-folders. In a project with several packages, a file in `ui/` is judged against `ui/package.json`, not the one at the top.

## What it cannot check

- Advice. "Write clean code" and "prefer small functions" cannot be tested, so it leaves them alone.
- Commands it cannot tell about. A command that points at another folder or workspace, or one in a project with no `package.json`, is counted in a "left alone" line at the end, not guessed at.
- File paths inside code blocks. Those are usually examples, so only commands are read there.
- Anything outside the project folder, such as a `CLAUDE.md` in your home folder.
- Whether the instruction is a *good* one. Only whether it is still *true*.

## Use it

You need Python 3.9 or newer. It has no other requirements.

```bash
pip install git+https://github.com/patkusch/mandata
mandata                # check the project in this folder
mandata path/to/repo   # or another one
mandata --json         # the same result as data
```

It exits with 0 when nothing is wrong, 1 when a claim is wrong now, and 2 when it could not run. `--fail-on warn` also fails on the "probably stale" items, and `--fail-on never` never fails.

To check on every push, add a step to your CI:

```yaml
- run: pip install git+https://github.com/patkusch/mandata
- run: mandata
```

## Where it got things wrong at first

I ran it on a real project with 17 instruction files in sub-folders (a monorepo). The first version reported 20 problems. Almost all were false alarms from the same few mistakes: it judged a sub-folder's commands against the top-level `package.json`, it treated `bun run pm2-{start,stop}` and `bun run src/index.ts` as script names, and it flagged file names that were written from inside a sub-folder. Each of those is now fixed and has a test. The same project now gets no problems and four "check" items, all of which are real: a file name that no longer exists, and two paths in a template that describe a different project.

A false alarm is treated as a bug. If it tells you something is wrong when it is not, please open an issue with the line.

## Tests

75 tests, no network, no files outside a throw-away folder. `python -m unittest discover -s tests`. The two projects in `examples/` (one healthy, one with drifted instructions) are checked in CI.

## Licence

MIT. See [LICENSE](LICENSE).

---

[Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security policy](SECURITY.md)
