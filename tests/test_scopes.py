"""Monorepos: a command in a sub-folder's instruction file is judged against that folder's own project."""
import unittest

from helpers import Project
from mandata.check import check_project

ROOT = {"name": "root", "scripts": {"docs:openapi": "x", "build": "tsc"}}
UI = {"name": "ui", "scripts": {"build": "vite build", "preview": "vite preview"}}


class Scopes(unittest.TestCase):
    def run_check(self, files):
        p = Project(files)
        self.addCleanup(p.cleanup)
        return check_project(p.root)

    def codes(self, files):
        return sorted((f.file, f.code) for f in self.run_check(files).findings)

    def test_a_sub_folder_file_is_checked_against_that_folders_package_json(self):
        files = {"package.json": ROOT, "ui/package.json": UI, "ui/CLAUDE.md": "`npm run preview` and `npm run build`\n"}
        self.assertEqual(self.codes(files), [])

    def test_a_script_that_only_the_sub_folder_lacks_is_still_found_if_a_folder_above_has_it(self):
        files = {"package.json": ROOT, "ui/package.json": UI, "ui/CLAUDE.md": "`npm run docs:openapi`\n"}
        self.assertEqual(self.codes(files), [])

    def test_a_script_nobody_has_is_wrong_and_the_list_shown_is_the_nearest_projects(self):
        r = self.run_check({"package.json": ROOT, "ui/package.json": UI, "ui/CLAUDE.md": "`npm run lint`\n"})
        (f,) = r.findings
        self.assertEqual(f.code, "script-missing")
        self.assertIn("It has: build, preview", f.message)

    def test_each_folder_uses_its_own_lock_file_to_decide_which_package_manager_is_right(self):
        files = {"package.json": ROOT, "bun.lock": "", "ui/package.json": UI, "ui/pnpm-lock.yaml": "",
                 "CLAUDE.md": "`bun run build`\n", "ui/CLAUDE.md": "`pnpm run build`\n"}
        self.assertEqual(self.codes(files), [])
        files["ui/CLAUDE.md"] = "`bun run build`\n"
        self.assertEqual(self.codes(files), [("ui/CLAUDE.md", "manager-mismatch")])

    def test_a_make_target_is_looked_up_in_the_nearest_makefile(self):
        files = {"Makefile": "root:\n\techo\n", "api/Makefile": "serve:\n\techo\n", "api/AGENTS.md": "`make serve` and `make root`\n"}
        self.assertEqual(self.codes(files), [("api/AGENTS.md", "make-missing")])

    def test_a_version_pin_in_a_sub_folder_applies_there_and_not_in_the_root(self):
        files = {"web/.nvmrc": "18\n", "web/CLAUDE.md": "Node 18\n", "CLAUDE.md": "Node 22\n"}
        self.assertEqual(self.codes(files), [])
        self.assertEqual(self.codes({"web/.nvmrc": "18\n", "web/CLAUDE.md": "Node 22\n"}), [("web/CLAUDE.md", "node-mismatch")])

    def test_a_file_that_says_exactly_the_same_as_another_in_its_folder_is_checked_once(self):
        r = self.run_check({"package.json": ROOT, "CLAUDE.md": "`npm run lint`\n", "AGENTS.md": "`npm run lint`\n"})
        self.assertEqual(len(r.findings), 1)
        self.assertEqual(r.copies, {"CLAUDE.md": "AGENTS.md"} if "AGENTS.md" < "CLAUDE.md" else {"AGENTS.md": "CLAUDE.md"})

    def test_the_same_words_in_different_folders_are_both_checked_because_they_mean_different_things(self):
        files = {"package.json": ROOT, "ui/package.json": UI, "CLAUDE.md": "`npm run preview`\n", "ui/CLAUDE.md": "`npm run preview`\n"}
        self.assertEqual(self.codes(files), [("CLAUDE.md", "script-missing")])


class Paths(unittest.TestCase):
    def codes(self, files):
        p = Project(files)
        self.addCleanup(p.cleanup)
        return sorted(f.code for f in check_project(p.root).findings)

    def test_a_bare_file_name_is_fine_if_the_file_exists_anywhere(self):
        self.assertEqual(self.codes({"CLAUDE.md": "See `meta.json` and `use-agents.ts`.\n", "a/b/meta.json": "", "ui/src/use-agents.ts": ""}), [])

    def test_a_path_written_from_a_sub_folder_matches_the_end_of_a_real_path(self):
        self.assertEqual(self.codes({"CLAUDE.md": "`components/workflows/node.tsx`\n", "ui/src/components/workflows/node.tsx": ""}), [])

    def test_a_path_without_an_ending_matches_a_file_with_that_name_and_any_ending(self):
        self.assertEqual(self.codes({"CLAUDE.md": "`src/be/db` holds it.\n", "src/be/db.ts": ""}), [])

    def test_a_pattern_or_an_alias_or_a_placeholder_is_not_a_path(self):
        text = "`@/components`, `src/migrations/NNN_name.sql`, `bun run pm2-{start,stop}`, `bun run src/index.ts`\n"
        self.assertEqual(self.codes({"CLAUDE.md": text, "package.json": {"scripts": {}}, "src/index.ts": ""}), [])

    def test_a_path_with_a_folder_that_exists_and_a_file_that_does_not_is_still_missing(self):
        self.assertEqual(self.codes({"CLAUDE.md": "`src/old/api.ts`\n", "src/other.ts": ""}), ["path-missing"])


if __name__ == "__main__":
    unittest.main()
