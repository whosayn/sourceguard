# Sourceguard

**Stop introducing code patterns your team has outgrown.** Sourceguard checks
newly added Git lines against your team's rules, so you can adopt a standard
without first cleaning up the entire codebase.

Use it to prevent deprecated APIs, debug statements, or project-specific
anti-patterns. Each rule explains what to use instead. It works on any text-based
language, needs only Python 3.9+ and Git, and has no runtime dependencies.

## Start in a minute

Install from a checkout of this repository:

```sh
python -m pip install .
sourceguard --init
```

This creates `.banned` at your repository root with an example rule:

```python
from sourceguard.banrule import BanRule

BANRULES_MAP = {
    "*.py": [
        BanRule(
            r"\bos\.path\.join\s*\(",
            "Use pathlib.Path instead.",
            excluded_paths=["vendor/*", "generated/*"],
        ),
    ],
}
```

Edit the rules for your team, commit `.banned`, then check your staged changes:

```sh
git add .
sourceguard
```

Example output:

```text
src/app.py:12: banned pattern '\\bos\\.path\\.join\\s*\\(': Use pathlib.Path instead.
```

Run from any directory in the repository. Only the staged version is checked;
unstaged edits and existing lines are ignored. A missing config produces an
error with setup instructions; checking never creates files.

## Pre-commit

For a checkout with Sourceguard installed, add this to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: sourceguard
        name: Sourceguard
        entry: sourceguard
        language: system
        pass_filenames: false
        always_run: true
        require_serial: true
```

Then run `pre-commit install`. This repository also exports a Python-language
`sourceguard` hook for remote use: pin its `rev` to a commit containing these
changes. The hook scans the Git index once, without accepting filenames.
`pre-commit run --all-files` still checks only staged additions.

## CI and tooling

To enforce rules on a branch's committed changes:

```sh
sourceguard --base origin/main
sourceguard --base origin/main --format json
```

`--base REF` compares the merge base of `REF` and `HEAD` to `HEAD`, excluding
staged and unstaged edits. Fetch the target branch and enough history to find a
merge base first. An invalid ref or insufficient history returns an error.

JSON output is an array of findings with `path`, `line` (integer), `pattern`, and
`description`; a clean run returns `[]`. Diagnostics go to stderr.

| Exit code | Meaning |
| --- | --- |
| 0 | No violations, or successful initialization |
| 1 | Banned patterns found |
| 2 | Configuration, Git, or invocation error |

Use `--config path/to/rules` for an alternate config, relative to the repository
root. `python -m sourceguard` works too. See `sourceguard --help` for all options.

## Rule semantics

- Map repository-relative file globs to lists of `BanRule` objects. `*.py`
  matches Python files at any depth. Every matching group is evaluated.
- Code patterns are Python regular expressions, searched independently on each
  added line. Escape literal dots (`r"os\.path\.join"`). Whitespace is preserved;
  anchors such as `^` match the source line, not the displayed line number.
- Each rule produces at most one finding per added line. Multiple rules can
  report on the same line.
- Exclusions use the same glob matching as file selectors. `vendor/*` matches
  files below the root `vendor` directory, including nested files; `*` can cross
  directory separators. A basename glob also matches at any depth.
- Deleted lines, unchanged context, pure renames, and Git binary patches are
  ignored. Modified lines count as newly added lines.

`.banned` is executable Python loaded from the working tree, including in CI.
Only load configs you trust. Regex matching is line-based and syntax-unaware:
comments and strings can match, and multiline patterns are not supported.
Sourceguard is a lightweight team policy check, not a security scanner or a
replacement for language-aware linting.

## Adopting with a team

Start with a few high-confidence rules and descriptions that show a concrete
replacement. Exclude generated and third-party code. Run on pull requests before
requiring it, and use reports to remove noisy rules. Existing violations remain
until their lines are edited, making gradual migration practical.

## Development

```sh
python -m unittest discover -s tests -v
```

Tests include real temporary Git repositories for staging, initial commits,
branch comparisons, renames, unusual filenames, and CLI behavior.
