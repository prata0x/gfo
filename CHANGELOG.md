# Changelog

## [0.10.0] - 2026-05-12

### Added
- `auth login`: added `--token-stdin` (read from stdin, recommended for CI) and `--token-file PATH` options
- `GFO_ALLOW_INSECURE_HTTP` environment variable: opt-in to allow `http://` for `api_url` (other than `localhost` / `127.0.0.1` / `::1`)
- `GFO_ALLOW_PRIVATE_HOSTS` environment variable: opt-in to allow API probing of private / loopback / link-local IPs (needed for internal Gitea/GitLab auto-detection)
- `GFO_MAX_DOWNLOAD_BYTES` environment variable: cap on streaming download size (default 5 GiB; `0` for unlimited)

### Fixed
- `pr list --state merged` (GitHub / Gitea): no longer undercounts when many closed PRs exist; paginates through all closed PRs before filtering
- `_resolve_label_ids` (Gitea): paginate all labels instead of relying on server-dependent `limit=0` behavior
- `_resolve_user_ids` (GitLab): raise `GfoError` for unresolved usernames instead of silently warning (prevents silent partial assignee/reviewer sync)
- `list_contributors` (Gitea): only catch `NotFoundError`; propagate auth / server / network errors instead of misreporting as unsupported
- `list_pull_request_files` / `list_requested_reviewers` (Azure DevOps): validate response is `dict` before `.get()`, raise `GfoError` on unexpected type
- `detect_service`: fall back to saved git config when remote URL cannot be retrieved (works in bare repos / CI without origin)
- `gfo config set/get` with unmatched quote in key: raise `ConfigError` instead of bare `ValueError`
- `git_checkout_branch`: replace locale-dependent stderr match with `git rev-parse --verify` (works under non-English locale)
- `repo compare` (GitLab): implement `additions` / `deletions` line counts (previously always `0`)
- `batch pr create`: narrow exception catch to `GfoError` so programming bugs surface instead of being recorded as "failed"

### Security
- `download_file`: strip auth headers / cookies / auth params when downloading from a cross-origin URL (prevents PAT leakage to GitLab `direct_asset_url` external hosts)
- `download_file`: enforce `GFO_MAX_DOWNLOAD_BYTES` ceiling (default 5 GiB) and delete partial file on overflow (mitigates malicious-server DoS)
- `download_release_asset` / `download_artifact` / `download_run_logs`: stricter path traversal guard using `Path.is_relative_to`, basename normalization for user-supplied IDs
- `GitLab.migrate_repository`: mask `auth_token` in every exception path (preserves exception type while rewriting `args`)
- `HttpError`: truncate response body at 4096 chars in error messages (prevents huge-body DoS)
- `detect.py` probes: disable redirects on `/api/*/version` probes (avoids redirect-based information disclosure)
- `auth login --token`: emit insecure warning (argv visible in process list); prefer `--token-stdin` / `--token-file`

### Breaking Changes
- `api_url` accepts only `https://` by default (was: any scheme). Use `GFO_ALLOW_INSECURE_HTTP=1` to opt in to plain HTTP; `localhost` / `127.0.0.1` / `::1` are always permitted
- Unknown-host service detection no longer probes private / loopback / link-local IPs by default. Set `GFO_ALLOW_PRIVATE_HOSTS=1` to restore (needed for internal Gitea/GitLab auto-detection)
- `GFO_INSECURE` no longer disables TLS verification for cloud-hosted services (github.com, gitlab.com, bitbucket.org, dev.azure.com, *.backlog.com / *.backlog.jp, *.visualstudio.com); a warning is printed to stderr on startup when set
- `auth login --token TOKEN`: deprecated (still works with a warning); migrate to `--token-stdin` / `--token-file`

## [0.9.0] - 2026-04-06

### Added
- `repo create`: support organization repositories via `org/repo` name format (e.g. `gfo repo create my-org/my-repo --private`)
- `repo create`: added `--internal` visibility flag for GitHub/GitLab organization repositories
- `repo migrate`: support organization repositories via `org/repo` format in `--name`
- `repo migrate`: added `--public` and `--internal` visibility flags (previously only `--private` existed)

### Fixed
- `--account` flag: now correctly hoisted as a global flag, except for `auth`/`init` subcommands which have their own `--account`
- `_hoist_global_flags`: subcommand detection no longer mistakes global flag values as subcommand names (e.g. `--format json auth` no longer misidentifies `json` as the subcommand)

### Breaking Changes
- `Repository.private: bool` replaced with `Repository.visibility: str` (`"public"`, `"private"`, `"internal"`)
- `repo list` output column changed from `private` to `visibility`
- `create_repository` / `migrate_repository` adapter method signatures changed: `private: bool` replaced with `visibility: str`, `organization: str | None` added

## [0.8.0] - 2026-03-29

### Added
- i18n: added 250 Japanese translation entries covering all `_()` strings
- `gfo -h` help output redesigned: grouped subcommands with descriptions, getting started section, usage examples, supported forges list, complete environment variable reference
- `config get/set/unset` help: added quoting rules for dot-containing keys
- `commands.md` / `commands.ja.md`: added 75 short option flags to documentation

### Fixed
- `GiteaAdapter.create_review`: send `APPROVED` event name instead of `APPROVE` (Gitea/Forgejo API requirement)
- `-R`/`--repo` override: git config `gfo.owner`/`gfo.repo` no longer overrides the CLI-specified repository
- Gogs detection: version `0.x` is now correctly identified as Gogs (previously misdetected as Gitea)
- `--remote`, `--repo`, `-R` flags: now hoisted as global flags so they work after subcommands
- Git repository detection: recognize `"can only be used inside a git repository"` error message
- `normalize_host`: preserve port number when URL format is passed (e.g. `http://localhost:3000`)
- `--host` option: automatically extract hostname from URLs across `init`, `auth login/switch/token/logout`
- Error messages: include `--non-interactive` and `--repo HOST/OWNER/REPO` usage hints

## [0.7.0] - 2026-03-25

### Added
- CLI short options: added 75 shorthand flags across all subcommands
- `read_file_arg` helper: unified file reading for `--body-file` / `--notes-file` options with consistent error handling
- mypy strict mode: enabled `disallow_untyped_defs = true` for full type safety
- Success messages for write/delete handlers (`file put`, `file delete`, `branch delete`, `tag delete`, `webhook delete`, etc.)

### Fixed
- `GiteaAdapter.create_issue`: label names are now resolved to IDs via `_resolve_label_ids()` (Gitea API requires integer IDs)
- `--jq` filter: fixed empty string check from `if jq:` to `if jq is not None:` to allow valid jq expressions
- `argparse.FileType` replaced with file path strings to avoid premature file handle issues
- `add_time_entry` duration type unified to `int | float` across all adapters
- Integration tests: fixed `test_02c_repo_contributors` for Gitea/Forgejo (API not implemented), fixed `test_40_file_crud` idempotency for GitBucket

## [0.6.0] - 2026-03-22

### Added

- `config` command with `get`, `set`, `list`, `unset`, `path` subcommands
- `auth token` command to display the current token
- `completion` command for shell completion
- `search code` command (GitHub/GitLab/Bitbucket/Azure DevOps)
- `ci delete` command (GitHub/GitLab/Azure DevOps)
- `release create --generate-notes` option (GitHub/GitLab)
- `--web` option extended to `pr`/`issue`/`release` `create`/`list`/`view`
- `pr` command extensions: `--draft`, `--ready`, `--milestone`, `subscribe`, `--dry-run`
- `issue` command extensions: `--due-date`, `--template`, `status`, `develop`
- `repo` command extensions: `unarchive`, `list --archived`, `create --readme`
- `pr create` / `issue create` `--body-file` (`-F`) option
- `repo create` now requires `--private` / `--public` flag

### Fixed

- Fix config key parsing for quoted notation with dot-containing keys
- Fix review issues: auth token, config `--jq`, limit+filter interaction, documentation

### Tests

- Add 115 unit tests for edge cases and error paths (coverage 90% → 91%)
- Add CLI integration tests with private member dependency removal
- Add SaaS integration tests with rate limiting delay
- Fix integration test issues (GitHub SHA, Bitbucket/Azure DevOps CI classification, timing, subprocess, SSH)

## [0.5.0] - 2026-03-20

### Added

- `pr list` filter options: `--author`, `--label`, `--assignee`, `--search`, `--base`, `--head`, `--draft` (B5-1–B5-7)
- `issue list` filter options: `--author`, `--milestone`, `--search` (B3-1–B3-3)
- `issue create --milestone` option (B3-4)
- `pr edit` / `issue edit` metadata options: `--add-label`, `--remove-label`, `--add-assignee`, `--remove-assignee`, `--milestone` (B2-1–B2-7)
- `pr merge --subject` / `--body` for custom merge commit message (B1-2)
- `branch view`, `tag view`, `deploy-key view`, `ssh-key view`, `gpg-key view` subcommands (F1-1–F1-5)
- `webhook edit`, `org edit`, `release-asset edit`, `tag-protect edit` subcommands (F2-1–F2-4)
- `pr status` subcommand (E1-1)
- `pr lock` / `pr unlock`, `issue lock` / `issue unlock` subcommands (E1-5–E1-6)
- CI extensions: `ci workflow`, `ci artifact`, `ci download`, `ci watch` with `--timeout` option (E1-3–E1-4, E1-7–E1-8)
- `issue subscribe` / `issue unsubscribe` subcommands (E1-9)
- `secret` / `variable` org-scope support (E1-10)
- `repo edit --name` for repository rename (E1-2)
- `repo sync` subcommand for fork synchronization (E2-1)

### Fixed

- Fix 19 code review issues: 9 major, 8 minor, 2 nitpick
- Fix 7 remaining code review issues

### Tests

- Fix 20 test code review issues (+713 tests, coverage 88% → 90%)

## [0.4.0] - 2026-03-20

### Breaking Changes

- Rename `update` subcommand to `edit` across all 8 commands (pr, issue, release, label, milestone, repo, wiki, branch-protect)
- Move `comment` command to `pr comment` / `issue comment` subcommands
- Move `review` command to `pr review` subcommand
- Replace `pr merge --method` with `--merge` / `--squash` / `--rebase` individual flags
- Change `credentials.toml` to new multi-account format

### Added

- `auth logout` subcommand
- `--web` / `-w` option for `view` / `list` subcommands (open in browser)
- `pr create` options: `--reviewer`, `--assignee`, `--label`, `--milestone`, `--fill`
- `release create --target` option

### Fixed

- Fix auth.py review issues (#1, #2, #3, #5, #6, #13)
- Fix command handler issues (#7, #9, #10, #11, #12, #21, #26)
- Fix `create_pull_request` issues (#4, #8)

## [0.3.0] - 2026-03-18

### Added

- `--repo` global option (specify target repository by URL or `HOST/OWNER/REPO`)
- `--remote` / `--host` global options and remote resolution fallback (origin → first available remote)
- Phase 1–6 multi-service feature expansion (50+ subcommands: PR operations, release/repo management, CI/security/org, issue/search/niche, batch/migrate)
- All `add_parser()` / `add_argument()` calls now include `help=_()` for schema output

### Fixed

- Schema output descriptions now always use English regardless of locale
- Eliminate dual version management (unified to hatchling dynamic version)

### Other

- Remove completed roadmap documents

## [0.2.2] - 2026-03-17

### Added

- `gfo schema` command (P4: JSON Schema metadata for all commands)
- Auto-switch to JSON output when stdout is not a TTY (P3: TTY detection)
- Fine-grained exit codes via `ExitCode(IntEnum)` mapped to each exception type
- Structured JSON error output on stderr when `--format json` is specified

### Fixed

- Fix issues from code review (H1-H4, M1-M8, L1-L3)
- Fix GCM opening browser during integration tests

### Other

- Remove `docs/roadmap.md` (P1–P4 complete, P5 deferred)

## [0.2.1] - 2026-03-17

### Added

- gettext-based i18n support (default English + Japanese locale)
- AI agent integration roadmap (`docs/roadmap.md`)

### Fixed

- Fix garbled Japanese output on Windows
- Fix i18n review issues (Windows locale normalization, path separators, missing translations)

### Other

- Remove completed roadmap files (`docs/roadmap/`)

## [0.2.0] - 2026-03-17

### Added

- `gfo browse` command (open repository, PR, or issue in browser — all 9 services)
- `--jq` global option (apply jq filter to JSON output)
- `gfo ssh-key` command (manage user SSH public keys — 6 services)
- `gfo org` command (list organizations, view details, members, repos — 7 services)
- `gfo notification` command (list and mark notifications as read — 5 services)
- `gfo branch-protect` command (manage branch protection rules — 5 services)
- `gfo secret` / `gfo variable` commands (manage CI/CD secrets and variables — 5 services)

## [0.1.1] - 2026-03-11

### Changed

- Add PyPI metadata (readme, keywords, classifiers, urls)
- Add CHANGELOG and link from README

## [0.1.0] - 2026-03-11

### Added

- Initial release
- Unified CLI supporting 9 Git hosting services: GitHub, GitLab, Bitbucket Cloud, Azure DevOps, Backlog, Gitea, Forgejo, Gogs, GitBucket
- Auto-detection of service from remote URL
- Commands: `init`, `auth`, `pr`, `issue`, `repo`, `release`, `label`, `milestone`, `comment`, `review`, `branch`, `tag`, `status`, `file`, `webhook`, `deploy-key`, `collaborator`, `ci`, `user`, `search`, `wiki`
- Output formats: `table`, `json`, `plain`
- Depends only on `requests` — no heavy dependencies
