# Changelog

All notable changes to this project are listed here, newest first.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- First version. It reads the files that tell a coding agent what to do (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.windsurfrules`, `CONVENTIONS.md`, Copilot and Cursor rules) and checks what it can against the project:
  - package commands such as `npm run lint`, and `make` targets, against `package.json` and the `Makefile`;
  - file and folder paths, and `@file` imports, against the files that exist, with a hint when a file has moved;
  - Node and Python versions against `engines`, `.nvmrc`, `requires-python` and `.python-version`;
  - the package manager against the lock file, and two instruction files that disagree with each other.
- In a project with sub-folders, each instruction file is judged against the nearest `package.json`, `Makefile` and lock file, not only the root one.
- Two files with exactly the same words in the same folder (for example `AGENTS.md` linking to `CLAUDE.md`) are checked once.
- `--exclude FOLDER` leaves out the instruction files under a folder, for sample projects used in tests.
- `--json`, and `--fail-on error|warn|never` to choose when the exit code is 1.
