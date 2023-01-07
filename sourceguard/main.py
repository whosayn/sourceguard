import itertools
import sys
import textwrap
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import List
from typing import Tuple

from sourceguard.engine import BanRulesMap
from sourceguard.engine import get_change_validation_engine
from sourceguard.git import get_project_root_dir
from sourceguard.git import get_changed_files_diffs
from sourceguard.git import get_diff_output

Filename = str
BanRuleDescription = str
ValidationOutput = Tuple[Filename, BanRuleDescription]


def run(diff_output: str, banrules_map: BanRulesMap) -> List[ValidationOutput]:
    validation_engine = get_change_validation_engine(banrules_map)
    failed_diff_output = itertools.chain.from_iterable(
        validation_engine.validate(file_diff)
        for file_diff in get_changed_files_diffs(diff_output))

    return list(failed_diff_output)


def create_template_toplevel_banned_file(ban_info_path: Path) -> None:
    if ban_info_path.exists():
        return

    with open(ban_info_path, "w+") as fh:
        fh.write(
            textwrap.dedent('''
                from sourceguard.banrule import BanRule

                """
                Example

                BanRule(
                   "os.path.join",
                   "Please use pathlib.Path instead"
                   )
                """
                PYTHON_BANRULES = [
                ]

                # maps extension regex to banrules
                BANRULES_MAP = {
                    "*.py" : PYTHON_BANRULES
                }
                ''').strip())


def main() -> int:
    root_dir = get_project_root_dir()
    diff_output = get_diff_output(root_dir)

    if not (ban_info_path := Path(root_dir).absolute() / ".banned").exists():
        create_template_toplevel_banned_file(ban_info_path)

    banrules = SourceFileLoader("banned", str(ban_info_path)).load_module()

    if not (failed_diff_output := run(diff_output, banrules.BANRULES_MAP)):
        return 1

    for filepath, failure_description in failed_diff_output:
        print("There's a banned code fragment in {filepath}: "
              "\n\t{failure_description}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
