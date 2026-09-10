# Sourceguard

[![Tests](https://github.com/whosayn/sourceguard/actions/workflows/tests.yml/badge.svg?branch=main&event=push)](https://github.com/whosayn/sourceguard/actions/workflows/tests.yml)
[![Release](https://github.com/whosayn/sourceguard/actions/workflows/release.yml/badge.svg)](https://github.com/whosayn/sourceguard/actions/workflows/release.yml)
[![PyPI version](https://img.shields.io/pypi/v/sourceguard.svg)](https://pypi.org/project/sourceguard/)

**Turn repeated code review comments into team rules.**

“Use our approved client.” “Don't commit focused tests.” “Stop adding calls to
that deprecated API.” Write the rule once; Sourceguard checks newly added Git
lines locally and in CI. Adopt standards without fixing all your legacy code.

- **Small policies:** literal strings or regexes, file globs, useful messages.
- **Gradual rollout:** observe warnings first, enforce rules when they're ready.
- **Useful feedback:** stable rule IDs, JSON output, and GitHub annotations.
- **Local execution:** Python 3.9+, Git, no runtime dependencies or hosted service.

## Try it

Install from a checkout of this repository:

```sh
python -m pip install .
sourceguard --init --preset javascript
sourceguard --check-config
```

Use `--preset python` for Python debugger checks. `--list-presets` shows the
available starters. These are editable examples, not comprehensive lint rules.
They start as warnings so trying Sourceguard doesn't block your team.

Commit the generated `sourceguard.json`, stage a change, then run:

```sh
git add .
sourceguard
```

For a newly added `test.only(...)`, you'll see:

```text
tests/cart.test.ts:12: warning [js-no-focused-tests] Remove .only so the full test suite runs.
```

Run from any directory in the repository. Only the staged version is checked;
unstaged edits and existing lines are ignored. Checking never creates files.

## Your team's first rule

Use `sourceguard --init` for a custom-rule starter, or edit `sourceguard.json`:

```json
{
  "version": 1,
  "exclude": ["vendor/*", "node_modules/*", "dist/*"],
  "rules": [
    {
      "id": "use-approved-client",
      "literal": "legacyClient(",
      "message": "Use approvedClient() instead of the deprecated client.",
      "files": ["*.ts", "*.tsx"],
      "exclude": ["tests/legacy/*"],
      "severity": "warning"
    }
  ]
}
```

`literal` matches exactly, including punctuation. For flexible matching, replace
it with `"pattern": "\\blegacyClient\\s*\\("`. Specify exactly one of these fields.
Run `sourceguard --check-config` to catch typos and invalid regular expressions.

The policy rejects unknown fields, duplicate IDs, and duplicate JSON keys, so
misspelled exclusions or severity settings don't silently change enforcement.

## Roll out without disrupting developers

```sh
sourceguard --base origin/main --fail-on never   # observe all findings
sourceguard --base origin/main                  # block errors, report warnings
sourceguard --base origin/main --fail-on warning # block both
```

Change individual rules from `"warning"` to `"error"` as they become trusted.
Rules without a severity default to `error`. Even with `--fail-on never`, broken
configuration or Git failures return exit code 2.

| Exit code | Meaning |
| --- | --- |
| 0 | No blocking findings, or successful setup/validation |
| 1 | Findings reached the selected blocking threshold |
| 2 | Configuration, Git, or invocation error |

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
features. The hook scans the Git index once, without accepting filenames.
`pre-commit run --all-files` still checks only staged additions.

## CI and GitHub annotations

```sh
sourceguard --base origin/main --format github
sourceguard --base origin/main --format json
```

`--base REF` compares the merge base of `REF` and `HEAD` to `HEAD`, excluding
staged and unstaged edits. Fetch the target branch and enough history to find a
merge base first. An invalid ref or insufficient history returns an error.

In a GitHub Actions job with Sourceguard installed, `--format github` emits
file/line annotations for findings. It needs no API token or comment bot.
`--format json` emits an array with `path`, `line` (integer), `pattern`,
`description`, `rule_id`, and `severity`; a clean run returns `[]`.
Diagnostics go to stderr.

## Configuration and matching reference

`sourceguard.json` takes precedence over the legacy `.banned` Python config.
Existing `.banned` policies still work, and `--init` never overwrites an existing
policy. `--config path/to/rules.json` selects an alternate config relative to the
repository root. Use a `.json` suffix for declarative policies; other config
paths use the legacy Python loader. `python -m sourceguard` works too.

- `version` must be `1`; `rules` must be an array, which may be empty.
- Each JSON rule needs a unique `id`, a `message`, nonempty `files`, and exactly
  one of `literal` or `pattern`. `exclude` and `severity` are optional.
- File selectors and exclusions are repository-relative globs. `*.py` matches
  Python files at any depth. `vendor/*` includes nested files under the root
  `vendor` directory: `*` can cross directory separators.
- Every matching rule runs. A rule matching several file globs reports only once
  per added line. Separate rules can report on the same line.
- Patterns are Python regexes applied independently to each added line.
  Whitespace is preserved and anchors match source text, not line numbers.
- Deleted lines, unchanged context, pure renames, and Git binary patches are
  ignored. Modified lines count as newly added lines.

Legacy example:

```python
from sourceguard.banrule import BanRule

BANRULES_MAP = {
    "*.py": [
        BanRule(
            r"\bos\.path\.join\s*\(",
            "Use pathlib.Path instead.",
            excluded_paths=["vendor/*"],
            id="use-pathlib",
            severity="warning",
        )
    ]
}
```

Legacy rules without IDs get a deterministic ID derived from their pattern.
Their default severity remains `error`, and the Python `run()` API still returns
its original four-element tuples.

JSON policies are data; `.banned` is executable Python. Both are loaded from the
working tree, including in CI. Only load Python configs you trust. Matching is
line-based and syntax-unaware: comments and strings can match, multiline
patterns are unsupported, and rules should be reviewed for false positives.
Sourceguard is a lightweight team policy check, not a security scanner or a
replacement for language-aware linting.

## Development

```sh
python -m unittest discover -s tests -v
```

Tests cover actual temporary Git repositories, policy validation, gradual
rollout, starter examples, and CI output.

## Releases

Publishing a GitHub release triggers tests, package builds, and automatic PyPI
publishing. Maintainers can preview a release with `python scripts/release.py`
and create it with `python scripts/release.py --publish` after merging the version
change to `main`. See [the release guide](docs/releasing.md) for the one-time PyPI
setup and release steps.
