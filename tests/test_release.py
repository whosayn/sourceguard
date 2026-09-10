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
                with patch.object(
                    release,
                    "build_distributions",
                    side_effect=lambda version: calls.append(("build", version)) or [],
                ):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(release.main(["--publish"]), 0)
        self.assertEqual(calls[-3], ("gh", "auth", "status"))
        self.assertEqual(calls[-2], ("build", "1.2.3"))
        self.assertEqual(calls[-1], tuple(release.release_command("1.2.3", "abc123")))
        self.assertEqual(calls[1], ("git", "status", "--porcelain"))
        self.assertEqual(calls[2][:2], ("git", "ls-remote"))

    def test_build_only_does_not_require_git_or_github(self):
        with patch.object(release, "read_version", return_value="1.2.3"):
            with patch.object(release, "command") as command:
                with patch.object(
                    release, "build_distributions", return_value=[]
                ) as build:
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(release.main(["--build"]), 0)
                build.assert_called_once_with("1.2.3")
                command.assert_not_called()

    def test_build_failure_prevents_release_creation(self):
        with patch.object(release, "read_version", return_value="1.2.3"):
            with patch.object(release, "validate_checkout"):
                with patch.object(release, "command", return_value="abc123") as command:
                    with patch.object(
                        release,
                        "build_distributions",
                        side_effect=ValueError("Build failed"),
                    ):
                        with contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(release.main(["--publish"]), 1)
                self.assertFalse(
                    any(
                        call.args[:3] == ("gh", "release", "create")
                        for call in command.call_args_list
                    )
                )

    def test_build_validates_fresh_artifacts_before_copying(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dist").mkdir()
            old = root / "dist" / "old.whl"
            old.write_text("preserve")
            commands = []

            def command(*args):
                commands.append(args)
                if args[2] == "build":
                    staging = Path(args[-1])
                    (staging / "sourceguard-1.2.3-py3-none-any.whl").write_text("wheel")
                    (staging / "sourceguard-1.2.3.tar.gz").write_text("sdist")
                else:
                    self.assertEqual(args[2:5], ("twine", "check", "--strict"))
                    self.assertEqual(len(args[5:]), 2)
                    for artifact in args[5:]:
                        self.assertNotEqual(Path(artifact).parent, root / "dist")

            with patch.object(release, "ROOT", root):
                with patch.object(release, "command", side_effect=command):
                    artifacts = release.build_distributions("1.2.3")
            self.assertEqual([p.read_text() for p in artifacts], ["wheel", "sdist"])
            self.assertEqual(old.read_text(), "preserve")

    def test_missing_artifacts_or_failed_validation_preserve_existing_files(self):
        for failure in ("missing", "validation"):
            with self.subTest(
                failure=failure
            ), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "dist").mkdir()
                wheel = root / "dist" / "sourceguard-1.2.3-py3-none-any.whl"
                wheel.write_text("previous")

                def command(*args):
                    if args[2] == "build" and failure == "validation":
                        staging = Path(args[-1])
                        (staging / wheel.name).write_text("new")
                        (staging / "sourceguard-1.2.3.tar.gz").write_text("new")
                    elif args[2] == "twine":
                        raise ValueError("Invalid metadata")

                with patch.object(release, "ROOT", root):
                    with patch.object(release, "command", side_effect=command):
                        with self.assertRaises(ValueError):
                            release.build_distributions("1.2.3")
                self.assertEqual(wheel.read_text(), "previous")
