# An adoption plan for Sourceguard

## The bet

Help a tech lead turn a repeated review comment into a useful, non-disruptive
check in five minutes. The initial customer is a team migrating a deprecated
internal API or standardizing on an approved library across a mixed-language
repository. Their conventions are too specific for off-the-shelf linters.

The pitch: **“Make that the last time you leave this review comment.”**

The next release now supports editable starter policies, non-executable JSON,
literal matching, stable rule IDs, warning-first rollout, configuration checks,
and GitHub annotations. These reduce the work needed to try one rule and see a
useful result. They don't prove that people want the product.

## What the ecosystem establishes

- [Semgrep supports custom rules](https://docs.semgrep.dev/writing-rules/rule-syntax)
  and [diff-aware CI](https://semgrep.dev/docs/semgrep-ci/sample-ci-configs).
  Those capabilities alone don't differentiate Sourceguard.
- [ast-grep's rule format](https://ast-grep.github.io/reference/yaml.html) includes
  messages, severity, file selection, and fixes. A more complex pattern engine
  would put Sourceguard in direct competition with mature tools.
- [Gitleaks](https://github.com/gitleaks/gitleaks/blob/master/README.md) offers
  default rules and pre-commit integration. A specific first-run outcome is a
  more compelling starting point than an empty configuration.
- [GitHub workflow annotations](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands)
  deliver file/line feedback without a separate hosted bot.

These are evidence of established workflows, not a survey proving demand for
Sourceguard. Our hypothesis is that small, transparent, project-specific policy
checks can win on setup effort and day-to-day usefulness.

## Next features, in priority order

| Priority | Capability | Concrete user problem | Proof to seek before expanding |
| --- | --- | --- | --- |
| 1 | Rule examples and `--test-rules` | A maintainer can't tell whether a new rule is noisy until it blocks someone | Three pilot teams maintain passing and failing examples for their rules |
| 2 | Versioned local/shared rule packs | Platform teams copy the same policy into several repositories and it drifts | Two teams ask to distribute the same rules across at least three repos |
| 3 | Exceptions with required reason and optional expiry | A legitimate migration exception forces teams to disable the whole check | Pilots report actual exceptions that can't be handled with a narrow file exclusion |
| 4 | Suggested replacements, then opt-in fixes | Developers see a ban but still have to work out the migration | Collect real before/after transformations; verify safe handling of partial staging before writing files |
| 5 | GitHub Action and editor feedback | Installation and waiting for CI add friction | Observe where pilot users abandon setup; package the path they use most |
| 6 | Trusted-base policy selection in CI | Teams need to evaluate a pull request against an approved policy rather than its edited config | A pilot needs a centrally enforced policy; define policy ownership and config-change review first |

Keep the next implementation focused on rule examples. Trust compounds when
users can demonstrate exactly what their rule catches and what it allows.
Don't build a cloud dashboard, AI rule generation, a marketplace, or telemetry
before there's evidence that an engaged team needs them.

## Get the first ten teams

1. Find maintainers currently asking contributors to stop using a deprecated API
   or repeat a concrete convention. Ask for examples of those review comments.
2. Build one rule with each consenting maintainer and demonstrate it against a
   real change. Observe time to the first useful finding and confusing steps.
3. Help them run in advisory mode for a week. Ask which findings were useful,
   which were noise, and whether the check stayed installed.
4. Publish three small, reproducible recipes: internal API migration, removing
   focused tests, and preventing interactive debuggers. Show the code change,
   output, exclusion, and warning-to-error rollout.
5. Release a versioned package and pinned pre-commit example after verification.
   Publish a short demo and request feedback in communities where the maintainers
   already participate. Outreach and publishing require separate authorization.

## Measure value, not repository stars

For the first ten pilots, record only information they voluntarily provide:

- Time from installation to the first useful check (target: under five minutes).
- Number still running after two weeks (initial target: six of ten).
- Useful findings divided by reviewed findings, per rule.
- Rules promoted from warning to error, and why others were disabled.
- Repeated review comments the team believes the rule removed.
- Requests to install it in a second repository.

These are proposed success criteria, not measured results. If teams don't retain
one useful rule, prioritize the learning over adding more features.
