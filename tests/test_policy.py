import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sourceguard.config import PRESETS, load_config, parse_policy
from sourceguard.engine import get_change_validation_engine
from sourceguard.git import FileDiff
from sourceguard.main import main
from sourceguard.reporting import Finding, render


def policy(**changes):
    rule = dict(
        id="use-client",
        literal="old.client(",
        message="Use client()",
        files=["*.py"],
        severity="warning",
    )
    rule.update(changes)
    return dict(version=1, rules=[rule])


class PolicyTest(unittest.TestCase):
    def findings(self, data, path="app.py", source="old.client("):
        engine = get_change_validation_engine(parse_policy(data))
        return list(engine.findings(FileDiff(path, [f"4: {source}"])))

    def test_literal_and_rule_identity(self):
        findings = self.findings(policy(files=["*.py", "app.*"]))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "use-client")
        self.assertEqual(findings[0].severity, "warning")
        self.assertEqual(findings[0].line, 4)
        self.assertEqual(self.findings(policy(), source="oldXclient("), [])

    def test_global_and_per_rule_exclusions(self):
        data = policy(exclude=["generated/*"])
        data["exclude"] = ["vendor/*"]
        self.assertEqual(self.findings(data, "vendor/lib.py"), [])
        self.assertEqual(self.findings(data, "generated/lib.py"), [])
        self.assertEqual(len(self.findings(data, "src/lib.py")), 1)

    def test_schema_rejects_typos_and_invalid_fields(self):
        bad_policies = [
            [],
            {},
            dict(version=True, rules=[]),
            dict(version=2, rules=[]),
            dict(version=1, rules=[], excludes=[]),
            dict(version=1, rules={}, exclude=[]),
            dict(version=1, rules=[], exclude="vendor/*"),
            policy(id=""),
            policy(id="bad,id"),
            policy(files=[]),
            policy(files="*.py"),
            policy(files=[""]),
            policy(message=""),
            policy(severity="warn"),
            policy(severty="warning"),
            policy(pattern="old"),
            policy(literal=""),
            policy(exclude=[1]),
        ]
        for data in bad_policies:
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_policy(data)

    def test_duplicate_ids_and_invalid_regex(self):
        data = policy()
        data["rules"] *= 2
        with self.assertRaisesRegex(ValueError, "Duplicate rule id"):
            parse_policy(data)
        data = policy()
        del data["rules"][0]["literal"]
        data["rules"][0]["pattern"] = "["
        with self.assertRaisesRegex(ValueError, "Invalid rule pattern"):
            self.findings(data)

    def test_presets_have_meaningful_positive_and_negative_examples(self):
        examples = {
            "python": [
                ("breakpoint()", 1),
                ("pdb.set_trace()", 1),
                ("  ipdb.set_trace()", 1),
                ("# breakpoint()", 0),
                ('print("breakpoint()")', 0),
            ],
            "javascript": [
                ("debugger;", 1),
                ("test.only('x', fn)", 1),
                ("describe.only('x', fn)", 1),
                ("// debugger;", 0),
                ("test('x', fn)", 0),
            ],
        }
        for preset, cases in examples.items():
            data = dict(version=1, rules=PRESETS[preset])
            path = "app.py" if preset == "python" else "app.ts"
            for source, count in cases:
                with self.subTest(preset=preset, source=source):
                    self.assertEqual(len(self.findings(data, path, source)), count)

    def test_github_annotation_escapes_untrusted_properties_and_message(self):
        finding = Finding(
            "a,b:%.py\n", 4, "bad", "one%\r\n::error::two", "rule", "warning"
        )
        annotation = render([finding], "github")
        self.assertEqual(
            annotation,
            "::warning file=a%2Cb%3A%25.py%0A,line=4,title=rule::"
            "one%25%0D%0A::error::two",
        )
        self.assertEqual(json.loads(render([finding], "json"))[0]["path"], finding.path)


class PolicyCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / "sourceguard.json"
        self.config.write_text(json.dumps(policy()), encoding="utf-8")

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        diff = "+++ b/app.py\n@@ -0,0 +1 @@\n+old.client(\n"
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch(
                    "sourceguard.main.get_project_root_dir", return_value=str(self.root)
                )
            )
            stack.enter_context(
                patch("sourceguard.main.get_diff_output", return_value=diff)
            )
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            result = main(list(args))
        return result, stdout.getvalue(), stderr.getvalue()

    def test_warning_first_and_thresholds(self):
        code, output, _ = self.cli("--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)[0]["severity"], "warning")
        self.assertEqual(self.cli("--fail-on", "warning")[0], 1)
        self.config.write_text(json.dumps(policy(severity="error")))
        self.assertEqual(self.cli()[0], 1)
        self.assertEqual(self.cli("--fail-on", "never")[0], 0)

    def test_advisory_mode_still_fails_on_invalid_configuration(self):
        self.config.write_text("{")
        self.assertEqual(self.cli("--fail-on", "never")[0], 2)

    def test_json_does_not_execute_python_and_takes_precedence(self):
        marker = self.root / "executed"
        (self.root / ".banned").write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        )
        self.assertEqual(self.cli()[0], 0)
        self.assertFalse(marker.exists())
        self.config.write_text(f"open({str(marker)!r}, 'w')")
        self.assertEqual(self.cli()[0], 2)
        self.assertFalse(marker.exists())

    def test_duplicate_json_keys_are_rejected(self):
        self.config.write_text('{"version":1,"rules":[],"rules":[]}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON field"):
            load_config(self.config)

    def test_validate_without_git_diff(self):
        with patch("sourceguard.main.get_diff_output", side_effect=AssertionError):
            with patch(
                "sourceguard.main.get_project_root_dir", return_value=str(self.root)
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--check-config"]), 0)

    def test_init_presets_and_no_overwrite(self):
        self.config.unlink()
        self.assertEqual(self.cli("--init", "--preset", "javascript")[0], 0)
        data = json.loads(self.config.read_text())
        self.assertEqual(data["rules"], PRESETS["javascript"])
        self.assertEqual(self.cli("--init", "--preset", "python")[0], 0)
        self.assertEqual(json.loads(self.config.read_text()), data)

    def test_list_presets_does_not_require_repository(self):
        with patch("sourceguard.main.get_project_root_dir", side_effect=AssertionError):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["--list-presets"]), 0)
                self.assertIn("javascript", output.getvalue())
