"""Command line: `mandata [folder]`."""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__, report
from .check import check_project


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mandata", description="Check that what your coding-agent instruction files say is still true.")
    p.add_argument("--version", action="version", version=f"mandata {__version__}")
    p.add_argument("path", nargs="?", default=".", help="the project folder (default: this one)")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.add_argument("--fail-on", choices=["error", "warn", "never"], default="error",
                   help="when to exit with 1: on a wrong claim (default), on any finding, or never")
    p.add_argument("--exclude", action="append", default=[], metavar="FOLDER",
                   help="leave out the instruction files under this folder, for example sample projects used in tests (repeatable)")
    args = p.parse_args(argv)
    if not os.path.isdir(args.path):
        print(f"mandata: {args.path} is not a folder", file=sys.stderr)
        return 2
    result = check_project(args.path, args.exclude)
    print(report.as_json(result) if args.json else report.text(result))
    errors, warnings = result.counts()
    if args.fail_on == "error":
        return 1 if errors else 0
    if args.fail_on == "warn":
        return 1 if errors or warnings else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
