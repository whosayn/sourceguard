from importlib.machinery import SourceFileLoader
import itertools
from pathlib import Path

from sourceguard.engine import BanRulesMap
from sourceguard.engine import get_change_validation_engine
from sourceguard.git import get_project_root_dir
from sourceguard.git import get_changed_files_diffs
from sourceguard.git import get_diff_output


def run(diff_output: str, banrules_map: BanRulesMap) -> None:
    validation_engine = get_change_validation_engine(banrules_map)
    failed_rules = itertools.chain.from_iterable(
        validation_engine.validate(file_diff)
        for file_diff in get_changed_files_diffs(diff_output))

    print(list(failed_rules))
    print(banrules_map)


def main() -> None:
    root_dir = get_project_root_dir()
    diff_output = get_diff_output(root_dir)

    ban_info_path = str(Path(root_dir).absolute() / ".banned")
    banrules = SourceFileLoader("banned", ban_info_path).load_module()

    run(diff_output, banrules.BANRULES_MAP)


if __name__ == "__main__":
    main()
