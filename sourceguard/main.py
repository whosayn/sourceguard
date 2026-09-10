"""Command-line entry point and public patch validation API."""
import argparse
import json
import runpy
import sys
from pathlib import Path

from sourceguard.engine import get_change_validation_engine
from sourceguard.git import (
    get_project_root_dir,
    get_changed_files_diffs,
    get_diff_output,
)

TEMPLATE = """from sourceguard.banrule import BanRule

# File paths are repository-relative globs; code patterns are Python regexes.
BANRULES_MAP = {
    "*.py": [
        BanRule(r"\\bos\\.path\\.join\\s*\\(", "Use pathlib.Path instead."),
    ],
}
"""


def run(diff_output, banrules_map):
    engine = get_change_validation_engine(banrules_map)
    return [
        finding
        for diff in get_changed_files_diffs(diff_output)
        for finding in engine.validate(diff)
    ]


def create_template_toplevel_banned_file(ban_info_path):
    try:
        with ban_info_path.open("x", encoding="utf-8") as file:
            file.write(TEMPLATE)
    except FileExistsError:
        return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Reject banned code patterns in newly added Git lines."
    )
    parser.add_argument(
        "--init", action="store_true", help="create an example .banned file"
    )
    parser.add_argument("--config", help="config path (relative to repository root)")
    parser.add_argument(
        "--base", help="check committed changes since merge base with REF"
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        root = Path(get_project_root_dir())
        config = root / (args.config or ".banned")
        if args.init:
            created = create_template_toplevel_banned_file(config)
            print(f"{'Created' if created else 'Already exists:'} {config}")
            return 0
        if not config.is_file():
            raise ValueError(
                f"Config not found: {config}. " "Run sourceguard --init to get started."
            )
        namespace = runpy.run_path(str(config))
        if "BANRULES_MAP" not in namespace:
            raise ValueError(f"{config} must define BANRULES_MAP")
        findings = run(get_diff_output(str(root), args.base), namespace["BANRULES_MAP"])
        if args.format == "json":
            print(
                json.dumps(
                    [
                        dict(
                            path=path,
                            line=int(line),
                            pattern=pattern,
                            description=description,
                        )
                        for path, line, pattern, description in findings
                    ]
                )
            )
        else:
            for path, line, pattern, description in findings:
                print(f"{path}:{line}: banned pattern {pattern!r}: " f"{description}")
        return 1 if findings else 0
    except Exception as exc:
        print(f"sourceguard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
