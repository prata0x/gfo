# Changelog

All notable changes to this project will be documented in this file.

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
