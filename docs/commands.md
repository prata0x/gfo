# Command Reference

## Global Options

Available for all commands.

| Option | Description | Default |
|---|---|---|
| `--format {table,json,plain}` | Output format | `table` |
| `--jq EXPRESSION` | Apply jq filter to JSON output (implicitly enables `--format json`) | — |
| `--version` | Show version and exit | — |

---

## gfo init

Initialize gfo configuration for a repository. Auto-detects the service from the remote URL and saves to `git config --local`.

> **Supported services**: All services

```
gfo init [--non-interactive] [--type TYPE] [--host HOST] [--api-url URL] [--project-key KEY]
```

| Option | Required | Description |
|---|---|---|
| `--non-interactive` | — | Skip interactive prompts (for CI) |
| `--type TYPE` | Required with `--non-interactive` | Service identifier (`github`, `gitlab`, `bitbucket`, `azure-devops`, `gitea`, `forgejo`, `gogs`, `gitbucket`, `backlog`) |
| `--host HOST` | Required with `--non-interactive` | Hostname (e.g., `github.com`, `gitea.example.com`) |
| `--api-url URL` | — | API base URL (auto-constructed if omitted) |
| `--project-key KEY` | — | Project key (Azure DevOps / Backlog) |

**Examples:**

```bash
# Interactive mode (auto-detects from remote URL)
gfo init

# Non-interactive mode (for CI)
gfo init --non-interactive --type github --host github.com

# Self-hosted GitLab
gfo init --non-interactive --type gitlab --host gitlab.example.com

# Azure DevOps (organization and project required)
gfo init --non-interactive --type azure-devops --host dev.azure.com --project-key MyProject

# Backlog
gfo init --non-interactive --type backlog --host myspace.backlog.com --project-key MYPROJECT
```

---

## gfo auth

Manage authentication tokens.

> **Supported services**: All services

### gfo auth login

Enter a token interactively and save it to `credentials.toml`.

```
gfo auth login [--host HOST] [--token TOKEN]
```

| Option | Description |
|---|---|
| `--host HOST` | Hostname (auto-resolved from `gfo init` config if omitted) |
| `--token TOKEN` | Specify token directly (interactive input if omitted) |

**Examples:**

```bash
gfo auth login
gfo auth login --host github.com
gfo auth login --host gitea.example.com --token mytoken123
```

### gfo auth status

Show a list of configured tokens (token values are hidden).

```
gfo auth status
```

---

## gfo pr

Operate pull requests (Merge Requests).

> **Supported services**: GitHub, GitLab, Bitbucket, Azure DevOps, Backlog, Gitea, Forgejo, GitBucket (Gogs not supported)

### gfo pr list

```
gfo pr list [--state {open,closed,merged,all}] [--limit N]
```

| Option | Default | Description |
|---|---|---|
| `--state` | `open` | PR state to display |
| `--limit` | `30` | Maximum number of results |

```bash
gfo pr list
gfo pr list --state all --limit 50
```

### gfo pr create

```
gfo pr create [--title TITLE] [--body BODY] [--base BRANCH] [--head BRANCH] [--draft]
```

| Option | Description |
|---|---|
| `--title` | PR title (interactive input if omitted) |
| `--body` | PR body |
| `--base` | Target branch (default branch if omitted) |
| `--head` | Source branch (current branch if omitted) |
| `--draft` | Create as draft PR |

```bash
gfo pr create --title "Fix login bug" --base main --head feature/fix-login
gfo pr create --title "WIP: new feature" --draft
```

### gfo pr view

```
gfo pr view NUMBER
```

```bash
gfo pr view 42
```

### gfo pr merge

> Backlog does not support PR merge

```
gfo pr merge NUMBER [--method {merge,squash,rebase}]
```

| Option | Default | Description |
|---|---|---|
| `--method` | `merge` | Merge method |

```bash
gfo pr merge 42
gfo pr merge 42 --method squash
```

### gfo pr close

```
gfo pr close NUMBER
```

```bash
gfo pr close 42
```

### gfo pr checkout

```
gfo pr checkout NUMBER
```

Checks out the PR branch locally.

```bash
gfo pr checkout 42
```

### gfo pr update

```
gfo pr update NUMBER [--title TITLE] [--body BODY] [--base BRANCH]
```

```bash
gfo pr update 42 --title "Updated title"
gfo pr update 42 --base develop
```

---

## gfo issue

Operate issues.

> **Supported services**: All services

### gfo issue list

```
gfo issue list [--state {open,closed,all}] [--assignee USER] [--label LABEL] [--limit N]
```

| Option | Default | Description |
|---|---|---|
| `--state` | `open` | Issue state to display |
| `--assignee` | — | Filter by assignee |
| `--label` | — | Filter by label |
| `--limit` | `30` | Maximum number of results |

```bash
gfo issue list
gfo issue list --state all --assignee alice --limit 100
```

### gfo issue create

```
gfo issue create --title TITLE [--body BODY] [--assignee USER] [--label LABEL] [--type TYPE] [--priority N]
```

| Option | Required | Description |
|---|---|---|
| `--title` | **Required** | Issue title |
| `--body` | — | Issue body |
| `--assignee` | — | Assignee |
| `--label` | — | Label |
| `--type` | — | Issue type (Azure DevOps: `Task`, `Bug`, etc.) |
| `--priority` | — | Priority (for services that use numeric priority, e.g., Backlog) |

```bash
gfo issue create --title "Bug: login fails"
gfo issue create --title "Feature request" --body "Details..." --label enhancement
```

### gfo issue view

```
gfo issue view NUMBER
```

```bash
gfo issue view 10
```

### gfo issue close

> GitBucket not supported

```
gfo issue close NUMBER
```

```bash
gfo issue close 10
```

### gfo issue delete

> GitHub / Gogs not supported

```
gfo issue delete NUMBER
```

```bash
gfo issue delete 10
```

### gfo issue update

> GitBucket not supported

```
gfo issue update NUMBER [--title TITLE] [--body BODY] [--assignee USER] [--label LABEL]
```

```bash
gfo issue update 10 --title "New title" --assignee bob
```

---

## gfo repo

Operate repositories.

> **Supported services**: All services

### gfo repo list

```
gfo repo list [--owner OWNER] [--limit N]
```

```bash
gfo repo list
gfo repo list --owner myorg --limit 50
```

### gfo repo create

```
gfo repo create NAME [--private] [--description DESC] [--host HOST]
```

```bash
gfo repo create my-new-repo --private --description "My project"
gfo repo create my-new-repo --host gitea.example.com
```

> **Note**: Azure DevOps and Backlog require `gfo init` configuration beforehand.
> - Azure DevOps: configure `organization` and `project`
> - Backlog: configure `project_key`

### gfo repo clone

```
gfo repo clone REPO [--host HOST] [--project PROJECT]
```

`REPO` must be in `owner/name` format.

`--project` is used to specify the project name for Azure DevOps. Can be omitted if already configured via `gfo init`.

```bash
gfo repo clone alice/my-project
gfo repo clone alice/my-project --host gitea.example.com
gfo repo clone my-repo --host dev.azure.com --project MyProject
```

### gfo repo view

```
gfo repo view [REPO]
```

Omitting `REPO` shows the current repository.

```bash
gfo repo view
gfo repo view alice/my-project
```

### gfo repo delete

```
gfo repo delete [--yes]
```

Deletes the current repository. Without `--yes`, a confirmation prompt is shown.

```bash
gfo repo delete --yes
```

### gfo repo fork

```
gfo repo fork [--org ORG]
```

```bash
gfo repo fork
gfo repo fork --org myorg
```

---

## gfo release

Manage releases.

> **Supported services**: GitHub, GitLab, Gitea, Forgejo, GitBucket

### gfo release list

```
gfo release list [--limit N]
```

```bash
gfo release list
```

### gfo release create

```
gfo release create TAG [--title TITLE] [--notes NOTES] [--draft] [--prerelease]
```

```bash
gfo release create v1.0.0 --title "Version 1.0.0" --notes "Release notes here"
gfo release create v1.1.0-rc1 --prerelease
gfo release create v2.0.0 --draft
```

### gfo release delete

```
gfo release delete TAG
```

```bash
gfo release delete v0.9.0
```

---

## gfo label

Manage labels.

> **Supported services**: GitHub, GitLab, Gitea, Forgejo, GitBucket

### gfo label list

```
gfo label list
```

### gfo label create

```
gfo label create NAME [--color COLOR] [--description DESC]
```

`--color` is specified as a 6-digit hex value in `RRGGBB` format (without `#`).

```bash
gfo label create bug --color ff0000 --description "Something is broken"
gfo label create enhancement --color 0075ca
```

### gfo label delete

```
gfo label delete NAME
```

```bash
gfo label delete old-label
```

---

## gfo milestone

Manage milestones.

> **Supported services**: GitHub, GitLab, Gitea, Forgejo, GitBucket

### gfo milestone list

```
gfo milestone list
```

### gfo milestone create

```
gfo milestone create TITLE [--description DESC] [--due DATE]
```

`--due` is specified in `YYYY-MM-DD` format.

```bash
gfo milestone create "v1.0 Release" --due 2024-12-31
```

### gfo milestone delete

```
gfo milestone delete NUMBER
```

```bash
gfo milestone delete 3
```

---

## gfo comment

Operate PR or Issue comments.

> **Supported services**: All services (comment update / delete: GitHub, Backlog, Gitea, Forgejo, GitBucket only)

### gfo comment list

```
gfo comment list {pr,issue} NUMBER [--limit N]
```

```bash
gfo comment list pr 42
gfo comment list issue 10 --limit 50
```

### gfo comment create

```
gfo comment create {pr,issue} NUMBER --body BODY
```

```bash
gfo comment create pr 42 --body "LGTM!"
gfo comment create issue 10 --body "I can reproduce this on v1.2.3"
```

### gfo comment update

```
gfo comment update COMMENT_ID --body BODY --on {pr,issue}
```

```bash
gfo comment update 12345 --body "Updated comment" --on pr
```

### gfo comment delete

```
gfo comment delete COMMENT_ID --on {pr,issue}
```

```bash
gfo comment delete 12345 --on issue
```

---

## gfo review

Operate PR reviews.

> **Supported services**: GitHub, GitLab

### gfo review list

```
gfo review list NUMBER
```

```bash
gfo review list 42
```

### gfo review create

```
gfo review create NUMBER {--approve | --request-changes | --comment} [--body BODY]
```

One of `--approve`, `--request-changes`, or `--comment` is required.

```bash
gfo review create 42 --approve
gfo review create 42 --request-changes --body "Please fix the tests"
gfo review create 42 --comment --body "Looks interesting, will review more later"
```

---

## gfo branch

Operate branches.

> **Supported services**: All services (branch create / delete: Gogs not supported)

### gfo branch list

```
gfo branch list [--limit N]
```

```bash
gfo branch list
```

### gfo branch create

```
gfo branch create NAME --ref REF
```

`--ref` accepts a SHA or branch name.

```bash
gfo branch create feature/new-ui --ref main
gfo branch create hotfix/v1 --ref abc123def456
```

### gfo branch delete

```
gfo branch delete NAME
```

```bash
gfo branch delete feature/old-ui
```

---

## gfo tag

Operate tags.

> **Supported services**: All services (tag create: Gogs / GitBucket not supported. tag delete: Gogs not supported)

### gfo tag list

```
gfo tag list [--limit N]
```

### gfo tag create

```
gfo tag create NAME --ref REF [--message MSG]
```

```bash
gfo tag create v1.0.0 --ref main
gfo tag create v1.0.0 --ref main --message "Release v1.0.0"
```

### gfo tag delete

```
gfo tag delete NAME
```

```bash
gfo tag delete v0.9.0-beta
```

---

## gfo status

Operate commit statuses (CI statuses).

> **Supported services**: GitHub, GitLab, Gitea, Forgejo

### gfo status list

```
gfo status list REF [--limit N]
```

```bash
gfo status list main
gfo status list abc123def456
```

### gfo status create

```
gfo status create REF --state {success,failure,pending,error} [--context CTX] [--description DESC] [--url URL]
```

```bash
gfo status create main --state success --context "ci/tests" --description "All tests passed"
gfo status create abc123 --state failure --context "ci/lint" --url https://ci.example.com/build/42
```

---

## gfo file

Operate files in a repository.

> **Supported services**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo, Gogs, GitBucket (Backlog not supported. Gogs supports file get only)

### gfo file get

Get the contents of a file.

```
gfo file get PATH [--ref REF]
```

```bash
gfo file get README.md
gfo file get src/main.py --ref feature/new-ui
```

### gfo file put

Create or update a file. Reads file contents from standard input.

```
gfo file put PATH --message MSG [--branch BRANCH]
```

```bash
echo "Hello" | gfo file put hello.txt --message "Add hello.txt"
cat myfile.py | gfo file put src/myfile.py --message "Update myfile" --branch feature/update
```

### gfo file delete

```
gfo file delete PATH --message MSG [--branch BRANCH]
```

```bash
gfo file delete old-file.txt --message "Remove old-file.txt"
```

---

## gfo webhook

Manage webhooks.

> **Supported services**: GitHub, GitLab, Bitbucket, Backlog, Gitea, Forgejo, Gogs, GitBucket (Azure DevOps not supported)

### gfo webhook list

```
gfo webhook list [--limit N]
```

### gfo webhook create

```
gfo webhook create --url URL --event EVENT [--event EVENT ...] [--secret SECRET]
```

`--event` can be specified multiple times.

```bash
gfo webhook create --url https://example.com/hook --event push --event pull_request
gfo webhook create --url https://example.com/hook --event push --secret mysecret
```

### gfo webhook delete

```
gfo webhook delete ID
```

```bash
gfo webhook delete 5
```

---

## gfo deploy-key

Manage deploy keys.

> **Supported services**: GitHub, GitLab, Bitbucket, Gitea, Forgejo, Gogs (Azure DevOps / Backlog / GitBucket not supported)

### gfo deploy-key list

```
gfo deploy-key list [--limit N]
```

### gfo deploy-key create

```
gfo deploy-key create --title TITLE --key KEY [--read-write]
```

```bash
gfo deploy-key create --title "CI Server" --key "ssh-rsa AAAA..."
gfo deploy-key create --title "Deploy Bot" --key "ssh-ed25519 AAAA..." --read-write
```

### gfo deploy-key delete

```
gfo deploy-key delete ID
```

```bash
gfo deploy-key delete 3
```

---

## gfo collaborator

Manage collaborators (repository members).

> **Supported services**: GitHub, GitLab, Bitbucket, Gitea, Forgejo, Gogs, GitBucket (Azure DevOps / Backlog not supported. collaborator add / remove: Bitbucket also not supported)

### gfo collaborator list

```
gfo collaborator list [--limit N]
```

### gfo collaborator add

```
gfo collaborator add USERNAME [--permission {read,write,admin}]
```

| Option | Default | Description |
|---|---|---|
| `--permission` | `write` | Permission level to grant |

```bash
gfo collaborator add alice
gfo collaborator add bob --permission admin
```

### gfo collaborator remove

```
gfo collaborator remove USERNAME
```

```bash
gfo collaborator remove alice
```

---

## gfo ci

Operate CI/CD pipeline jobs and workflows.

> **Supported services**: GitHub, GitLab, Gitea, Forgejo

### gfo ci list

```
gfo ci list [--ref REF] [--limit N]
```

```bash
gfo ci list
gfo ci list --ref main
```

### gfo ci view

```
gfo ci view ID
```

```bash
gfo ci view 12345678
```

### gfo ci cancel

```
gfo ci cancel ID
```

```bash
gfo ci cancel 12345678
```

---

## gfo user

Display authenticated user information.

> **Supported services**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo, Gogs, GitBucket (Backlog not supported)

### gfo user whoami

Display information about the authenticated user.

```bash
gfo user whoami
```

---

## gfo search

Search repositories and issues.

> **Supported services**: GitHub, GitLab

### gfo search repos

```
gfo search repos QUERY [--limit N]
```

```bash
gfo search repos "cli tool" --limit 20
```

### gfo search issues

```
gfo search issues QUERY [--limit N]
```

```bash
gfo search issues "login bug" --limit 10
```

---

## gfo wiki

Manage wiki pages.

> **Supported services**: GitLab, Gitea, Forgejo

### gfo wiki list

```
gfo wiki list [--limit N]
```

### gfo wiki view

```
gfo wiki view ID
```

### gfo wiki create

```
gfo wiki create --title TITLE --content CONTENT
```

```bash
gfo wiki create --title "Getting Started" --content "# Getting Started\n\nWelcome!"
```

### gfo wiki update

```
gfo wiki update ID [--title TITLE] [--content CONTENT]
```

```bash
gfo wiki update 1 --title "New Title"
```

### gfo wiki delete

```
gfo wiki delete ID
```

```bash
gfo wiki delete 1
```

---

## gfo browse

Open the repository, PR, or issue URL in the default browser. No API calls are made.

> **Supported services**: All services

```
gfo browse [--pr N | --issue N | --settings] [--print]
```

| Option | Description |
|---|---|
| (none) | Open repository top page |
| `--pr N` | Open PR #N page |
| `--issue N` | Open Issue #N page |
| `--settings` | Open repository settings page |
| `--print` | Print URL to stdout instead of opening browser |

```bash
gfo browse                     # Open repository top page
gfo browse --pr 42             # Open PR #42
gfo browse --issue 7           # Open Issue #7
gfo browse --settings          # Open settings page
gfo browse --pr 42 --print     # Print URL only (don't open browser)
```

> Backlog does not support `--issue` / `--settings` (`NotSupportedError`)

---

## gfo branch-protect

Manage branch protection rules.

> **Supported services**: GitHub, GitLab, Bitbucket, Gitea, Forgejo
>
> **Note**: Bitbucket only supports force-push and deletion control. Review requirements (`--require-reviews`), status checks (`--require-status-checks`), and admin enforcement (`--enforce-admins`) are not supported.

### gfo branch-protect list

```
gfo branch-protect list [--limit N]
```

### gfo branch-protect view

```
gfo branch-protect view BRANCH
```

### gfo branch-protect set

```
gfo branch-protect set BRANCH [--require-reviews N] [--require-status-checks CHECK...] [--enforce-admins | --no-enforce-admins] [--allow-force-push | --no-allow-force-push] [--allow-deletions | --no-allow-deletions]
```

| Option | Description |
|---|---|
| `--require-reviews N` | Required number of review approvals (0 to disable) |
| `--require-status-checks CHECK...` | Required status check names (multiple allowed) |
| `--enforce-admins` / `--no-enforce-admins` | Enforce protection for admins |
| `--allow-force-push` / `--no-allow-force-push` | Allow force push |
| `--allow-deletions` / `--no-allow-deletions` | Allow branch deletion |

```bash
gfo branch-protect set main --require-reviews 2 --no-allow-force-push
```

### gfo branch-protect remove

```
gfo branch-protect remove BRANCH
```

```bash
gfo branch-protect remove main
```

---

## gfo notification

Manage inbox notifications.

> **Supported services**: GitHub, GitLab, Gitea, Forgejo, Backlog

### gfo notification list

```
gfo notification list [--unread-only] [--limit N]
```

| Option | Default | Description |
|---|---|---|
| `--unread-only` | false | Show unread only |
| `--limit N` | 30 | Maximum number of results |

```bash
gfo notification list --unread-only
```

### gfo notification read

```
gfo notification read [ID] [--all]
```

| Argument/Option | Description |
|---|---|
| `ID` | Notification ID to mark as read |
| `--all` | Mark all notifications as read |

```bash
gfo notification read 12345      # Mark specific notification as read
gfo notification read --all      # Mark all as read
```

---

## gfo org

Manage organizations (Organization / Group / Workspace).

> **Supported services**: GitHub, GitLab, Bitbucket, Azure DevOps, Gitea, Forgejo, Gogs

### gfo org list

```
gfo org list [--limit N]
```

### gfo org view

```
gfo org view NAME
```

### gfo org members

> Azure DevOps does not support `org members` (use Teams for member management).

```
gfo org members NAME [--limit N]
```

```bash
gfo org members my-org
```

### gfo org repos

```
gfo org repos NAME [--limit N]
```

```bash
gfo org repos my-org --limit 50
```

---

## gfo ssh-key

Manage user SSH public keys.

> **Supported services**: GitHub, GitLab, Bitbucket, Gitea, Forgejo, Gogs

### gfo ssh-key list

```
gfo ssh-key list [--limit N]
```

### gfo ssh-key create

```
gfo ssh-key create --title TITLE --key PUBLIC_KEY
```

```bash
gfo ssh-key create --title "My Laptop" --key "ssh-ed25519 AAAA..."
```

### gfo ssh-key delete

```
gfo ssh-key delete ID
```

```bash
gfo ssh-key delete 12345
```

---

## gfo secret

Manage CI/CD secrets (encrypted values, not readable).

> **Supported services**: GitHub, GitLab, Bitbucket, Gitea, Forgejo

### gfo secret list

```
gfo secret list [--limit N]
```

### gfo secret set

```
gfo secret set NAME {--value VALUE | --env-var ENV_VAR | --file FILE}
```

| Option | Description |
|---|---|
| `--value VALUE` | Secret value (passed in plaintext) |
| `--env-var ENV_VAR` | Read value from environment variable |
| `--file FILE` | Read value from file |

```bash
gfo secret set API_KEY --value "sk-xxxx"
gfo secret set DB_PASSWORD --env-var MY_DB_PASS
gfo secret set CERT --file ./cert.pem
```

> GitHub requires PyNaCl for encryption (`pip install PyNaCl`).

### gfo secret delete

```
gfo secret delete NAME
```

---

## gfo variable

Manage CI/CD variables (plaintext values, readable).

> **Supported services**: GitHub, GitLab, Bitbucket, Gitea, Forgejo

### gfo variable list

```
gfo variable list [--limit N]
```

### gfo variable set

```
gfo variable set NAME --value VALUE [--masked]
```

| Option | Description |
|---|---|
| `--value VALUE` | Variable value (required) |
| `--masked` | Set as masked variable (GitLab only) |

```bash
gfo variable set NODE_ENV --value "production"
gfo variable set SECRET_KEY --value "abc" --masked   # GitLab only
```

### gfo variable get

```
gfo variable get NAME
```

```bash
gfo variable get NODE_ENV
```

### gfo variable delete

```
gfo variable delete NAME
```
