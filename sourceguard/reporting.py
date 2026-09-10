"""Stable findings for terminals, CI annotations, and automated consumers."""

from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    pattern: str
    description: object
    rule_id: str
    severity: str


def _escape(value, property_value=False):
    value = str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if property_value:
        value = value.replace(":", "%3A").replace(",", "%2C")
    return value


def render(findings, format):
    if format == "json":
        return json.dumps([asdict(finding) for finding in findings])
    output = []
    for finding in findings:
        if format == "github":
            output.append(
                f"::{finding.severity} file={_escape(finding.path, True)},"
                f"line={finding.line},title={_escape(finding.rule_id, True)}::"
                f"{_escape(finding.description)}"
            )
        else:
            output.append(
                f"{finding.path}:{finding.line}: {finding.severity} "
                f"[{finding.rule_id}] {finding.description}"
            )
    return "\n".join(output)


def has_blocking_findings(findings, fail_on):
    if fail_on == "never":
        return False
    return any(
        fail_on == "warning" or finding.severity == "error" for finding in findings
    )
