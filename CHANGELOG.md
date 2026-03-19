# Changelog

All notable changes to this project will be documented in this file.

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
