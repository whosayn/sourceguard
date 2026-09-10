import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "release_helper", Path(__file__).resolve().parents[1] / "scripts" / "release.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTest(unittest.TestCase):
    def test_only_supported_versions_can_become_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for version in ("1.2.3", "2.0.0rc1", "2.0.0a0", "2.0.0b2"):
                (root / "setup.cfg").write_text(f"[metadata]\nversion = {version}\n")
                self.assertEqual(release.read_version(root), version)
            for version in ("1.2", "01.2.3", "v1.2.3", "1.2.3; echo unsafe"):
                (root / "setup.cfg").write_text(f"[metadata]\nversion = {version}\n")
                with self.assertRaises(ValueError):
                    release.read_version(root)

    def test_tag_mismatch_fails_without_running_commands(self):
        with patch.object(release, "read_version", return_value="1.2.3"):
            with patch.object(release, "command") as command:
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(release.main(["--check-tag", "v1.2.4"]), 1)
                command.assert_not_called()
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(release.main(["--check-tag", "v1.2.3"]), 0)
                command.assert_not_called()

    def test_preview_never_contacts_github_or_publishes(self):
        with patch.object(release, "read_version", return_value="1.2.3"):
            with patch.object(release, "command", return_value="abc123") as command:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(release.main([]), 0)
                command.assert_called_once_with("git", "rev-parse", "HEAD")
                self.assertIn("Preview only", output.getvalue())
                self.assertIn("--target abc123", output.getvalue())

    def test_prerelease_flags(self):
        self.assertNotIn("--prerelease", release.release_command("1.2.3", "sha"))
        for version in ("1.2.3rc1", "1.2.3a1", "1.2.3b1"):
            args = release.release_command(version, "sha")
            self.assertIn("--prerelease", args)
            self.assertIn("--latest=false", args)

    def test_dirty_checkout_rejected_before_network_access(self):
        with patch.object(release, "command", return_value=" M setup.cfg") as command:
            with self.assertRaisesRegex(ValueError, "clean"):
                release.validate_checkout("abc123", "v1.2.3")
            command.assert_called_once_with("git", "status", "--porcelain")

    def test_unmerged_commit_and_existing_tag_are_rejected(self):
        for remote in (
            "def456\trefs/heads/main",
            "abc123\trefs/heads/main\nabc123\trefs/tags/v1.2.3",
        ):
            with patch.object(release, "command", side_effect=["", remote]):
                with self.assertRaises(ValueError):
                    release.validate_checkout("abc123", "v1.2.3")
        with patch.object(
            release, "command", side_effect=["", "abc123\trefs/heads/main"]
        ):
            release.validate_checkout("abc123", "v1.2.3")

    def test_publish_creates_release_only_after_validation(self):
        calls = []

        def command(*args):
            calls.append(args)
            if args[:2] == ("git", "rev-parse"):
                return "abc123"
            if args[:2] == ("git", "ls-remote"):
                return "abc123\trefs/heads/main"
            return ""

        with patch.object(release, "read_version", return_value="1.2.3"):
            with patch.object(release, "command", side_effect=command):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(release.main(["--publish"]), 0)
        self.assertEqual(calls[-2], ("gh", "auth", "status"))
        self.assertEqual(calls[-1], tuple(release.release_command("1.2.3", "abc123")))
        self.assertEqual(calls[1], ("git", "status", "--porcelain"))
        self.assertEqual(calls[2][:2], ("git", "ls-remote"))
