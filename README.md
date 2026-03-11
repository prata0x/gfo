[日本語](README.ja.md)

# gfo – Git Forge Operator

A CLI tool to operate multiple Git hosting services with a **unified command interface**.

- Operate 9 services with the same commands (GitHub, GitLab, Bitbucket, Azure DevOps, Backlog, Gitea, Forgejo, Gogs, GitBucket)
- Auto-detects the service from remote URL
- Depends only on `requests` — lightweight
- Supports `table` / `json` / `plain` output formats

## Supported Services

| Service | Identifier | Auth Environment Variable |
|---|---|---|
| GitHub | `github` | `GITHUB_TOKEN` |
| GitLab | `gitlab` | `GITLAB_TOKEN` |
| Bitbucket Cloud | `bitbucket` | `BITBUCKET_TOKEN` (`email:api-token` format) |
| Azure DevOps | `azure-devops` | `AZURE_DEVOPS_PAT` |
| Gitea | `gitea` | `GITEA_TOKEN` |
| Forgejo | `forgejo` | `GITEA_TOKEN` |
| Gogs | `gogs` | `GITEA_TOKEN` |
| GitBucket | `gitbucket` | `GITBUCKET_TOKEN` |
| Backlog | `backlog` | `BACKLOG_API_KEY` |

## Installation

```bash
pip install gfo
```

**Requirements**: Python 3.11 or later

## Quick Start

```bash
# 1. Initialize in your repository (auto-detects service from remote URL)
gfo init

# 2. Set up authentication token
gfo auth login

# 3. List pull requests
gfo pr list

# 4. Create an issue
gfo issue create --title "Bug report"

# 5. Clone a repository
gfo repo clone alice/my-project
```

## Authentication

Token resolution order:

1. `credentials.toml` (saved via `gfo auth login`)
2. Service-specific environment variables (see table above)
3. `GFO_TOKEN` generic environment variable (fallback for all services)

**File paths:**
- Windows: `%APPDATA%\gfo\credentials.toml`
- Linux / macOS: `~/.config/gfo/credentials.toml`

```bash
# Set token interactively
gfo auth login --host github.com

# Set via environment variable
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Check authentication status
gfo auth status
```

See [docs/authentication.md](docs/authentication.md) for token creation instructions for each service (required scopes/permissions).

## Commands

| Command | Subcommands | Description |
|---|---|---|
| `gfo init` | — | Initialize project configuration |
| `gfo auth` | `login`, `status` | Save token / check auth status |
| `gfo pr` | `list`, `create`, `view`, `merge`, `close`, `checkout`, `update` | Pull request operations |
| `gfo issue` | `list`, `create`, `view`, `close`, `delete`, `update` | Issue operations |
| `gfo repo` | `list`, `create`, `clone`, `view`, `delete`, `fork` | Repository operations |
| `gfo release` | `list`, `create`, `delete` | Release management |
| `gfo label` | `list`, `create`, `delete` | Label management |
| `gfo milestone` | `list`, `create`, `delete` | Milestone management |
| `gfo comment` | `list`, `create`, `update`, `delete` | PR / Issue comment operations |
| `gfo review` | `list`, `create` | PR review operations |
| `gfo branch` | `list`, `create`, `delete` | Branch operations |
| `gfo tag` | `list`, `create`, `delete` | Tag operations |
| `gfo status` | `list`, `create` | Commit status operations |
| `gfo file` | `get`, `put`, `delete` | Repository file operations |
| `gfo webhook` | `list`, `create`, `delete` | Webhook management |
| `gfo deploy-key` | `list`, `create`, `delete` | Deploy key management |
| `gfo collaborator` | `list`, `add`, `remove` | Collaborator management |
| `gfo ci` | `list`, `view`, `cancel` | CI/CD job operations |
| `gfo user` | `whoami` | Display authenticated user info |
| `gfo search` | `repos`, `issues` | Search repositories / issues |
| `gfo wiki` | `list`, `view`, `create`, `update`, `delete` | Wiki operations |

See [docs/commands.md](docs/commands.md) for detailed options and examples for each command.

### Global Options

| Option | Description | Default |
|---|---|---|
| `--format {table,json,plain}` | Output format | `table` |
| `--version` | Show version | — |

## Configuration

gfo resolves configuration in 3 layers (in order of priority):

1. `git config --local` (per-repository, saved by `gfo init`)
2. `~/.config/gfo/config.toml` (global)
3. Auto-detection from remote URL

**config.toml example:**

```toml
[defaults]
output = "table"          # Default output format (table / json / plain)
host = "github.com"       # Default host (optional)

[hosts."gitea.example.com"]
type = "gitea"
api_url = "https://gitea.example.com/api/v1"

[hosts."gitlab.example.com"]
type = "gitlab"
api_url = "https://gitlab.example.com/api/v4"
```

**File paths:**
- Windows: `%APPDATA%\gfo\config.toml`
- Linux / macOS: `~/.config/gfo/config.toml`

## Feature Support Matrix

| Feature | GitHub | GitLab | Bitbucket | Azure DevOps | Backlog | Gitea | Forgejo | Gogs | GitBucket |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| PR / MR | ○ | ○ | ○ | ○ | ○ | ○ | ○ | × | ○ |
| PR Merge | ○ | ○ | ○ | ○ | × | ○ | ○ | × | ○ |
| Issue | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Release | ○ | ○ | × | × | × | ○ | ○ | × | ○ |
| Label | ○ | ○ | × | × | × | ○ | ○ | × | ○ |
| Milestone | ○ | ○ | × | × | × | ○ | ○ | × | ○ |
| Review | ○ | ○ | × | × | × | × | × | × | × |
| Wiki | × | ○ | × | × | × | ○ | ○ | × | × |
| CI/CD | ○ | ○ | × | × | × | ○ | ○ | × | × |
| Search | ○ | ○ | × | × | × | × | × | × | × |

> ×: Not supported (returns `NotSupportedError`)

## Development

```bash
# Run tests (with coverage)
pytest

# Run specific tests
pytest tests/test_commands/test_pr.py
```

### Integration Tests

Integration tests against real services are also available.

- **Self-hosted** (Gitea / Forgejo / Gogs / GitBucket): Can run automatically with Docker
- **SaaS** (GitHub / GitLab / Bitbucket / Azure DevOps): Requires accounts and API tokens for each service

See [docs/integration-testing.md](docs/integration-testing.md) for detailed setup instructions.

```bash
# Self-hosted tests (auto Docker startup and cleanup)
bash tests/integration/run_selfhosted.sh

# SaaS tests (set tokens in .env first)
bash tests/integration/run_saas.sh
```

## License

0BSD
