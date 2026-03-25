# Changelog

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
