import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sourceguard.banrule import BanRule
from sourceguard.git import get_changed_files_diffs, get_diff_output
from sourceguard.main import main, run


class RulesTest(unittest.TestCase):
    def test_regex_iterators_overlapping_globs_and_multiple_rules(self):
        diff = "+++ b/src/app.py\n@@ -0,0 +1 @@\n+bad(123) other\n"
        rules = {
            "*.py": iter([BanRule(r"bad\(\d+\)", "first"), BanRule("other", "second")]),
            "src/*": [BanRule("bad", "third")],
        }
        self.assertEqual(
            [row[3] for row in run(diff, rules)], ["first", "second", "third"]
        )

    def test_exclusion_does_not_hide_other_rules(self):
        diff = "+++ b/vendor/app.py\n@@ -0,0 +1 @@\n+bad other\n"
        rules = {
            "*.py": [BanRule("bad", "skip", ["vendor/*"]), BanRule("other", "keep")]
        }
        self.assertEqual([row[3] for row in run(diff, rules)], ["keep"])
        self.assertEqual(len(run(diff.replace("vendor/", "src/"), rules)), 2)

    def test_source_is_not_stripped_or_prefixed_with_line_number(self):
        diff = "+++ b/a.py\n@@ -0,0 +1,2 @@\n+  bad\n+good\n"
        rules = {"*.py": [BanRule(r"^  bad$", "indent"), BanRule(r"^1:", "not source")]}
        self.assertEqual([row[3] for row in run(diff, rules)], ["indent"])

    def test_control_characters_do_not_split_source_lines(self):
        diff = "+++ b/a.py\n@@ -0,0 +1 @@\n+before\vbad\n"
        self.assertEqual(len(run(diff, {"*": [BanRule("bad", "found")]})), 1)

    def test_invalid_regex_is_actionable(self):
        with self.assertRaisesRegex(ValueError, "Invalid rule pattern"):
            run("", {"*": [BanRule("[", "broken")]})

    def test_patch_line_numbers_and_header_like_source(self):
        diff = (
            "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n"
            "@@ -2,2 +2,3 @@\n context\n-old\n+new\n+++ b/source\n"
            "@@ -10 +11 @@\n-old\n+last\n"
            "\\ No newline at end of file\n"
        )
        files = list(get_changed_files_diffs(diff))
        self.assertEqual(files[0].filepath, "a.py")
        self.assertEqual(files[0].diff_lines, ["3: new", "4: ++ b/source", "11: last"])


class GitIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")
        self.env = patch.dict(
            os.environ,
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch(
            "sourceguard.main.get_project_root_dir", return_value=str(self.root)
        ):
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(stdout))
                stack.enter_context(contextlib.redirect_stderr(stderr))
                code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def config(self):
        (self.root / ".banned").write_text(
            "from sourceguard.banrule import BanRule\n"
            'BANRULES_MAP = {"*.py": [BanRule("bad", "Use good")] }\n'
        )

    def test_initial_commit_staged_only_and_json(self):
        self.config()
        file = self.root / "space ü.py"
        file.write_text("bad\n")
        self.git("add", "--", file.name)
        file.write_text("good\n")
        cwd = os.getcwd()
        code, out, err = self.cli("--format", "json")
        self.assertEqual(code, 1, err)
        self.assertEqual(json.loads(out)[0]["path"], file.name)
        self.assertEqual(json.loads(out)[0]["line"], 1)
        self.assertEqual(os.getcwd(), cwd)

    def test_committed_base_ignores_legacy_and_unstaged_lines(self):
        self.config()
        file = self.root / "a.py"
        file.write_text("bad legacy\ngood\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        base = self.git("rev-parse", "HEAD").strip()
        file.write_text("bad legacy\ngood\nbad new\n")
        self.git("add", ".")
        self.git("commit", "-qm", "new")
        file.write_text("bad unstaged\n")
        code, out, err = self.cli("--base", base, "--format", "json")
        self.assertEqual(code, 1, err)
        self.assertEqual([row["line"] for row in json.loads(out)], [3])
        self.assertEqual(self.cli()[0], 0)

    def test_rename_delete_binary_and_quoted_paths(self):
        for name in ["old.py", "delete.py"]:
            (self.root / name).write_text("bad\n")
        self.git("add", ".")
        self.git("commit", "-qm", "initial")
        self.git("mv", "old.py", "new.py")
        self.git("rm", "delete.py")
        (self.root / "binary").write_bytes(b"\x00bad\n")
        name = "tab name.py" if os.name == "nt" else "tab\tname.py"
        (self.root / name).write_text("bad new file\n")
        self.git("add", ".")
        diffs = list(get_changed_files_diffs(get_diff_output(str(self.root))))
        self.assertEqual(
            [(d.filepath, d.diff_lines) for d in diffs], [(name, ["1: bad new file"])]
        )

    def test_setup_is_explicit_and_does_not_overwrite(self):
        code, _, err = self.cli()
        self.assertEqual(code, 2)
        self.assertIn("--init", err)
        self.assertFalse((self.root / ".banned").exists())
        self.assertEqual(self.cli("--init")[0], 0)
        content = (self.root / ".banned").read_text()
        self.assertEqual(self.cli("--init")[0], 0)
        self.assertEqual((self.root / ".banned").read_text(), content)
        self.assertEqual(self.cli()[0], 0)

    def test_configuration_errors_and_bad_ref(self):
        (self.root / ".banned").write_text("BANRULES_MAP = {")
        self.assertEqual(self.cli()[0], 2)
        self.config()
        code, _, err = self.cli("--base", "does-not-exist")
        self.assertEqual(code, 2)
        self.assertIn("sourceguard:", err)

    def test_module_entry_point_from_nested_directory(self):
        self.config()
        nested = self.root / "nested"
        nested.mkdir()
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        result = subprocess.run(
            [os.sys.executable, "-m", "sourceguard", "--format", "json"],
            cwd=nested,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
