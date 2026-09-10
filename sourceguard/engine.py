"""Apply every matching rule to newly added source lines."""

import re
import hashlib
from fnmatch import fnmatchcase
from pathlib import PurePosixPath
from typing import Dict, Iterable

from sourceguard.banrule import BanRule
from sourceguard.reporting import Finding

BanRulesMap = Dict[str, Iterable[BanRule]]


def path_matches(filepath, pattern):
    return fnmatchcase(filepath, pattern) or PurePosixPath(filepath).match(pattern)


class Validator:
    def __init__(self, banrules):
        self.rules = []
        for rule in banrules:
            if not isinstance(rule, BanRule):
                raise ValueError("Rules must be BanRule instances")
            if rule.severity not in ("error", "warning"):
                raise ValueError("Rule severity must be error or warning")
            try:
                regex = re.compile(rule.pattern)
            except (re.error, TypeError) as exc:
                raise ValueError(
                    f"Invalid rule pattern {rule.pattern!r}: {exc}"
                ) from exc
            self.rules.append((rule, regex))

    def validate(self, file_diff):
        rules = [
            (rule, regex)
            for rule, regex in self.rules
            if not any(
                path_matches(file_diff.filepath, pattern)
                for pattern in rule.excluded_paths or ()
            )
        ]
        for line in file_diff.diff_lines:
            line_no, _, source = line.partition(": ")
            for rule, regex in rules:
                if regex.search(source):
                    yield rule, line_no


class ValidationEngine:
    def __init__(self, validators):
        self.validators = validators

    def findings(self, file_diff):
        seen = set()
        for pattern, validator in self.validators.items():
            if path_matches(file_diff.filepath, pattern):
                for rule, line_no in validator.validate(file_diff):
                    # One logical rule can select several overlapping file globs.
                    key = (id(rule), line_no)
                    if key in seen:
                        continue
                    seen.add(key)
                    rule_id = (
                        rule.id
                        or "legacy-"
                        + hashlib.sha256(rule.pattern.encode("utf-8")).hexdigest()[:12]
                    )
                    yield Finding(
                        file_diff.filepath,
                        int(line_no),
                        rule.pattern,
                        rule.description,
                        rule_id,
                        rule.severity,
                    )

    def validate(self, file_diff):
        for finding in self.findings(file_diff):
            yield (
                finding.path,
                str(finding.line),
                finding.pattern,
                finding.description,
            )


def get_change_validation_engine(banrules_map: BanRulesMap):
    if not isinstance(banrules_map, dict):
        raise ValueError("BANRULES_MAP must map file globs to lists of BanRule")
    return ValidationEngine(
        {pattern: Validator(rules) for pattern, rules in banrules_map.items()}
    )
