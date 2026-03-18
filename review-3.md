# Review 3

## Findings

### 1. High: `gfo issue migrate` reopens closed issues on the destination

- Affected code: `src/gfo/commands/issue.py:257-274`, `src/gfo/commands/issue.py:299`
- `_migrate_one_issue()` always calls `dst.create_issue(...)` and then only migrates comments. It never mirrors `issue.state` from the source.
- `handle_migrate(... --all)` explicitly includes closed issues via `src_adapter.list_issues(state="all", limit=0)`, so closed issues are guaranteed to flow through this path.
- Result: closed issues are recreated as open issues on the target service, which is a behavioral corruption rather than a cosmetic mismatch.
- Repro:
  - Create a source issue with `state="closed"`.
  - Run `gfo issue migrate --from ... --to ... --number N`.
  - The migrated issue is created successfully, but no follow-up `close_issue()` is issued for the target.

### 2. Medium: issue migration silently truncates comment history at 30 comments

- Affected code: `src/gfo/commands/issue.py:265-269`
- `_migrate_one_issue()` fetches comments with `src.list_comments("issue", number)` and does not pass `limit=0`.
- The adapter contract defaults `list_comments(..., limit=30)` to 30 items (`src/gfo/adapter/base.py:896`), and the concrete adapters follow that default (`github.py:513`, `gitlab.py:848`, `gitea.py:519`, `bitbucket.py:492`, `backlog.py:489`, `azure_devops.py:771`).
- Result: any issue with 31 or more comments loses the tail of its discussion during migration, with no warning in the result output.
- Repro:
  - Migrate an issue that has more than 30 comments.
  - Only the first page of comments is copied because the source adapter is called with its default limit.

### 3. Medium: `SERVICE_SPEC` cannot address GitLab subgroup repositories

- Affected code: `src/gfo/commands/__init__.py:147-156`
- For non-Azure/Backlog services, `parse_service_spec()` requires exactly two path segments (`owner/repo`). That rejects valid GitLab repositories under nested groups such as `group/subgroup/repo`.
- This is inconsistent with the adapter itself: `GitLabAdapter._project_path()` explicitly supports subgroup owners, and there is already a test covering `group/sub1/sub2/myrepo` in `tests/test_adapters/test_gitlab.py:208-215`.
- Result: both `gfo issue migrate` and `gfo batch pr create` are unusable for GitLab subgroup projects even though the underlying adapter supports them.
- Repro:
  - Call `parse_service_spec("gitlab:group/subgroup/repo")`.
  - It raises `ConfigError: Invalid service spec format...` instead of producing a valid `ServiceSpec`.

## Validation

- Ran: `pytest tests/test_commands/test_service_spec.py tests/test_commands/test_issue_migrate.py tests/test_commands/test_batch.py -q`
- Ran: `pytest tests/test_cli.py -q`
- Both commands passed, so these issues are gaps in behavioral coverage rather than currently failing tests.