# gfo – Git Forge Operator

A Python CLI that operates several Git hosting services through **one set of commands**.

## Project

| Item | Value |
|---|---|
| Package | `gfo` |
| Entry point | `gfo.cli:main` |
| Python | 3.11 or later |
| License | 0BSD |

### Supported services

| Service | Identifier | Credential environment variable |
|---|---|---|
| GitHub | `github` | `GITHUB_TOKEN` |
| GitLab | `gitlab` | `GITLAB_TOKEN` |
| Bitbucket Cloud | `bitbucket` | `BITBUCKET_TOKEN` (`email:api-token`) |
| Azure DevOps | `azure-devops` | `AZURE_DEVOPS_PAT` |
| Gitea | `gitea` | `GITEA_TOKEN` |
| Forgejo | `forgejo` | `GITEA_TOKEN` |
| Gogs | `gogs` | `GITEA_TOKEN` |
| GitBucket | `gitbucket` | `GITBUCKET_TOKEN` |
| Backlog | `backlog` | `BACKLOG_API_KEY` (sent as the `apiKey` query parameter) |

## Instruction files

The detailed rules live in nested `AGENTS.md` files. Some tools load one only after reading a file in its directory, and others never do, so read the matching file yourself before editing these paths:

| Paths | Read first |
|---|---|
| `src/gfo/**`, `tests/**` (exceptions); `src/gfo/config.py`, `auth.py`, `detect.py`, `tests/test_config.py`, `tests/test_auth.py` | `src/gfo/AGENTS.md`: exception hierarchy, configuration and authentication |
| `src/gfo/adapter/**`, `tests/test_adapters/**`, any `github.py`, `gitlab.py`, `bitbucket.py`, `azure_devops.py`, `backlog.py`, `gitea.py`, `forgejo.py`, `gogs.py`, `gitbucket.py` and their `test_*.py`, `src/gfo/commands/init.py`, `src/gfo/commands/repo.py` | `src/gfo/adapter/AGENTS.md`: shared adapter conventions and each service's rules |
| `src/gfo/cli.py`, `src/gfo/commands/**`, `tests/test_cli.py` | `src/gfo/commands/AGENTS.md`: checklist for adding a subcommand |
| `tests/**` | `tests/AGENTS.md`: testing conventions |

## Language

- Commit messages, pull request and issue titles and bodies are English.
- Code identifiers, shell, YAML keys, types and the technical terms in comments are English. Comments and docstrings may otherwise be Japanese.
- User documentation comes in English and Japanese pairs (`docs/<name>.md` and `docs/<name>.ja.md`), changed together.
- This rule does not govern conversational replies.

## Stack and commands

- **Runtime dependency**: `requests` only.
- **Development dependencies** (`[dependency-groups]`): `pytest`, `responses` (HTTP mocks), `pytest-cov`, `pytest-xdist` (CI runs `-n 4`), `ruff`, `bandit`, `mypy`, `types-requests`, `pre-commit`.
- **Build**: `hatchling`; the version is in `src/gfo/__init__.py`.
- **Toolchain**: `mise` pins Python and uv; `uv` resolves dependencies and installs from `uv.lock`. Run tools through `uv run`, not `python -m`.

```bash
mise install
uv sync                              # installs the dev dependency group by default
uv run pytest                        # unit tests; no coverage, integration tests excluded
uv run pytest --cov=gfo --cov-report=term-missing -n auto
uv run pytest tests/test_commands/test_pr.py -v
uv run ruff check .
uv run ruff format .
uv run mypy src/gfo
uv run bandit -r src/gfo -c pyproject.toml
uv run pre-commit install            # hooks run through uv run
```

- Commit `uv.lock` with hashes. A dependency change runs `uv lock` and includes the lock in the same PR. CI runs `uv sync --locked`, so a stale lock fails.

## CI and supply chain

- **CI** (`.github/workflows/ci.yml`) runs every job on GitHub-hosted `ubuntu-latest`: gfo is public and Actions are free, so self-hosted runners are not used. It runs ruff, `ruff format --check`, mypy, bandit and pytest.
  - **Integration tests never run in CI**, since they reach real services; `addopts` in `pyproject.toml` ignores `tests/integration`.
  - Hardening: `permissions: contents: read`, `persist-credentials: false`, every action pinned to a 40-character commit SHA, and a step that checks the pins.
- **Dependabot** (`.github/dependabot.yml`) updates `uv` and `github-actions` weekly (Monday 06:00 JST) with a 7-day `cooldown` that holds back fresh releases. Merge only PRs whose CI passed.
- **Release and PyPI** (`.github/workflows/release.yml`): a `v*` tag push publishes to PyPI through **Trusted Publishing (OIDC)**, so no token secret exists. The `build` job (checkout, `contents: read`) is separate from the `publish` job (OIDC `id-token: write`, no checkout, GitHub Environment `pypi`), which keeps source checkout and token issuance apart. Actions are SHA-pinned as in `ci.yml`. Releases go through the `release` skill: bump, PR, CI green, `--merge`, tag the merge commit on `main`, push the tag. PyPI needs the Trusted Publisher (workflow `release.yml`, environment `pypi`) registered once.
- The repository is public: **never put secrets, tokens or internal URLs in commits, issues or PRs.**

## Workflow

GitHub enforces the rulesets: `main-protection` on `main`, `release-tags` on release tags.

- Never commit or push to `main` directly, and never force-push it. Cut a feature branch (`git switch -c <kebab>`), commit, push, `gh pr create --base main`, and self-merge with `gh pr merge --merge` once CI is green (squash is disabled).
- Never merge red CI. Read the actual `gh pr checks` output before merging, and do not pipe `gh pr checks --watch` into another command.
- File an issue before starting on a problem you found. The backlog lives in GitHub Issues (`gh`), not in notes, TODO comments or handoff documents.
- Stage files explicitly by path. Before committing, run `~/.local/bin/ai-agent-security-check --staged`, and `~/.local/bin/ai-agent-comment-check --staged` when code comments changed.
- Conventional Commits: header about 72 characters at most; scopes such as `cli, adapter, github, gitlab, pr, issue, release, http, config, auth, ci, deps, docs`.
- Once a general rule ("always do Y for X") is confirmed, keep applying it mechanically as its reach grows. Raise a candidate exception as a separate question instead of narrowing the rule yourself.
- A command added or changed updates `docs/commands.md` and `docs/commands.ja.md` in the same PR.

## Engineering

- Code comments explain durable constraints, invariants, or reasons the code cannot show. They do not carry task plans, change narratives, dates, issue or PR references, references to other documents, or promises of future work.
- Before fixing a bug, write a test that reproduces it. For a concurrency bug, use a harness that forces the concurrent execution.
- Judge a performance change by whether it makes gfo faster, not by effect size alone. Benchmark before claiming a speedup, with repeated, interleaved runs where practical.
- Rank options with materially different tradeoffs by what a new tool would choose today and whether it stays sound long term; diff size or effort alone is not a tiebreaker. When the user must decide, give the background, two to four options with their effect on users, operations and long-term debt, and a recommendation.

## Requires confirmation

Confirm with the user first, one item at a time:

- Adding a dependency.
- Creating, moving or deleting a release tag, or deleting a remote release; any other destructive operation.
- Rewriting published history; pushing to `main` directly is forbidden either way.
- Editing or deleting files outside this repository.

Without confirmation: feature branches, commits, pushes, PRs, and self-merging once CI is green.

## Layout

```text
src/gfo/
├── cli.py / auth.py / config.py / detect.py / exceptions.py
├── git_util.py / http.py / output.py
├── i18n.py / _context.py / locale/   # gettext (ja): .po is committed, hatch_build.py builds .mo
├── adapter/
│   ├── base.py          # GitServiceAdapter abstract base (re-exports the shared helpers)
│   ├── models.py        # dataclasses (PullRequest, Issue and others)
│   ├── github_like.py   # GitHubLikeAdapter: the _to_* conversion mixin shared by GitHub and the Gitea family
│   ├── _helpers.py      # _wrap_conversion_error and friends (breaks the base <-> github_like cycle)
│   ├── registry.py      # @register decorator, create_adapter()
│   ├── github.py / gitlab.py / bitbucket.py / azure_devops.py
│   ├── backlog.py / gitea.py / forgejo.py / gogs.py / gitbucket.py
└── commands/            # 30+ subcommand modules

tests/
├── conftest.py / test_adapter_base.py / test_auth.py / test_cli.py / test_config.py
├── test_adapters/       # one suite per adapter
├── test_commands/       # one suite per command (make_args() helper)
└── integration/         # tests against real services (not in CI)

docs/
├── commands.md / commands.ja.md                   # every subcommand's options
├── authentication.md / authentication.ja.md       # per-service authentication setup
├── cli-comparison.md                              # comparison with gh, glab and others
├── integration-testing.md / integration-testing.ja.md
├── unsupported.md                                 # features left out on purpose, with the reasons
└── feature-support-matrix.json                    # machine-readable mirror of the README matrix (updated by hand)
```
