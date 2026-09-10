"""Portable, strictly validated policies; legacy Python policies remain supported."""

import json
import re
import runpy

from sourceguard.banrule import BanRule
from sourceguard.engine import get_change_validation_engine

DEFAULT_CONFIG = "sourceguard.json"

PRESETS = {
    "python": [
        {
            "id": "python-no-debugger",
            "pattern": r"^\s*(?:breakpoint\s*\(|(?:pdb|ipdb)\.set_trace\s*\()",
            "message": "Remove the interactive debugger before shipping.",
            "files": ["*.py"],
            "severity": "warning",
        },
    ],
    "javascript": [
        {
            "id": "js-no-debugger",
            "pattern": r"^\s*debugger\s*(?:;|$)",
            "message": "Remove the debugger statement before shipping.",
            "files": ["*.js", "*.jsx", "*.ts", "*.tsx", "*.mjs", "*.cjs"],
            "severity": "warning",
        },
        {
            "id": "js-no-focused-tests",
            "pattern": r"\b(?:it|test|describe)\.only\s*\(",
            "message": "Remove .only so the full test suite runs.",
            "files": ["*.js", "*.jsx", "*.ts", "*.tsx", "*.mjs", "*.cjs"],
            "severity": "warning",
        },
    ],
}


def _unknown_keys(value, allowed, where):
    unknown = value.keys() - allowed
    if unknown:
        raise ValueError(f"{where}: unknown field(s): {', '.join(sorted(unknown))}")


def _strings(value, where, nonempty=False):
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item.strip() for item in value)
        or (nonempty and not value)
    ):
        raise ValueError(f"{where} must be a list of nonempty strings")
    return value


def parse_policy(data):
    if not isinstance(data, dict):
        raise ValueError("Policy must be a JSON object")
    _unknown_keys(data, {"version", "rules", "exclude"}, "Policy")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Policy version must be 1")
    if not isinstance(data.get("rules"), list):
        raise ValueError("Policy rules must be a list")
    excluded = _strings(data.get("exclude", []), "Policy exclude")
    rules_map, ids = {}, set()
    for index, item in enumerate(data["rules"]):
        where = f"Rule {index + 1}"
        if not isinstance(item, dict):
            raise ValueError(f"{where} must be an object")
        _unknown_keys(
            item,
            {"id", "pattern", "literal", "message", "files", "exclude", "severity"},
            where,
        )
        rule_id = item.get("id")
        if not isinstance(rule_id, str) or not re.fullmatch(
            r"[a-zA-Z0-9][\w.-]*", rule_id
        ):
            raise ValueError(f"{where}: id must use letters, numbers, _, . or -")
        if rule_id in ids:
            raise ValueError(f"Duplicate rule id: {rule_id}")
        ids.add(rule_id)
        if ("pattern" in item) == ("literal" in item):
            raise ValueError(f"{rule_id}: specify exactly one of pattern or literal")
        pattern = item.get("pattern", item.get("literal"))
        if not isinstance(pattern, str) or not pattern:
            raise ValueError(f"{rule_id}: pattern or literal must be a nonempty string")
        if "literal" in item:
            pattern = re.escape(pattern)
        message = item.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError(f"{rule_id}: message must be a nonempty string")
        severity = item.get("severity", "error")
        if severity not in ("error", "warning"):
            raise ValueError(f"{rule_id}: severity must be error or warning")
        files = _strings(item.get("files"), f"{rule_id}: files", nonempty=True)
        ignores = _strings(item.get("exclude", []), f"{rule_id}: exclude")
        rule = BanRule(pattern, message, excluded + ignores, rule_id, severity)
        for glob in files:
            rules_map.setdefault(glob, []).append(rule)
    return rules_map


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def load_config(path):
    if not path.is_file():
        raise ValueError(
            f"Config not found: {path}. Run sourceguard --init to get started."
        )
    if path.suffix == ".json":
        rules = parse_policy(
            json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
        )
    else:
        namespace = runpy.run_path(str(path))
        if "BANRULES_MAP" not in namespace:
            raise ValueError(f"{path} must define BANRULES_MAP")
        rules = namespace["BANRULES_MAP"]
    return get_change_validation_engine(rules)


def resolve_config(root, explicit=None):
    if explicit:
        return root / explicit
    # Keep existing installations working; never silently replace an existing policy.
    for name in (DEFAULT_CONFIG, ".banned"):
        if (root / name).is_file():
            return root / name
    return root / DEFAULT_CONFIG


def create_policy(path, preset=None):
    rules = (
        PRESETS[preset]
        if preset
        else [
            {
                "id": "use-approved-client",
                "literal": "legacyClient(",
                "message": "Use approvedClient() instead of the deprecated client.",
                "files": ["*.py", "*.js", "*.ts", "*.tsx"],
                "severity": "warning",
            }
        ]
    )
    data = {
        "version": 1,
        "exclude": ["vendor/*", "node_modules/*", "dist/*"],
        "rules": rules,
    }
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(data, indent=2) + "\n")
