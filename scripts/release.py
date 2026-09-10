#!/usr/bin/env python3
"""Preview or publish a GitHub release from the merged package version."""
import argparse
import configparser
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "whosayn/sourceguard"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}.git"
VERSION_PATTERN = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:(a|b|rc)\d+)?"


def read_version(root):
    config = configparser.ConfigParser(interpolation=None)
    config.read(root / "setup.cfg", encoding="utf-8")
    version = config.get("metadata", "version")
    if not re.fullmatch(VERSION_PATTERN, version):
        raise ValueError("Use a version like 1.2.3 or 1.2.3rc1 in setup.cfg")
    return version


def command(*args):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"Command failed: {args[0]}")
    return result.stdout.strip()


def release_command(version, sha):
    args = [
        "gh",
        "release",
        "create",
        f"v{version}",
        "--repo",
        REPOSITORY,
        "--target",
        sha,
        "--title",
        f"v{version}",
        "--generate-notes",
    ]
    if re.fullmatch(VERSION_PATTERN, version).group(1):
        args.extend(["--prerelease", "--latest=false"])
    return args


def validate_checkout(sha, tag):
    if command("git", "status", "--porcelain"):
        raise ValueError("Working tree must be clean before publishing a release")
    refs = command(
        "git", "ls-remote", REPOSITORY_URL, "refs/heads/main", f"refs/tags/{tag}"
    )
    refs = dict(
        (ref, commit) for commit, ref in (line.split() for line in refs.splitlines())
    )
    if refs.get("refs/heads/main") != sha:
        raise ValueError("HEAD must match GitHub main. Merge the version PR first.")
    if f"refs/tags/{tag}" in refs:
        raise ValueError(f"Tag {tag} already exists. Use a new package version.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--publish",
        action="store_true",
        help="create the GitHub release and trigger PyPI publishing",
    )
    mode.add_argument("--check-tag", help="verify a release tag against setup.cfg")
    args = parser.parse_args(argv)
    try:
        version = read_version(ROOT)
        tag = f"v{version}"
        if args.check_tag is not None:
            if args.check_tag != tag:
                raise ValueError(f"Release tag must be {tag}, got {args.check_tag!r}")
            print(f"Verified {tag}")
            return 0
        sha = command("git", "rev-parse", "HEAD")
        release = release_command(version, sha)
        if not args.publish:
            print("Preview only; no tag, release, or PyPI upload was created.")
            print(shlex.join(release))
            print("After merging to main, run this script with --publish.")
            return 0
        validate_checkout(sha, tag)
        command("gh", "auth", "status")
        print(command(*release))
        print("GitHub release created. Follow the Release workflow for PyPI status.")
        return 0
    except (OSError, ValueError, configparser.Error) as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
