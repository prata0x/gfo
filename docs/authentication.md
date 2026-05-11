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

### Multiple Accounts per Host

You can store multiple tokens per host by specifying an account name:

```bash
gfo auth login --host github.com --account personal
gfo auth login --host github.com --account work
```

Switch the active account:

```bash
gfo auth switch work --host github.com
```

Remove a saved token:

```bash
gfo auth logout --host github.com
gfo auth logout --host github.com --account work
```

Use a specific account for a single command:

```bash
gfo --account work pr list
```

Or set a per-repository default account:

```bash
gfo init --account work
```

Token resolution order for accounts:
1. `--account` CLI option (ContextVar)
2. `git config gfo.account` (per-repository)
3. `config.toml` host configuration (`account` key)
4. `_default` key in `credentials.toml`
5. Fallback: `"default"`

### Method 2: Manually edit credentials.toml

**File paths:**
- Windows: `%APPDATA%\gfo\credentials.toml`
- Linux / macOS: `~/.config/gfo/credentials.toml`

```toml
[tokens."github.com"]
_default = "default"
default = "ghp_xxxxxxxxxxxxxxxxxxxx"

[tokens."gitlab.com"]
_default = "default"
default = "glpat-xxxxxxxxxxxxxxxxxxxx"

[tokens."bitbucket.org"]
_default = "default"
default = "user@example.com:app-password"

[tokens."dev.azure.com"]
_default = "default"
default = "azure-pat-string"

[tokens."gitea.example.com"]
_default = "default"
default = "xxxxxxxxxxxxxxxxxxxxxxxx"

[tokens."myspace.backlog.com"]
_default = "default"
default = "backlog-api-key"
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

## Security-related Environment Variables

These environment variables control TLS verification, transport security, and download safeguards. Defaults are chosen to prevent token leakage and SSRF; loosen them only when you understand the consequences.

| Variable | Values | Default | Description |
|---|---|---|---|
| `GFO_INSECURE` | `1` / `true` / `yes` | unset (verify TLS) | Disables TLS certificate verification for **self-hosted** hosts. Cloud-hosted services (github.com, gitlab.com, bitbucket.org, dev.azure.com, *.backlog.com / *.backlog.jp, *.visualstudio.com) always enforce TLS verification regardless of this flag. A warning is printed to stderr on startup when set. |
| `GFO_ALLOW_INSECURE_HTTP` | `1` / `true` / `yes` | unset (https only) | Allows `api_url` to use `http://` for arbitrary hosts. `localhost`, `127.0.0.1`, and `::1` are always permitted regardless of this flag. Tokens sent over plain HTTP are exposed to LAN/Wi-Fi sniffing — use only when you accept that risk. |
| `GFO_ALLOW_PRIVATE_HOSTS` | `1` / `true` / `yes` | unset (rejected) | Allows API probing of unknown hosts that resolve to private / loopback / link-local / reserved IP ranges. Required when running an internal Gitea/Forgejo/GitLab/GitBucket on a private network and relying on auto-detection. Without this flag, gfo refuses to probe such addresses to mitigate SSRF. |
| `GFO_MAX_DOWNLOAD_BYTES` | integer (bytes) | `5368709120` (5 GiB) | Maximum cumulative bytes accepted by streaming downloads (`gfo release asset download`, `gfo ci download`, log downloads). Exceeding the limit aborts the download and removes the partial file. Set to `0` for unlimited (not recommended). Invalid values fall back to the default. |

**Example — self-hosted Gitea with a self-signed cert behind a private IP:**

```bash
export GFO_INSECURE=1
export GFO_ALLOW_PRIVATE_HOSTS=1
gfo --repo gitea.internal/team/repo pr list
```

**Example — bumping the download size limit to 20 GiB:**

```bash
export GFO_MAX_DOWNLOAD_BYTES=21474836480
gfo release asset download v1.0.0 large-asset.bin
```

---

## Token Creation Instructions by Service

### GitHub

**Fine-grained Personal Access Token (Recommended)**

1. Log in to GitHub, click your avatar in the top-right → **Settings**
2. In the left menu at the bottom, go to **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
3. Click **Generate new token**
4. Set Token name and Expiration
5. Under **Repository access**, select your target repositories
6. Grant required permissions:

   **Repository permissions:**

   | Permission | Access Level | Purpose |
   |------------|-------------|---------|
   | Contents | `Read and write` | `gfo repo` (file operations), `gfo release` (assets) |
   | Issues | `Read and write` | If using `gfo issue` |
   | Pull requests | `Read and write` | If using `gfo pr` |
   | Metadata | `Read-only` | Granted automatically |
   | Commit statuses | `Read and write` | If using `gfo status` |
   | Webhooks | `Read and write` | If using `gfo webhook` |
   | Administration | `Read and write` | If using `gfo branch-protect` or `gfo repo delete` |
   | Secrets | `Read and write` | If using `gfo secret` |
   | Variables | `Read and write` | If using `gfo variable` |

   **Account permissions:**

   | Permission | Access Level | Purpose |
   |------------|-------------|---------|
   | Git SSH keys | `Read and write` | If using `gfo ssh-key` |

   **Organization permissions (for org repositories):**

   | Permission | Access Level | Purpose |
   |------------|-------------|---------|
   | Members | `Read-only` | If using `gfo org` |

7. Click **Generate token** and copy it

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

   | Scope | Purpose |
   |-------|---------|
   | `api` | All gfo commands (read and write) |
   | `read_api` | Read-only (`gfo repo`, `gfo pr`, `gfo issue` list/details only) |
   | `read_repository` | `gfo repo` (clone, read files) |
   | `write_repository` | `gfo repo` (create/update files, push) |
   | `read_user` | Get authenticated user info |

   > **Recommended**: Select the `api` scope if you need write operations (creating PRs, issues, etc.). `api` includes all other scopes.

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
4. Select required scopes:
   | Scope | Purpose |
   |---------|------|
   | `read:repository:bitbucket` | `gfo repo` (list, details, read files) |
   | `write:repository:bitbucket` | `gfo repo` (create/update files) |
   | `admin:repository:bitbucket` | If using `gfo branch-protect` |
   | `read:pullrequest:bitbucket` | `gfo pr` (list, details) |
   | `write:pullrequest:bitbucket` | `gfo pr` (create, merge, close) |
   | `read:issue:bitbucket` | `gfo issue` (list, details; if using Issue Tracker) |
   | `write:issue:bitbucket` | `gfo issue` (create, change state; if using Issue Tracker) |
   | `read:pipeline:bitbucket` | List `gfo secret` / `gfo variable` |
   | `write:pipeline:bitbucket` | Update `gfo secret` / `gfo variable` |
   | `admin:pipeline:bitbucket` | Create/delete `gfo secret` / `gfo variable` |
   | `read:ssh-key:bitbucket` | List SSH keys (if using `gfo ssh-key`) |
   | `write:ssh-key:bitbucket` | Create/update SSH keys (if using `gfo ssh-key`) |
   | `delete:ssh-key:bitbucket` | Delete SSH keys (if using `gfo ssh-key`) |
   | `read:workspace:bitbucket` | If using `gfo org` |
   | `read:user:bitbucket` | All commands (authentication check) |

   > **Note**: `write` does not include `read`. Select both scopes when both read and write access are needed.
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

   | Scope | Access Level | Purpose |
   |-------|-------------|---------|
   | Code | `Read & write` | `gfo repo`, `gfo pr`, `gfo release` |
   | Work Items | `Read & write` | If using `gfo issue` |
   | Project and Team | `Read` | If using `gfo org` |

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
3. Enter a **Token Name** and set the access level for each scope:

   | Scope | Access Level | Purpose |
   |-------|-------------|---------|
   | `repository` | Read | `gfo repo` (list, details, read files) |
   | `repository` | Read and Write | `gfo repo` (create/update files), `gfo pr`, `gfo release`, `gfo branch-protect` |
   | `issue` | Read | `gfo issue` (list, details), `gfo label`, `gfo milestone` |
   | `issue` | Read and Write | `gfo issue` (create, update, delete), `gfo label`, `gfo milestone` |
   | `organization` | Read | `gfo org` (list, details, members) |
   | `user` | Read | Get authenticated user info |
   | `user` | Read and Write | `gfo ssh-key` (SSH key management) |
   | `notification` | Read | `gfo notification` (list) |
   | `notification` | Read and Write | `gfo notification` (mark as read) |

4. Click **Generate Token**

```bash
gfo auth login --host gitea.example.com
```

---

### Forgejo

Same steps and scope system as Gitea.

1. Log in to Forgejo, click your avatar in the top-right → **Settings**
2. Go to **Applications** → **Manage Access Tokens**
3. Enter a Token Name and set the access level for each scope under **Select Permissions**:

   | Scope | Access Level | Purpose |
   |-------|-------------|---------|
   | `repository` | Read | `gfo repo` (list, details, read files) |
   | `repository` | Read and Write | `gfo repo` (create/update files), `gfo pr`, `gfo release`, `gfo branch-protect` |
   | `issue` | Read | `gfo issue` (list, details), `gfo label`, `gfo milestone` |
   | `issue` | Read and Write | `gfo issue` (create, update, delete), `gfo label`, `gfo milestone` |
   | `organization` | Read | `gfo org` (list, details, members) |
   | `user` | Read | Get authenticated user info |
   | `user` | Read and Write | `gfo ssh-key` (SSH key management) |
   | `notification` | Read | `gfo notification` (list) |
   | `notification` | Read and Write | `gfo notification` (mark as read) |

4. Click **Generate Token**

```bash
gfo auth login --host forgejo.example.com
```

> [Codeberg](https://codeberg.org) is Forgejo-based, so you can issue tokens using the same steps.

---

### Gogs

1. Log in to Gogs, click your avatar in the top-right → **Your Settings**
2. Go to **Applications** → **Generate New Token** in the left menu
3. Enter a Token Name and click **Generate Token**

> Tokens have no scope control — full account permissions are granted.
> Gogs does not support PR, label, milestone, or release APIs.

```bash
gfo auth login --host gogs.example.com
```

---

### GitBucket

1. Log in to GitBucket, click your avatar in the top-right → **Account Settings**
2. Go to **Personal access token** → **Generate new token**
3. Enter a Note and click **Generate**

> Tokens have no scope control — full account permissions are granted.
> Tokens can only be issued from the Web UI (API-based issuance is not supported).

```bash
gfo auth login --host gitbucket.example.com:8080
```

Specify the host name including the port number.

---

## Authentication for Cross-Service Commands

Commands that operate on multiple services simultaneously, such as `gfo issue migrate` and `gfo batch pr create`, specify repositories using the `service:owner/repo` format.

Tokens for each service are resolved using the same priority order as regular commands (credentials.toml → environment variables → GFO_TOKEN).

```bash
# Example: Migrating issues from GitHub to Gitea
# Both GitHub and Gitea tokens are required
gfo auth login --host github.com --token ghp_xxxx
gfo auth login --host gitea.example.com --token your-gitea-token

gfo issue migrate --from github:owner/repo --to gitea:gitea.example.com:owner/repo --number 42
```
