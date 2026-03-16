# Changelog

All notable changes to this project will be documented in this file.

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
