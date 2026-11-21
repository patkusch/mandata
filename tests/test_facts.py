import unittest

from helpers import Project
from mandata.facts import load_facts


class Facts(unittest.TestCase):
    def facts(self, files):
        p = Project(files)
        self.addCleanup(p.cleanup)
        return load_facts(p.root)

    def test_scripts_workspaces_manager_and_lock_files_are_read_from_package_json(self):
        f = self.facts({"package.json": {"scripts": {"build": "x", "test": "y"}, "workspaces": ["a"], "packageManager": "pnpm@9.1.0"},
                        "pnpm-lock.yaml": "", "yarn.lock": ""})
        self.assertEqual(set(f.scripts), {"build", "test"})
        self.assertTrue(f.has_workspaces)
        self.assertEqual(f.package_manager, "pnpm")
        self.assertEqual(f.lockfile_managers, {"pnpm", "yarn"})

    def test_no_package_json_means_nothing_is_known_about_scripts_not_that_there_are_none(self):
        self.assertIsNone(self.facts({"README.md": ""}).scripts)
        self.assertEqual(self.facts({"package.json": {"name": "x"}}).scripts, {})

    def test_a_broken_package_json_is_ignored_rather_than_crashing(self):
        self.assertIsNone(self.facts({"package.json": "{not json"}).scripts)

    def test_the_node_floor_comes_from_engines_in_every_common_spelling(self):
        for spec, want in ((">=20", 20), (">= 18.17", 18), ("^22.1.0", 22), ("~20", 20), ("20.x", 20), ("22", 22), ("*", None)):
            f = self.facts({"package.json": {"engines": {"node": spec}}})
            self.assertEqual(f.node_floor, want, spec)

    def test_a_pinned_node_version_comes_from_nvmrc_node_version_or_tool_versions(self):
        self.assertEqual(self.facts({".nvmrc": "v20.11.0\n"}).node_exact, 20)
        self.assertEqual(self.facts({".node-version": "22\n"}).node_exact, 22)
        self.assertEqual(self.facts({".tool-versions": "nodejs 18.19.0\npython 3.11.4\n"}).node_exact, 18)
        self.assertEqual(self.facts({".nvmrc": "lts/*\n"}).node_exact, None)

    def test_python_floor_and_pin(self):
        self.assertEqual(self.facts({"pyproject.toml": '[project]\nrequires-python = ">=3.10"\n'}).python_floor, (3, 10))
        self.assertEqual(self.facts({".python-version": "3.12.1\n"}).python_exact, (3, 12))
        self.assertEqual(self.facts({".tool-versions": "python 3.11.4\n"}).python_exact, (3, 11))
        self.assertIsNone(self.facts({"pyproject.toml": "[project]\nname = 'x'\n"}).python_floor)

    def test_make_targets_are_found_including_several_on_one_line_and_not_variables_or_special_names(self):
        f = self.facts({"Makefile": ".PHONY: test\nPY ?= python3\nVERSION := 1\ntest build:\n\techo\nlint:\n\techo\n%.o: %.c\n\techo\n"})
        self.assertEqual(f.make_targets, {"test", "build", "lint"})
        self.assertIsNone(self.facts({"README.md": ""}).make_targets)

    def test_files_and_folders_are_indexed_and_build_folders_are_left_out(self):
        f = self.facts({"src/a.py": "", "docs/x/y.md": "", "node_modules/p/i.js": "", ".git/config": "", "dist/out.js": ""})
        self.assertIn("src/a.py", f.files)
        self.assertIn("docs/x", f.dirs)
        self.assertEqual(f.by_name["a.py"], ["src/a.py"])
        self.assertFalse(any(p.startswith(("node_modules", ".git/", "dist")) for p in f.files))

    def test_plain_names_in_gitignore_are_remembered_and_patterns_are_not(self):
        f = self.facts({".gitignore": "# comment\nsecrets/\n*.log\n!keep\nbuild-output\n"})
        self.assertEqual(f.ignored, {"secrets", "build-output"})


if __name__ == "__main__":
    unittest.main()
