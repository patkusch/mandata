import unittest

from helpers import Project
from mandata.check import ERROR, WARN, check_project

PKG = {"name": "x", "scripts": {"build": "tsc", "test": "node --test"}, "engines": {"node": ">=22"}}


class Check(unittest.TestCase):
    def run_check(self, files):
        p = Project(files)
        self.addCleanup(p.cleanup)
        return check_project(p.root)

    def codes(self, files):
        return sorted((f.code, f.level) for f in self.run_check(files).findings)

    def test_a_project_whose_instructions_are_all_true_has_no_findings(self):
        r = self.run_check({"package.json": PKG, "Makefile": "test:\n\techo\n", "src/api.ts": "", "docs/guide.md": "",
                            "CLAUDE.md": "Run `npm test`, `npm run build` and `make test`.\nEdit `src/api.ts`; read [guide](docs/guide.md).\nNeeds Node 22.\n"})
        self.assertEqual(r.findings, [])
        self.assertEqual(r.files, ["CLAUDE.md"])

    def test_a_missing_script_is_wrong_now_and_names_the_scripts_that_do_exist(self):
        r = self.run_check({"package.json": PKG, "CLAUDE.md": "Run `npm run lint`.\n"})
        (f,) = r.findings
        self.assertEqual((f.code, f.level, f.line, f.said), ("script-missing", ERROR, 1, "npm run lint"))
        self.assertIn('no "lint" script. It has: build, test', f.message)

    def test_npm_test_with_no_test_script_is_wrong_but_npm_start_is_not_judged(self):
        self.assertEqual(self.codes({"package.json": {"scripts": {}}, "CLAUDE.md": "`npm test`\n"}), [("script-missing", ERROR)])
        self.assertEqual(self.codes({"package.json": {"scripts": {}}, "CLAUDE.md": "`npm start`\n"}), [])

    def test_a_project_with_no_scripts_at_all_says_so(self):
        (f,) = self.run_check({"package.json": {"name": "x"}, "CLAUDE.md": "`npm run build`\n"}).findings
        self.assertIn("no scripts at all", f.message)

    def test_package_commands_cannot_be_judged_without_a_package_json_and_are_counted_as_left_alone(self):
        r = self.run_check({"CLAUDE.md": "`npm run build`\n"})
        self.assertEqual(r.findings, [])
        self.assertEqual(sum(r.unchecked.values()), 1)
        self.assertIn("no package.json", list(r.unchecked)[0])

    def test_a_workspace_project_is_not_blamed_for_a_script_that_may_live_in_a_sub_package(self):
        r = self.run_check({"package.json": {"scripts": {}, "workspaces": ["packages/*"]}, "CLAUDE.md": "`npm run build`\n"})
        self.assertEqual(r.findings, [])
        self.assertEqual(sum(r.unchecked.values()), 1)

    def test_a_make_target_that_is_not_there_is_wrong(self):
        (f,) = self.run_check({"Makefile": "test:\n\techo\nbuild:\n\techo\n", "CLAUDE.md": "`make check`\n"}).findings
        self.assertEqual((f.code, f.level), ("make-missing", ERROR))
        self.assertIn("It has: build, test", f.message)

    def test_a_missing_file_is_only_something_to_check_and_a_moved_one_says_where_it_went(self):
        self.assertEqual(self.codes({"CLAUDE.md": "Edit `src/old.ts`.\n", "src/a.ts": ""}), [("path-missing", WARN)])
        (f,) = self.run_check({"CLAUDE.md": "Edit `src/old.ts`.\n", "src/new/old.ts": ""}).findings
        self.assertEqual(f.code, "path-moved")
        self.assertIn("src/new/old.ts", f.message)

    def test_several_files_with_the_name_are_counted_not_guessed(self):
        (f,) = self.run_check({"CLAUDE.md": "`src/util.ts`\n", "a/util.ts": "", "b/util.ts": "", "src/x.ts": ""}).findings
        self.assertIn("2 with that name exist elsewhere", f.message)

    def test_folders_are_checked_too(self):
        self.assertEqual(self.codes({"CLAUDE.md": "See `docs/`.\n", "README.md": ""}), [("path-missing", WARN)])
        self.assertEqual(self.codes({"CLAUDE.md": "See `docs/`.\n", "docs/a.md": ""}), [])

    def test_a_folder_named_without_its_parents_is_found_when_it_exists_somewhere_below(self):
        self.assertEqual(self.codes({"CLAUDE.md": "See `components/`.\n", "src/components/a.ts": ""}), [])

    def test_build_output_ignored_folders_and_env_files_are_never_expected_to_exist(self):
        files = {"CLAUDE.md": "Do not edit `dist/app.js`, `build/out.js`, `secrets/key.json` or `.env.local`; logs go to `run.log`.\n",
                 ".gitignore": "secrets/\n", "README.md": ""}
        self.assertEqual(self.codes(files), [])

    def test_a_path_is_found_from_the_folder_the_instruction_file_is_in(self):
        files = {"app/CLAUDE.md": "See `docs/x.md` and `../shared/y.md`.\n", "app/docs/x.md": "", "shared/y.md": ""}
        self.assertEqual(self.codes(files), [])

    def test_an_import_that_does_not_exist_is_wrong_because_the_agent_silently_never_reads_it(self):
        (f,) = self.run_check({"CLAUDE.md": "@docs/rules.md\n", "docs/other.md": ""}).findings
        self.assertEqual((f.code, f.level), ("import-missing", ERROR))
        self.assertEqual(self.codes({"CLAUDE.md": "@docs/rules.md\n", "docs/rules.md": ""}), [])

    def test_a_node_version_below_the_stated_minimum_or_different_from_the_pin_is_wrong(self):
        self.assertEqual(self.codes({"package.json": PKG, "CLAUDE.md": "Node 18\n"}), [("node-too-old", ERROR)])
        self.assertEqual(self.codes({".nvmrc": "20\n", "CLAUDE.md": "Node 22\n"}), [("node-mismatch", ERROR)])

    def test_a_version_that_is_a_minimum_or_newer_than_the_minimum_is_fine(self):
        self.assertEqual(self.codes({"package.json": PKG, "CLAUDE.md": "Node 18+ is fine; we use Node 24.\n"}), [])

    def test_a_python_version_below_the_minimum_or_different_from_the_pin_is_wrong(self):
        self.assertEqual(self.codes({"pyproject.toml": '[project]\nrequires-python = ">=3.11"\n', "CLAUDE.md": "Python 3.9\n"}), [("python-too-old", ERROR)])
        self.assertEqual(self.codes({".python-version": "3.12\n", "CLAUDE.md": "Python 3.11\n"}), [("python-mismatch", ERROR)])
        self.assertEqual(self.codes({"pyproject.toml": '[project]\nrequires-python = ">=3.9"\n', "CLAUDE.md": "Python 3.13\n"}), [])

    def test_using_a_package_manager_the_project_does_not_is_something_to_check(self):
        r = self.run_check({"pnpm-lock.yaml": "", "package.json": PKG, "CLAUDE.md": "Run `npm install`.\n"})
        (f,) = r.findings
        self.assertEqual((f.code, f.level, f.said), ("manager-mismatch", WARN, "npm install"))
        self.assertIn("pnpm", f.message)
        self.assertEqual(self.codes({"pnpm-lock.yaml": "", "CLAUDE.md": "`pnpm install`\n"}), [])

    def test_the_package_manager_field_beats_stray_lock_files(self):
        files = {"package.json": {**PKG, "packageManager": "pnpm@9"}, "package-lock.json": "", "CLAUDE.md": "`npm install`\n"}
        self.assertEqual(self.codes(files), [("manager-mismatch", WARN)])

    def test_two_instruction_files_that_name_different_managers_disagree_when_the_project_does_not_say(self):
        files = {"CLAUDE.md": "`npm install`\n", "AGENTS.md": "`pnpm install`\n"}
        self.assertEqual(self.codes(files), [("files-disagree-manager", WARN)])

    def test_two_instruction_files_with_different_test_commands_disagree_but_overlap_is_fine(self):
        self.assertEqual(self.codes({"CLAUDE.md": "`pytest`\n", "AGENTS.md": "`npm test`\n"}), [("files-disagree-test", WARN)])
        self.assertEqual(self.codes({"CLAUDE.md": "`pytest`\n", "AGENTS.md": "`pytest` or `npm test`\n"}), [])

    def test_every_kind_of_instruction_file_is_found_including_nested_and_editor_rules(self):
        files = {"CLAUDE.md": "", "AGENTS.md": "", "GEMINI.md": "", ".cursorrules": "", ".windsurfrules": "", "CONVENTIONS.md": "",
                 ".github/copilot-instructions.md": "", ".cursor/rules/style.mdc": "", "web/AGENTS.md": "", "README.md": "", "docs/notes.md": ""}
        r = self.run_check(files)
        self.assertEqual(sorted(r.files), sorted(k for k in files if k not in ("README.md", "docs/notes.md")))
        self.assertEqual(r.files[0].count("/"), 0, "root-level files come first")

    def test_the_same_mistake_on_one_line_is_reported_once(self):
        r = self.run_check({"package.json": PKG, "CLAUDE.md": "`npm run lint` and again `npm run lint`\n"})
        self.assertEqual(len(r.findings), 1)

    def test_findings_are_ordered_by_file_then_line(self):
        r = self.run_check({"package.json": PKG, "CLAUDE.md": "`npm run b`\n\n`npm run a`\n", "AGENTS.md": "`npm run c`\n"})
        self.assertEqual([(f.file, f.line) for f in r.findings], [("AGENTS.md", 1), ("CLAUDE.md", 1), ("CLAUDE.md", 3)])

    def test_the_result_counts_and_converts_to_plain_data(self):
        r = self.run_check({"package.json": PKG, "CLAUDE.md": "`npm run lint` and `src/gone.ts`\n"})
        self.assertEqual(r.counts(), (1, 1))
        d = r.to_dict()
        self.assertEqual((d["errors"], d["warnings"], d["files"]), (1, 1, ["CLAUDE.md"]))
        self.assertEqual({f["code"] for f in d["findings"]}, {"script-missing", "path-missing"})


if __name__ == "__main__":
    unittest.main()
