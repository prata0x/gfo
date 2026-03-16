# Authentication Guide

## How to Configure Tokens

gfo resolves tokens in the following priority order:

1. `credentials.toml` (saved via `gfo auth login`)
2. Service-specific environment variables
3. `GFO_TOKEN` environment variable (fallback for all services)

### Method 1: gfo auth login (Recommended)

Run the following inside your repository to save the token to `credentials.toml`:

```bash
gfo auth login
```

To specify the host explicitly:

```bash
gfo auth login --host github.com
```

To pass the token directly on the command line (for scripts / CI):

```bash
gfo auth login --host github.com --token ghp_xxxx
```

Check configured tokens:

```bash
gfo auth status
```

### Method 2: Manually edit credentials.toml

**File paths:**
- Windows: `%APPDATA%\gfo\credentials.toml`
- Linux / macOS: `~/.config/gfo/credentials.toml`

```toml
[tokens]
"github.com" = "ghp_xxxxxxxxxxxxxxxxxxxx"
"gitlab.com" = "glpat-xxxxxxxxxxxxxxxxxxxx"
"bitbucket.org" = "user@example.com:app-password"
"dev.azure.com" = "azure-pat-string"
"gitea.example.com" = "xxxxxxxxxxxxxxxxxxxxxxxx"
"myspace.backlog.com" = "backlog-api-key"
```

### Method 3: Environment Variables

| Service | Environment Variable |
|---|---|
| GitHub | `GITHUB_TOKEN` |
| GitLab | `GITLAB_TOKEN` |
| Bitbucket Cloud | `BITBUCKET_TOKEN` |
| Azure DevOps | `AZURE_DEVOPS_PAT` |
| Gitea / Forgejo / Gogs | `GITEA_TOKEN` |
| GitBucket | `GITBUCKET_TOKEN` |
| Backlog | `BACKLOG_API_KEY` |
| All services (fallback) | `GFO_TOKEN` |

---

## Token Creation Instructions by Service

### GitHub

**Fine-grained Personal Access Token (Recommended)**

1. Log in to GitHub, click your avatar in the top-right → **Settings**
2. In the left menu at the bottom, go to **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
3. Click **Generate new token**
4. Set Token name and Expiration
5. Under **Repository access**, select your target repositories
6. Grant required permissions under **Repository permissions**:
   - Contents: `Read and write` (required for file operations)
   - Issues: `Read and write`
   - Pull requests: `Read and write`
   - Metadata: `Read-only` (granted automatically)
   - Commit statuses: `Read and write` (if using `gfo status`)
   - Webhooks: `Read and write` (if using `gfo webhook`)
   - Administration: `Read and write` (if using `gfo branch-protect`)
   - Secrets: `Read and write` (if using `gfo secret`)
   - Variables: `Read and write` (if using `gfo variable`)
7. Grant required permissions under **Account permissions**:
   - Git SSH keys: `Read and write` (if using `gfo ssh-key`)
8. Grant required permissions under **Organization permissions** (for org repositories):
   - Members: `Read-only` (if using `gfo org members`)
9. Click **Generate token** and copy it

> **Note**: `gfo notification` is not supported with Fine-grained Tokens. Use a Classic Token with the `notifications` scope.

```bash
gfo auth login --host github.com
# Token: ghp_xxxxxxxxxxxxxxxxxxxx
```

**Classic Personal Access Token**

- Scopes: `repo` (full access), `notifications` (for `gfo notification`), `admin:public_key` (for `gfo ssh-key`), `read:org` (for `gfo org`)
- Generate from Settings → Developer settings → Personal access tokens → Tokens (classic)

---

### GitLab

1. Log in to GitLab, click your avatar in the top-right → **Edit profile**
2. In the left menu, click **Access Tokens** → **Add new token**
3. Set Token name and Expiration date
4. Select scopes:
   - Read-only: `read_api`
   - For write operations (creating PRs, issues, etc.): `api`
5. Click **Create personal access token**

```bash
gfo auth login --host gitlab.com
# Token: glpat-xxxxxxxxxxxxxxxxxxxx
```

For self-hosted GitLab:

```bash
gfo auth login --host gitlab.example.com
```

---

### Bitbucket Cloud

> **Note**: App Passwords are scheduled for deprecation in June 2026. Please use Scoped API Tokens.

**Creating a Scoped API Token**

1. Log in to Bitbucket, click your avatar in the top-right → **Settings**
2. Under **Personal Bitbucket settings**, go to **Scoped API tokens** → **Create token**
3. Set Token label
4. Grant required permissions:
   - **Repositories**: `Read` / `Write`
   - **Repositories**: `Admin` (if using `gfo branch-protect`)
   - **Pull requests**: `Read` / `Write` (note: `write` does not include `read`, so both are required)
   - **Issues**: `Read` / `Write` (if using Issue Tracker)
   - **Pipelines**: `Read` / `Write` / `Admin` (if using `gfo secret` / `gfo variable`)
   - **SSH keys**: `Read` / `Write` / `Delete` (if using `gfo ssh-key`)
   - **Workspace membership**: `Read` (if using `gfo org`)
5. Click **Create** and copy the token

**Token format**: Set as `email:token` separated by a colon.

```bash
export BITBUCKET_TOKEN="user@example.com:ATATT-xxxxxxxxxxxxxxxxxxxx"
```

Or:

```bash
gfo auth login --host bitbucket.org
# Token: user@example.com:ATATT-xxxxxxxxxxxxxxxxxxxx
```

---

### Azure DevOps

1. Log in to Azure DevOps, click the user icon in the top-right → **Personal access tokens**
2. Click **New Token**
3. Set Name, Organization, and Expiration
4. Grant required permissions under **Scopes**:
   - **Code**: `Read & write`
   - **Work Items**: `Read & write` (required for Issue/task operations)
5. Click **Create** and copy the token

```bash
export AZURE_DEVOPS_PAT="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Or:

```bash
gfo auth login --host dev.azure.com
```

> During `gfo init`, you will need to provide the **Organization** and **Project**.

---

### Backlog

1. Log in to Backlog, click your avatar in the top-right → **Personal Settings**
2. Go to **API** in the left menu
3. Enter a memo (optional) and click **Register**
4. Copy the generated API key

> The API key has no scope control — full account permissions are granted.

```bash
export BACKLOG_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Or:

```bash
gfo auth login --host yourspace.backlog.com
```

> During `gfo init`, you will need to provide the **project key** (e.g., `MYPROJECT`).

---

### Gitea

1. Log in to Gitea, click your avatar in the top-right → **Settings**
2. Go to **Applications** → **Manage Access Tokens** in the left menu
3. Enter a **Token Name** and select the required scopes
4. Click **Generate Token**

```bash
gfo auth login --host gitea.example.com
```

---

### Forgejo

Same steps as Gitea.

1. Log in to Forgejo, click your avatar in the top-right → **Settings**
2. Go to **Applications** → **Manage Access Tokens**
3. Enter a Token Name, select scopes, and click **Generate Token**

```bash
gfo auth login --host forgejo.example.com
```

> [Codeberg](https://codeberg.org) is Forgejo-based, so you can issue tokens using the same steps.

---

### Gogs

1. Log in to Gogs, click your avatar in the top-right → **Your Settings**
2. Go to **Applications** → **Generate New Token** in the left menu
3. Enter a Token Name and click **Generate Token**

```bash
gfo auth login --host gogs.example.com
```

> Gogs does not support PR, label, milestone, or release APIs.

---

### GitBucket

1. Log in to GitBucket, click your avatar in the top-right → **Account Settings**
2. Go to **Personal access token** → **Generate new token**
3. Enter a Note and click **Generate**

> Tokens can only be issued from the Web UI (API-based issuance is not supported).

```bash
gfo auth login --host gitbucket.example.com:8080
```

Specify the host name including the port number.
