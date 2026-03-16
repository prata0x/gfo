# Integration Testing Guide

Instructions for running integration tests against each Git hosting service in gfo.

## Overview

| Category | Services | Method |
|---|---|---|
| Self-hosted | Gitea, Forgejo, Gogs, GitBucket | Docker Compose (automated setup) |
| SaaS | GitHub, GitLab, Bitbucket, Azure DevOps | Free plan (manual setup required) |
| Paid | Backlog | Conditionally skipped (account holders only) |

## Prerequisites

- Python 3.11 or later
- Installed via `pip install -e ".[dev]"`
- Self-hosted tests: Docker Desktop (Docker Compose v2)
- SaaS tests: Account and API token for each service

---

## Self-Hosted Tests (Docker)

Self-hosted tests can be run **fully automatically**. No prior user configuration is required.

### One-shot Execution

```bash
bash tests/integration/run_selfhosted.sh
```

This script automatically performs the following:
1. Starts 4 services (Gitea / Forgejo / Gogs / GitBucket) with Docker Compose
2. Waits for health checks to pass for each service
3. Runs `setup_services.py` to create users, generate tokens, and create test repositories
4. Runs pytest for integration tests
5. Cleans up Docker containers and volumes

### Manual Execution

```bash
# 1. Start services
docker compose -f tests/integration/docker-compose.yml up -d

# 2. Wait until each service is healthy
docker compose -f tests/integration/docker-compose.yml ps

# 3. Initial setup (create users, tokens, repositories)
python tests/integration/setup_services.py

# 4. Run tests
pytest tests/integration/ -m selfhosted -v --no-cov

# 5. Run specific service only
pytest tests/integration/test_gitea.py -v --no-cov

# 6. Cleanup
docker compose -f tests/integration/docker-compose.yml down -v
```

### Port Assignments

| Service | Web UI | SSH |
|---|---|---|
| Gitea | http://localhost:3000 | 2222 |
| Forgejo | http://localhost:3001 | 2223 |
| Gogs | http://localhost:3002 | 2224 |
| GitBucket | http://localhost:3003 | 2225 |

### Resources Created by Setup

`setup_services.py` automatically creates the following and writes them to `tests/integration/.env`:

- Admin user: `gfo-admin` / `gfo-test-pass123`
  - GitBucket only: `root` / `root` (default admin)
- Test repository: `gfo-integration-test`
- Test branch: `gfo-test-branch` (for PR tests, with files added)
- API tokens: generated per service

---

## SaaS Tests

SaaS tests **require obtaining an account and setting up tokens for each service**. Follow the steps below.

### Steps Common to All Services

#### Step 1: Create a Test Repository

Create a repository named `gfo-integration-test` on each service.
**Initialize with README** (empty repositories are not allowed — an initial commit is required).

#### Step 2: Create a Test Branch

Create a `gfo-test-branch` branch for PR testing and add a diff from the default branch.

```bash
# After cloning the repository
git checkout -b gfo-test-branch
echo "test" > test-branch-file.txt
git add test-branch-file.txt
git commit -m "test: add branch file for integration test"
git push origin gfo-test-branch
```

#### Step 3: Configure Environment Variables

```bash
cp tests/integration/.env.example tests/integration/.env
# Edit .env to set each token
```

#### Step 4: Run Tests

```bash
# All SaaS tests
bash tests/integration/run_saas.sh

# Specific service only
pytest tests/integration/test_github.py -v --no-cov
```

---

### GitHub

#### Create Repository

1. Create a repository at https://github.com/new
   - Repository name: `gfo-integration-test`
   - Check **Add a README file**
2. Create the `gfo-test-branch` branch using Step 2 above

#### Get API Token

1. GitHub.com > Settings > Developer settings > Personal access tokens > **Fine-grained tokens**
2. Click **Generate new token**
3. Repository access: **All repositories** (required for `repo create/delete` tests that need access to new repositories)
4. Repository permissions:
   - Contents: **Read and write**
   - Issues: **Read and write**
   - Pull requests: **Read and write**
   - Administration: **Read and write** (required for `repo delete` and `branch-protect`)
   - Commit statuses: **Read and write** (required for creating/listing commit statuses)
   - Webhooks: **Read and write** (required for Webhook CRUD tests)
   - Metadata: **Read** (required, granted automatically)
   - Secrets: **Read and write** (required for `secret` tests)
   - Variables: **Read and write** (required for `variable` tests)
5. Account permissions:
   - Git SSH keys: **Read and write** (required for `ssh-key` tests)
6. Organization permissions (for org repositories):
   - Members: **Read** (required for `org members` tests)
7. Generate token and copy

> **Note**: `notification` tests require a Classic Token with the `notifications` scope, as Fine-grained Tokens do not support notification APIs. For full integration testing including `notification`, use a Classic Token with scopes: `repo`, `notifications`, `admin:public_key`, `read:org`.

#### Environment Variables

See `github-spec.md §12` for details.

---

### GitLab

#### Create Repository

1. Create a project at https://gitlab.com/projects/new
   - Project name: `gfo-integration-test`
   - Check **Initialize repository with a README**
2. Create the `gfo-test-branch` branch using Step 2 above

#### Get API Token

1. GitLab.com > User Settings > Access Tokens
2. Click **Add new token**
3. Token name: `gfo-test`
4. Expiration date: any (recommended to delete after testing)
5. Scopes:
   - `api` (all API operations)
6. Create personal access token and copy

#### Environment Variables

See `gitlab-spec.md §12` for details.

---

### Bitbucket Cloud

Bitbucket does not support **release / label / milestone** via API, so those tests are skipped.

#### Create Repository

1. Create a repository at https://bitbucket.org/repo/create
   - Repository name: `gfo-integration-test`
   - **Include a README?** → Yes
2. Create the `gfo-test-branch` branch using Step 2 above

> **Enable Issue Tracker**: Repository settings > Features > Issue tracker (required for Issue tests).
>
> **Enable Pipelines**: Repository settings > Pipelines > Settings > Enable Pipelines (required for `gfo secret` / `gfo variable` tests).

#### Get Scoped API Token

Bitbucket Cloud uses **Scoped API Tokens** (App Passwords are fully deprecated in June 2026).

1. Open https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Label: `gfo-test`
4. Select the following **Scopes**:
   | Scope | Reason |
   |---------|------|
   | `read:repository:bitbucket` | Read repository info, list, `list_collaborators` |
   | `write:repository:bitbucket` | Add diff commits to branch between tests (see note) |
   | `admin:repository:bitbucket` | Required for `repo create` |
   | `delete:repository:bitbucket` | Required for `repo delete` |
   | `read:pullrequest:bitbucket` | List and get PRs |
   | `write:pullrequest:bitbucket` | Create, merge, close PRs |
   | `read:issue:bitbucket` | List and get issues |
   | `write:issue:bitbucket` | Create issues, change state |
   | `delete:issue:bitbucket` | Required for `issue delete` |
   | `read:webhook:bitbucket` | List webhooks |
   | `write:webhook:bitbucket` | Create and update webhooks |
   | `delete:webhook:bitbucket` | Delete webhooks |
   | `read:ssh-key:bitbucket` | List SSH keys and deploy keys |
   | `write:ssh-key:bitbucket` | Create and update SSH keys and deploy keys |
   | `delete:ssh-key:bitbucket` | Delete SSH keys and deploy keys |
   | `read:user:bitbucket` | Required for `get_current_user` |
   | `read:workspace:bitbucket` | Required for `org list/view` |
   | `read:pipeline:bitbucket` | Required for `secret/variable list` |
   | `write:pipeline:bitbucket` | Required for `secret/variable set` |
   | `admin:pipeline:bitbucket` | Required for `secret/variable` create/delete |

   > **Note**: `write:repository:bitbucket` is not required by gfo itself. It is needed to commit a marker file (via Bitbucket Src API) before test runs, since after a PR merge the `gfo-test-branch` and `main` will have no diff.
5. Create and copy the token

#### Environment Variables

See `bitbucket-spec.md §12` for details.

---

### Azure DevOps

Azure DevOps does not support **release / label / milestone** via API, so those tests are skipped. Issues are treated as Work Items.

#### Create Organization and Project

1. Create or use an existing organization at https://dev.azure.com
2. Create a `gfo-integration-test` project with New project
   - Version control: **Git**
   - Work item process: **Agile** (optional)
3. Repos > Initialize (with README)
4. Create the `gfo-test-branch` branch using Step 2 above

#### Get API Token (Personal Access Token)

1. Azure DevOps top-right user icon > **Personal access tokens**
2. Click **New Token**
3. Name: `gfo-test`
4. Organization: select the target organization
5. Scopes: select **Custom defined**
   - Code: **Read, write & manage** (required for `repo create/delete`; **Read & write** is insufficient)
   - Work Items: **Read, write & manage** (required for `issue delete`; **Read & write** cannot delete)
   - Project and Team: **Read** (required for `org list/view`)
   - Member Entitlement Management: **Read** (required for `/_apis/connectionData` endpoint used by `create_review` and `get_current_user`)
6. Create and copy the token

> **Note**: `create_review` and `get_current_user` use the `/_apis/connectionData` endpoint. You need to include **Member Entitlement Management: Read** under Custom defined scopes, or use a **Full access** PAT.

#### Environment Variables

See `azure-devops-spec.md §12` for details.

---

### Backlog (Paid Service)

Backlog is **paid-only**, so tests are skipped by default. Configure only if you have an account.

Unsupported operations: pr merge / release / label / milestone

#### Create Repository

1. Create a project in your Backlog space
2. Project settings > Git > Add repository > `gfo-integration-test`
3. Create the `gfo-test-branch` branch using Step 2 above

#### Get API Key

1. Personal settings > API > **Issue new API key**
2. Memo: `gfo-test`
3. Issue and copy

#### Environment Variables

See `backlog-spec.md §12` for details.

---

## Environment Variables Summary

See `.env.example`. Copy to `.env` and set the values.

```bash
cp tests/integration/.env.example tests/integration/.env
```

`.env` is included in `.gitignore` and will not be committed to the repository.

---

## Test Coverage Matrix

| Operation | GitHub | GitLab | Bitbucket | Azure DevOps | Gitea | Forgejo | Gogs | GitBucket | Backlog |
|---|---|---|---|---|---|---|---|---|---|
| repo view/list | o | o | o | o | o | o | o | o | o |
| label | o | o | skip | skip | o | o | skip | o | skip |
| milestone | o | o | skip | skip | o | o | skip | o | skip |
| issue | o | o | o | o | o | o | o | o | o |
| pr create/list/view | o | o | o | o | o | o | skip | o | o |
| pr merge | o | o | o | o | o | o | skip | o | skip |
| release | o | o | skip | skip | o | o | o | o | skip |
| browse | o | o | o | o | o | o | o | o | o |
| branch-protect | o | o | o | skip | o | o | skip | skip | skip |
| notification | o | o | skip | skip | o | o | skip | skip | o |
| org | o | o | o | o | o | o | o | skip | skip |
| ssh-key | o | o | o | skip | o | o | o | skip | skip |
| secret | o | o | o | skip | o | o | skip | skip | skip |
| variable | o | o | o | skip | o | o | skip | skip | skip |

---

## Troubleshooting

### Docker Services Fail to Start

```bash
# Check logs
docker compose -f tests/integration/docker-compose.yml logs gitea

# Restart individual service
docker compose -f tests/integration/docker-compose.yml restart gitea
```

### Port Already in Use

Change the port mappings in `docker-compose.yml` and update the base URLs in `setup_services.py` accordingly.

### Tests Time Out

Increase the `timeout` argument of the `wait_for_health` function in `setup_services.py` (default: 120 seconds).

### 401 Error in SaaS Tests

- Re-check token scopes and permissions
- For Bitbucket, confirm the format is `email:api-token`
- For Azure DevOps, confirm the token is tied to the correct organization

### PR Tests Fail in Azure DevOps

Confirm that `gfo-test-branch` exists in the `gfo-integration-test` **repository** (not just the project). Azure DevOps projects and repositories are separate concepts.

### Resources Remain After Tests

Each test run leaves issues, PRs, releases, etc. on the service.
If you get "already exists" errors on re-run, manually delete them from the service Web UI, or delete and recreate the test repository.
