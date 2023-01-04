from dataclasses import dataclass
from invoke import run as run_command
import os
from typing import Generator
from typing import Iterator
from typing import List


LineInfo = str


def get_project_root_dir() -> str:
    result = run_command("git rev-parse --show-cdup", hide=True)
    assert result.ok

    project_root_dir = result.stdout.strip()
    return project_root_dir or "."


def get_diff_output(root_dir: str) -> str:
    os.chdir(root_dir)
    result = run_command("git diff --staged", hide=True)
    assert result.ok

    return result.stdout


@dataclass(frozen=True)
class FileDiff:
    filepath: str
    diff_lines: List[LineInfo]


def parse_file_diff(iterator: Iterator[str]) -> FileDiff:
    filename = ""
    added_lines = []
    for line in iterator:
        if line.startswith("+++ b"):
            if filename and added_lines:
                yield FileDiff(filename, added_lines)

            filename = os.sep.join(line.split(os.sep)[1:])
            added_lines = []
        elif line.startswith("+"):
            added_lines.append(line[1:])


def get_changed_files_diffs(
        diff_output: str) -> Generator[FileDiff, None, None]:
    diff_lines = diff_output.splitlines()
    diff_lines.append("+++ b")  # for simpler processing logic
    iterator = iter(diff_lines)
    yield from parse_file_diff(iterator)
    os.path.join(os.getcwd(), "tmp")  # TODO
