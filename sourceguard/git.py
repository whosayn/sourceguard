"""Read Git patches without changing the caller's working directory."""

import ast
import re
import subprocess
from dataclasses import dataclass
from typing import Iterator, List


class GitError(ValueError):
    pass


def _git(*args, cwd=None):
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise GitError(result.stderr.strip() or "Git command failed")
    return result.stdout


def get_project_root_dir() -> str:
    return _git("rev-parse", "--show-toplevel").strip()


def get_diff_output(root_dir: str, base=None) -> str:
    args = [
        "-c",
        "core.quotePath=false",
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--unified=0",
        "--find-renames",
        "--src-prefix=a/",
        "--dst-prefix=b/",
    ]
    args.extend(["--cached"] if base is None else [f"{base}...HEAD"])
    return _git(*args, "--", cwd=root_dir)


@dataclass(frozen=True)
class FileDiff:
    filepath: str
    diff_lines: List[str]


def parse_file_diff(iterator: Iterator[str]) -> Iterator[FileDiff]:
    filename = ""
    added_lines = []
    line_no = 0
    remaining = 0
    for line in iterator:
        if line.startswith("diff --git "):
            if filename and added_lines:
                yield FileDiff(filename, added_lines)
            filename, added_lines, remaining = "", [], 0
        elif remaining and line.startswith("+"):
            added_lines.append(f"{line_no}: {line[1:]}")
            line_no += 1
            remaining -= 1
        elif remaining and line.startswith(" "):
            line_no += 1
            remaining -= 1
        elif line.startswith("+++ "):
            if filename and added_lines:
                yield FileDiff(filename, added_lines)
            path = line[4:].split("\t", 1)[0]
            if path.startswith('"'):
                path = ast.literal_eval(path)
            filename = path[2:] if path.startswith("b/") else ""
            added_lines = []
        elif line.startswith("@@ "):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                line_no = int(match[1])
                remaining = int(match[2]) if match[2] is not None else 1
    if filename and added_lines:
        yield FileDiff(filename, added_lines)


def get_changed_files_diffs(diff_output: str) -> Iterator[FileDiff]:
    yield from parse_file_diff(iter(diff_output.split("\n")))
