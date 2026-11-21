import contextlib
import io
import json
import unittest
from pathlib import Path

from helpers import Project
from mandata import __version__
from mandata.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def call(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class Cli(unittest.TestCase):
    def test_version_and_help(self):
        code, out, _ = call(["--version"])
        self.assertEqual((code, out.strip()), (0, f"mandata {__version__}"))
        code, out, _ = call(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("instruction files", out)

    def test_a_folder_that_does_not_exist_is_a_plain_message_and_exit_2(self):
        code, out, err = call(["/no/such/folder"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("is not a folder", err)

    def test_the_healthy_example_passes_with_exit_0(self):
        code, out, _ = call([str(EXAMPLES / "healthy")])
        self.assertEqual(code, 0)
        self.assertIn("Everything it could test is still true.", out)

    def test_the_drifted_example_fails_with_exit_1_and_names_each_problem_with_its_line(self):
        code, out, _ = call([str(EXAMPLES / "drifted")])
        self.assertEqual(code, 1)
        self.assertIn("CLAUDE.md", out)
        self.assertIn('line 3    PROBLEM  npm run check: package.json has no "check" script. It has: build, lint, test.', out)
        self.assertIn('make verify: the Makefile has no "verify" target', out)
        self.assertIn("Node 18: package.json says it needs Node 22 or newer.", out)
        self.assertIn("@docs/style.md: this file is imported but it is not there", out)
        self.assertIn("src/server/api.ts: that is not there any more. A file with that name is at src/api.ts.", out)
        self.assertIn("4 problems (wrong now), 3 things to check (probably stale).", out)
        self.assertIn("It cannot judge advice", out)

    def test_fail_on_chooses_what_makes_the_exit_code_one(self):
        p = Project({"CLAUDE.md": "See `src/gone.ts`.\n", "src/x.ts": ""})
        self.addCleanup(p.cleanup)
        self.assertEqual(call([str(p.root)])[0], 0, "a probably-stale path is not a wrong claim")
        self.assertEqual(call([str(p.root), "--fail-on", "warn"])[0], 1)
        q = Project({"package.json": {"scripts": {}}, "CLAUDE.md": "`npm run lint`\n"})
        self.addCleanup(q.cleanup)
        self.assertEqual(call([str(q.root)])[0], 1)
        self.assertEqual(call([str(q.root), "--fail-on", "never"])[0], 0)

    def test_json_has_the_counts_findings_and_what_was_left_alone(self):
        code, out, _ = call([str(EXAMPLES / "drifted"), "--json"])
        data = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual((data["errors"], data["warnings"]), (4, 3))
        self.assertEqual(data["files"], ["CLAUDE.md"])
        first = data["findings"][0]
        self.assertEqual(set(first), {"level", "file", "line", "code", "said", "message"})

    def test_a_project_with_no_instruction_files_says_so_and_passes(self):
        p = Project({"README.md": "hi"})
        self.addCleanup(p.cleanup)
        code, out, _ = call([str(p.root)])
        self.assertEqual(code, 0)
        self.assertIn("No agent instruction files found", out)

    def test_the_folder_defaults_to_the_current_one(self):
        import os
        p = Project({"CLAUDE.md": "Nothing checkable here.\n"})
        self.addCleanup(p.cleanup)
        old = os.getcwd()
        os.chdir(p.root)
        self.addCleanup(os.chdir, old)
        code, out, _ = call([])
        self.assertEqual(code, 0)
        self.assertIn("checked 1 instruction file", out)

    def test_a_note_says_when_commands_were_left_alone_and_when_a_file_was_a_copy(self):
        p = Project({"CLAUDE.md": "`npm run build`\n", "AGENTS.md": "`npm run build`\n"})
        self.addCleanup(p.cleanup)
        _, out, _ = call([str(p.root)])
        self.assertIn("so it was only checked once", out)
        self.assertIn("no package.json at the project root", out)


if __name__ == "__main__":
    unittest.main()
