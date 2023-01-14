import re
from pathlib import Path
from typing import Dict
from typing import Generator
from typing import Iterator

from sourceguard.git import FileDiff
from sourceguard.banrule import BanRule

ExtensionPattern = str
BanRulesMap = Dict[ExtensionPattern, Iterator[BanRule]]


class Validator:

    def __init__(self, banrules: Iterator[BanRule]):
        self.pattern_lookup = {
            banrule.pattern: banrule
            for banrule in banrules
        }
        combined_patterns = "|".join(banrule.pattern for banrule in banrules)
        self.regex = re.compile(
            combined_patterns) if combined_patterns else None

    def validate(self, file_diff: FileDiff) -> Generator[BanRule, None, None]:

        def file_not_in_excluded_path(banrule: BanRule) -> bool:
            if not banrule.excluded_paths:
                return True

            return any(
                Path(excluded_path).match(file_diff.filepath)
                for excluded_path in banrule.excluded_paths)

        if not self.regex:
            return

        matches = (self.regex.match(diff_line.strip())
                   for diff_line in file_diff.diff_lines)

        yield from filter(file_not_in_excluded_path,
                          (self.pattern_lookup[match.group(0)]
                           for match in matches if match is not None))


class ValidationEngine:

    def __init__(self, validators: Dict[ExtensionPattern, Validator]):
        self.validators = validators

    def validate(self, file_diff: FileDiff) -> Generator[BanRule, None, None]:
        filepath = Path(file_diff.filepath)
        extension_pattern = next(
            filter(filepath.match,
                   (extension_pattern
                    for extension_pattern in self.validators.keys())), "")
        if not extension_pattern:
            return

        validator = self.validators[extension_pattern]
        yield from ((file_diff.filepath, failed_rule.pattern,
                     failed_rule.description)
                    for failed_rule in validator.validate(file_diff))


def get_change_validation_engine(banrules_map: BanRulesMap):
    validators = {
        extension_pattern: Validator(rules)
        for extension_pattern, rules in banrules_map.items()
    }
    return ValidationEngine(validators)
