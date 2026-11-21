import unittest

from mandata.claims import extract
from mandata.facts import Facts


def claims(text, dirs=("src", "docs")):
    f = Facts(root=".")
    f.dirs = set(dirs)
    return [(c.kind, c.line, c.text) for c in extract(text.splitlines(), f)]


def kinds(text, kind, **kw):
    return [t for k, _, t in claims(text, **kw) if k == kind]


class Commands(unittest.TestCase):
    def test_package_scripts_are_read_from_inline_code_and_code_blocks(self):
        self.assertEqual(kinds("Run `npm run lint` first.", "script"), ["npm run lint"])
        self.assertEqual(kinds("```bash\nnpm run build\npnpm run dev\n```", "script"), ["npm run build", "pnpm run dev"])

    def test_a_prompt_in_front_of_a_command_is_ignored(self):
        self.assertEqual(kinds("```\n$ npm run build\n```", "script"), ["npm run build"])

    def test_npm_test_means_the_test_script_and_npm_start_is_left_alone_because_it_has_a_default(self):
        self.assertEqual(kinds("`npm test`", "script"), ["npm test"])
        self.assertEqual(kinds("`npm start`", "script"), [])
        self.assertEqual(kinds("`npm install`", "script"), [])

    def test_pnpm_and_yarn_run_a_script_when_the_word_is_not_one_of_their_own_commands(self):
        self.assertEqual(kinds("`pnpm lint` and `yarn build`", "script"), ["pnpm lint", "yarn build"])
        self.assertEqual(kinds("`pnpm install` `yarn add left-pad` `pnpm dlx x`", "script"), [])

    def test_bun_test_is_the_built_in_test_runner_not_a_script(self):
        self.assertEqual(kinds("`bun test`", "script"), [])
        self.assertEqual(kinds("`bun run lint`", "script"), ["bun run lint"])

    def test_commands_aimed_at_another_folder_or_workspace_are_set_aside_not_judged(self):
        for line in ("`pnpm --filter web build`", "`npm run build --workspace=api`", "`cd app && npm run dev`", "`npm --prefix ui run build`"):
            self.assertEqual(kinds(line, "script"), [], line)
            self.assertEqual(len(kinds(line, "skipped")), 1, line)

    def test_make_targets_are_read_only_from_code_so_ordinary_sentences_are_not_commands(self):
        self.assertEqual(kinds("Run `make test` and then `make -j4 build`.", "make"), ["make test", "make build"])
        self.assertEqual(kinds("Make sure it works. Please make it fast, and make a plan.", "make"), [])
        self.assertEqual(kinds("`make` on its own", "make"), [])
        self.assertEqual(kinds("`make CC=gcc`", "make"), [])

    def test_the_test_command_is_noted_for_comparing_files(self):
        self.assertEqual(kinds("`pytest -q`", "test"), ["pytest"])
        self.assertEqual(kinds("`npm run test`", "test"), ["npm run test"])
        self.assertEqual(kinds("`cargo test`", "test"), ["cargo test"])
        self.assertEqual(kinds("`ls`", "test"), [])

    def test_every_use_of_a_package_manager_is_noted(self):
        self.assertEqual(kinds("`npm install` then `yarn build`", "manager"), ["npm install", "yarn build"])


class Paths(unittest.TestCase):
    def test_paths_in_inline_code_and_links_are_claims(self):
        self.assertEqual(kinds("Edit `src/app.ts` and [guide](docs/guide.md#top).", "path"), ["src/app.ts", "docs/guide.md"])

    def test_a_line_number_is_not_part_of_the_path(self):
        self.assertEqual([c for k, _, c in claims("see `src/app.ts:42`") if k == "path"], ["src/app.ts:42"])

    def test_paths_inside_code_blocks_are_not_checked_because_they_are_usually_examples(self):
        self.assertEqual(kinds("```\ncat src/example.ts\n```", "path"), [])

    def test_things_that_only_look_like_paths_are_not(self):
        for text in ("`and/or`", "`yes/no`", "`http://example.com/a.md`", "`~/notes.md`", "`/etc/hosts.conf`", "`path/to/file.ts`",
                     "`src/<name>.ts`", "`src/*.ts`", "`${HOME}/x.md`", "`3.10`", "`foo bar.ts`", "`--flag/x`"):
            self.assertEqual(kinds(text, "path"), [], text)

    def test_a_word_with_a_slash_is_a_path_only_when_its_first_folder_exists_or_it_ends_in_a_slash(self):
        self.assertEqual(kinds("`src/components`", "path"), ["src/components"])
        self.assertEqual(kinds("`widgets/parts`", "path"), [])
        self.assertEqual(kinds("`widgets/`", "path"), ["widgets/"])

    def test_a_bare_file_name_with_a_known_ending_is_a_path(self):
        self.assertEqual(kinds("`tsconfig.json` and `main.go`", "path"), ["tsconfig.json", "main.go"])
        self.assertEqual(kinds("`example.com`", "path"), [])

    def test_imports_are_at_signs_in_plain_text_not_in_code(self):
        self.assertEqual(kinds("@docs/rules.md\nAlso @notes.txt here.", "import"), ["@docs/rules.md", "@notes.txt"])
        self.assertEqual(kinds("`@types/node` and mail me @someone", "import"), [])


class Versions(unittest.TestCase):
    def test_node_and_python_versions_are_read_from_prose(self):
        self.assertEqual(kinds("Needs Node 20 and Node.js v18.", "node"), ["Node 20", "Node.js v18"])
        self.assertEqual(kinds("Use Python 3.11.", "python"), ["Python 3.11"])

    def test_a_plus_or_newer_marks_a_minimum_not_an_exact_version(self):
        out = extract(["Node 20+, Node 18 or newer, Node 22."], Facts(root="."))
        floors = {c.text: c.data["floor"] for c in out if c.kind == "node"}
        self.assertEqual(floors, {"Node 20+": True, "Node 18 or newer": True, "Node 22": False})

    def test_words_that_merely_contain_node_are_not_versions(self):
        self.assertEqual(kinds("The node modules folder and a node 5 times.", "node"), ["node 5"])


if __name__ == "__main__":
    unittest.main()
