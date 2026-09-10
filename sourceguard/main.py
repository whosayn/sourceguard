"""Command-line entry point and public patch validation API."""

import argparse
import sys
from pathlib import Path

from sourceguard.engine import get_change_validation_engine
from sourceguard.config import PRESETS, create_policy, load_config, resolve_config
from sourceguard.reporting import render, has_blocking_findings
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
        "--init", action="store_true", help="create a portable JSON policy"
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="starter rules to copy into a new policy (with --init)",
    )
    parser.add_argument(
        "--list-presets", action="store_true", help="list built-in starter policies"
    )
    parser.add_argument("--config", help="config path (relative to repository root)")
    parser.add_argument(
        "--base", help="check committed changes since merge base with REF"
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate policy without scanning Git changes",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "never"),
        default="error",
        help="blocking threshold (default: error)",
    )
    parser.add_argument("--format", choices=("text", "json", "github"), default="text")
    args = parser.parse_args(argv)
    if args.preset and not args.init:
        parser.error("--preset requires --init")
    if args.list_presets:
        for name, rules in PRESETS.items():
            print(f"{name}: " + ", ".join(rule["id"] for rule in rules))
        return 0
    try:
        root = Path(get_project_root_dir())
        config = resolve_config(root, args.config)
        if args.init:
            if config.exists():
                print(f"Already exists: {config}")
            elif config.suffix == ".json":
                create_policy(config, args.preset)
                print(f"Created {config}; starter rules warn until promoted to errors.")
            else:
                if args.preset:
                    raise ValueError("--preset requires a .json config path")
                create_template_toplevel_banned_file(config)
                print(f"Created {config}")
            return 0
        engine = load_config(config)
        if args.check_config:
            print(f"Valid policy: {config}")
            return 0
        findings = [
            finding
            for diff in get_changed_files_diffs(get_diff_output(str(root), args.base))
            for finding in engine.findings(diff)
        ]
        output = render(findings, args.format)
        if output:
            print(output)
        return int(has_blocking_findings(findings, args.fail_on))
    except Exception as exc:
        print(f"sourceguard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
