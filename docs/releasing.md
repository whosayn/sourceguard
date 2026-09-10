# Releasing Sourceguard

GitHub releases are the source of release events. Publishing a release triggers
`.github/workflows/release.yml`, which runs the six-platform/version test jobs,
verifies the tag matches `setup.cfg` and the commit belongs to `main`, builds a
wheel and source distribution, checks their metadata, tests the installed wheel,
and uploads the distributions to PyPI. The same files are then attached to the
GitHub release. Draft releases don't publish to PyPI.

## One-time setup

You need maintainer access to the `sourceguard` project on PyPI and admin access
to `whosayn/sourceguard` on GitHub.

1. In GitHub, open **Settings → Environments**, create an environment named
   **pypi**, and allow deployment tags matching **v***. Release workflows run
   against a tag, so allowing only the `main` branch would block publishing.
   You can optionally require your approval before the publishing job runs.
2. In [PyPI's Sourceguard publishing settings](https://pypi.org/manage/project/sourceguard/settings/publishing/),
   add a GitHub Trusted Publisher with these exact values:

   | Field | Value |
   | --- | --- |
   | Owner | `whosayn` |
   | Repository | `sourceguard` |
   | Workflow filename | `release.yml` |
   | Environment | `pypi` |

3. Merge this workflow and its helper into `main` before creating the first
   release. Consider a tag ruleset protecting `v*` so release tags can't be
   rewritten or deleted accidentally.

No `PYPI_TOKEN` secret is needed. The publishing job uses GitHub's short-lived
OIDC identity, and PyPI generates package attestations automatically through the
publishing action. See [PyPI's Trusted Publishing documentation](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Build distributions locally

Install the build tools in your Python environment, then build without publishing:

```sh
python -m pip install build twine
python scripts/release.py --build
```

This builds a source archive and a wheel from that archive using isolated build
environments, validates both with `twine check --strict`, and saves them in
`dist/`. It works on a feature branch with uncommitted changes for local testing.
Each build uses a fresh staging directory, so old files in `dist/` cannot satisfy
validation. Existing artifacts are preserved unless replaced by validated files
with the same name.

## Each release

1. Open a PR that updates `[metadata] version` in `setup.cfg` to a new, unused
   version. Use `X.Y.Z` for stable releases or `X.Y.Zrc1`, `X.Y.Za1`, or `X.Y.Zb1`
   for prereleases. Do not reuse `1.0.1` for the new code.
2. Merge the PR after CI passes, then check out the updated `main` locally:

   ```sh
   git switch main
   git pull --ff-only origin main
   python scripts/release.py
   ```

   The script defaults to a local-only preview and prints the exact release
   command. It neither changes files nor publishes anything in preview mode.
3. Install [GitHub CLI](https://cli.github.com/) and authenticate with
   `gh auth login` if needed. Then publish:

   ```sh
   python scripts/release.py --publish
   ```

   The helper first builds and validates the wheel and source archive locally.
   A build or metadata failure prevents release creation. It requires the build
   tools above and a clean working tree. It verifies `HEAD` matches GitHub's
   `main` and rejects an existing release tag. It creates `v<version>` at that
   exact commit with generated release notes. Prerelease versions are marked as
   prereleases on GitHub. It doesn't push commits to `main`. The workflow builds
   its own distributions from the tagged commit for PyPI and GitHub assets;
   the local build is a preflight check, not an upload.
4. Watch **Actions → Release** and approve the `pypi` environment if configured.
   A published GitHub release doesn't mean the PyPI upload has finished: wait
   for the workflow to complete, then verify the new version on PyPI.

You can also use **GitHub → Releases → Draft a new release**. Create a tag such
as `v1.1.0` on the merged version commit, generate the notes, and publish it.
The tag must exactly equal `v` plus the version in `setup.cfg`. Mark preview
versions as prereleases. Both stable releases and published prereleases trigger
the workflow, and prereleases are uploaded to the real PyPI index.

## If a release fails

- A tag/version mismatch or a commit outside `main` stops publishing. Correct
  the release process; don't move a tag that has already shipped to users.
- If authentication fails before any upload, check the four Trusted Publisher
  fields and the `pypi` environment's tag policy, then rerun failed jobs.
- If only the GitHub asset upload fails, rerun failed jobs. That job reuses the
  saved distributions without republishing to PyPI.
- PyPI versions and distribution files are immutable. The workflow deliberately
  does not skip duplicate uploads. If a publish partially succeeds, inspect
  PyPI before retrying; don't rebuild and overwrite that version. Use a new
  patch release if necessary. Artifacts are retained for 30 days.
- The badges report actual hosted workflow runs and the published PyPI version.
  They won't show the new workflow's status until it has been pushed and run.
