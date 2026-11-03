# Adapters

Shared adapter conventions, then each service's own rules. The root AGENTS.md maps every rule's paths, including tests and the Azure DevOps command modules, to this file.

## Adapter Common Conventions

Applies to `src/gfo/adapter/**`, `tests/test_adapters/**`.

### New Adapter Checklist

When adding a new service from scratch, survey all of the following locations before starting
(for details on each, see the subsections of this section and the service sections of this file,
GitHub through Gitea Family).

1. **`src/gfo/adapter/{service}.py`**: Inherit from `GitServiceAdapter` (or the `GitHubLikeAdapter` mixin) and register with `@register("{service}")`
2. **`src/gfo/adapter/registry.py`**
   - `create_http_client()` (L36–): Add a branch for the authentication method (one of `auth_header` / `auth_params` / `basic_auth`)
   - `create_adapter()` (L68–): Add a `kwargs` branch only if the constructor needs extra arguments (`project_key`, etc.)
3. **`tests/test_adapters/conftest.py`**: Add the `{service}_client` + `{service}_adapter` fixtures for the service
4. **`tests/test_adapters/test_{service}.py`**: Create unit tests, including 404/403 error tests and empty list `[]` tests (see `tests/AGENTS.md`)
5. **`AGENTS.md`** (root): Add the identifier and authentication environment variable to the "Supported services" table
6. **`src/gfo/adapter/AGENTS.md`** (this file): Add the service's quirks (pagination method, unsupported APIs, response format differences, etc.) as a new service section
7. **i18n**: If you add user-facing text, add translations to `src/gfo/locale/ja/LC_MESSAGES/gfo.po` (`.mo` is generated at build time, so do not commit it)
8. **`docs/commands.md` / `docs/commands.ja.md`**: Document any options valid only for the new service or any behavior differences

### Inheritance Tree and Registration

```
GitServiceAdapter (ABC, adapter/base.py)
├── GitHubAdapter           @register("github")      * also uses the GitHubLikeAdapter mixin
│   └── GitBucketAdapter    @register("gitbucket")
├── GitLabAdapter           @register("gitlab")
├── BitbucketAdapter        @register("bitbucket")
├── BacklogAdapter          @register("backlog")
├── AzureDevOpsAdapter      @register("azure-devops")
└── GiteaAdapter            @register("gitea")       * also uses the GitHubLikeAdapter mixin
    ├── ForgejoAdapter      @register("forgejo")
    └── GogsAdapter         @register("gogs")
```

- `GitHubAdapter` / `GiteaAdapter` use multiple inheritance: `class XxxAdapter(GitHubLikeAdapter, GitServiceAdapter)`.
- `GitBucketAdapter` is a **subclass of `GitHubAdapter`** (not `GiteaAdapter`, because GitBucket is GitHub API compatible).
- `GitHubLikeAdapter` (`adapter/github_like.py`) is a mixin of shared `_to_*` conversion helpers for the GitHub/Gitea family.
  The `GitHubLikeAdapter` at the end of `base.py` is a backward-compatible re-export, not the actual definition.

### Import Paths for Shared Symbols (Canonical)

New adapters must import through the same paths as the existing concrete adapters:

| Symbol | Path |
|---|---|
| `GitServiceAdapter`, `_wrap_conversion_error`, `_mask_token_in_exception` | `from .base import ...` (defined in `_helpers.py`, but re-exported by `base.py`) |
| Data classes (`PullRequest`, etc.) | `from .models import ...` |
| `GitHubLikeAdapter` (GitHub/Gitea family only) | `from .github_like import ...` |

Only `github_like.py` itself imports directly from `._helpers`, to avoid a circular import with `base.py`. Adapter implementations must not copy this.

### Data Class Conventions

All data classes live in `adapter/models.py` (no dependencies beyond the standard library).
All are `@dataclass` with `frozen=True, slots=True`:
`PullRequest`, `Issue`, `Repository`, `Release`, `Label`, `Milestone`, and others

### The state Parameter of list_milestones

`list_milestones(*, state: str = "open", limit: int = 0)`. When the `state` query parameter is
omitted, GitHub/Gitea return only `open` (closed milestones are never returned unless `state=all` is given explicitly).
GitLab's `state` parameter accepts only `active`/`closed`; there are no `open`/`all` values,
and omitting it returns everything (active + closed). Therefore `GitLabAdapter.list_milestones()` maps
`"open"→"active"`, `"closed"→"closed"`, and `"all"→` omit the parameter.
For Bitbucket/Backlog/Azure DevOps/Gogs, milestones themselves raise `NotSupportedError`, so `state` is unused.

- Past bug (#206): GitHub/Gitea `list_milestones()` never sent `state`, so
  closed milestones never appeared in `gfo milestone list` or in `_resolve_milestone_id_by_title`
  (title resolution for `--milestone <title>`). The latter was fixed to query
  explicitly with `state="all"` (`base.py: _resolve_milestone_id_by_title`).

### Return Value of create_or_update_file

Return type: `str | None`. **Adapters that can return the commit SHA must return it.**

| Adapter | Returned value |
|---|---|
| GitHub / Gitea / Forgejo | `commit.sha` (PUT/POST response) |
| Azure DevOps | `commits[0].commitId` (pushes API response) |
| GitLab / Bitbucket / Gogs / others | `None` (the API does not return a SHA) |

Reason: to avoid branch HEAD propagation delay. Passing the commit SHA as `ref` references the object directly.

### Pagination Methods (`http.py`)

| Method | Services | Function |
|---|---|---|
| `Link` header | GitHub / Gitea family (including Forgejo, Gogs, GitBucket) | `paginate_link_header` |
| `X-Next-Page` header | GitLab | `paginate_page_param` |
| `values`/`next` in the response body | Bitbucket Cloud | `paginate_response_body` |
| `offset`/`count` query parameters | Backlog | `paginate_offset` |
| `$top`/`$skip` query parameters | Azure DevOps | `paginate_top_skip` |

- Past bug (#135): The table wrongly listed Azure DevOps as using `continuationToken`. Some endpoints such as
  `Builds - List` officially support `continuationToken` (see the "Azure DevOps is out of scope" item
  below), but `http.py` has no `continuationToken`-based `paginate_*` function, and list operations actually
  use `paginate_top_skip` with `$top`/`$skip`. The methods for the Gitea family (actually the `Link` header) and
  Backlog (actually `offset`/`count`) were also swapped, and the Bitbucket Cloud row
  (`paginate_response_body`) was missing entirely

### Fetching the Job/Step List in get_pipeline_logs

In the branch of `get_pipeline_logs(pipeline_id, *, job_id=None)` where `job_id` is not given (the path that
fetches logs for the whole pipeline/build at once), if the endpoint that lists jobs/steps actually
supports pagination, always use the same pagination helper as the other list methods in the
same file. However, do not assume "it is a list operation, so route it through a pagination helper mechanically" —
check the official documentation for each endpoint individually to confirm that the endpoint itself
actually supports pagination parameters.

- Past bug (#145, #146): In three adapters — GitLab (`paginate_page_param`), GitHub (manual `per_page`/`page` loop;
  "List jobs for a workflow run" officially supports `per_page`/`page`, max 100), and Bitbucket
  (`paginate_response_body`) — only `get_pipeline_logs` bypassed the pagination used by the other methods in
  its own file, so for pipelines with more jobs/steps than each service's default page size (GitLab/Gitea: 20,
  GitHub: 30–100, Bitbucket: the `pagelen` default), logs past the page boundary were silently dropped
  with no error or warning
- **Azure DevOps is out of scope** (investigated in #146): `Build Logs - List` (`GET /build/builds/{id}/logs`)
  officially supports no query parameters other than `api-version`. It is a different endpoint from
  `Builds - List` (which explicitly supports `$top`/`continuationToken`), used by `list_pipelines` and others
  in the same file, and was judged not to support pagination. Mechanically applying `paginate_top_skip`
  risks an infinite loop that keeps fetching the same page if the server ignores unknown query
  parameters (this incorrect application was once flagged in pre-commit review and reverted)

### Output and Filter Conventions

- **`--jq` support is required**: Every handler must connect the `jq` argument to its output (widening only the signature without connecting it is forbidden)
- **Handlers returning `list[str]` / `dict`**: `output()` cannot be used → apply `apply_jq_filter` directly
- **Order of applying limit**: Apply limit after filtering (applying it before filtering yields too few results)
- **Success messages in mutation handlers**: Use `output_result()`, not bare `print()` (bare `print()` ignores `fmt`/`jq` and returns plain text)
  - Past bug (missed in #63, #142): Only `handle_dismiss` in `review.py` used bare `print(_(...))`, so a plain-text message was returned even with `--format json`. Watch for the "looks supported" pattern where only the `fmt`/`jq` arguments are added to the signature and left unused in the handler body

### Upsert Pattern

- **set methods** (`set_variable`, `set_secret`, etc.): Check existence with GET → use PUT (update) / POST (create) accordingly
  - POST alone causes an API error for existing resources

### Method and Code Conventions

- **Method signatures**: Do not accept `**kwargs`; use the same explicit keyword arguments as `base.py`
- **`from __future__ import annotations`**: Required in every `commands/*.py`
- **Organization.url**: Return the web URL, not the API URL
- **Delete/write handlers**: Output success messages with `output_result()` (follow the existing label/webhook handlers; for `--jq`/`--format` support details, see the "Output and Filter Conventions" subsection)

### HTTP Timeout and Retry

- **Timeout**: Specify `timeout=30` on every request (the `requests` default is None = unlimited)
- **Retry**: Automatically retry only 429 (rate limit), at most once. Respect the `Retry-After` header; wait 60 seconds if it is absent
- **Other HTTP errors**: No retry

### Defensive Coding

- Do not unconditionally assume a field exists → `data.get("field") or default`
- `assignee` and similar fields require an `isinstance(val, dict)` check
- Always wrap KeyError/TypeError inside `_to_*` in GfoError

## GitHub Adapter Rules

Applies to `**/github.py`, `**/test_github.py`.

### Key Implementation Patterns

- **list_issues**: Filter with `"pull_request" not in r` to exclude PRs
- **state="merged"**: The GitHub API returns these as `closed`, so filter on the client side
  ```python
  if state == "merged":
      items = [pr for pr in items if pr.merged_at is not None]
  ```
- **search_issues**: Automatically add `is:issue` to the query (so PRs are not mixed in)
- **create_or_update_file**: Return `commit.sha` (to counter branch propagation delay)
- **Authentication**: `Authorization: Bearer {token}` header
- **Release deletion**: Deleting a release does not delete its tag automatically. To delete the tag too, call `DELETE /git/refs/tags/{tag}` separately
- **ID resolution for release deletion**: Two steps from tag name → release id (`GET /releases/tags/{tag}` → `DELETE /releases/{id}`)

## GitLab Adapter Rules

Applies to `**/gitlab.py`, `**/test_gitlab.py`.

### Key Implementation Patterns

- **iid vs global id**: In GitLab, `iid` (sequential number within a project) and `id` (global) are different things
  - `delete_milestone` and similar operations need to resolve iid → global id
- **state mapping**: Convert GitLab `opened` → gfo `open`
- **Repository identification**: Use `path` (URL-safe), not `name`
- **Label color**: GitLab uses `#RRGGBB` format. Be careful handling the `#` prefix when adding/removing
- **merge_pull_request**: With `method="rebase"`, GitLab's `/rebase` endpoint only rebases onto the target branch and does not merge. Perform the actual merge in three steps: `/rebase` → poll with `GET` using `include_rebase_in_progress=true` (until `rebase_in_progress` becomes `false`; if `merge_error` is present, raise it as a failure) → `/merge`
  - Past bug: It called `/rebase` and returned immediately, so the MR was only rebased, never merged, and stayed open (no exception was raised, so it looked successful)
- **create_or_update_file**: Return `None` (the GitLab files API does not return a SHA)
- **Authentication**: `PRIVATE-TOKEN: {token}` header
- **URL-encoding the project ID**: Encode `owner/repo` with `%2F` (`urllib.parse.quote(path, safe='')`). Subgroups `group/sub/repo` are handled the same way
- **Pagination**: An empty `X-Next-Page` header = last page. List operations through `paginate_page_param()` never have the caller specify `per_page` explicitly; the function's default of 100 (equal to the GitLab API maximum) is used, but if `limit` (from `--limit`) is below 100, `per_page` is lowered to `limit` (`if 0 < limit < per_page: per_page = limit` in `http.py`). The GitLab API's own default when unspecified is 20, but this path sends `per_page` explicitly and does not depend on it. However, plain GETs that do not go through `paginate_page_param()`, such as `_resolve_milestone_id_by_title` (fetches `milestones` with only a `title` filter) and `list_issue_templates` (`templates/issues`), do not specify `per_page`, so GitLab's default when unspecified (20) applies as is
  - Past bug (#245): The rule said "default 20", wrongly describing the GitLab API's own default when unspecified as if it were the value gfo sends for list operations through `paginate_page_param()`. The same kind of rule file drift as #135
- **Paths that must be URL-encoded**: URL-encode the tag name/label name in DELETE requests for release tags and labels
- **`remove_issue_reaction`**: Do not narrow the `list_issue_reactions` results by `content` alone; first restrict them to your own reactions with `get_current_username()`, then decide the ID to delete (the same bug class as the equivalent GitHub fix #161)
  - Past bug: It deleted the first match by content alone, so it could delete another user's reaction of the same kind
- **`set_variable`**: In GitLab, `gfo secret` and `gfo variable` share the same CI/CD variables collection, distinguished by the `masked` flag. When you GET an existing record, read `masked` and PUT with the logical OR of it and the caller's `masked` (the same root cause as the Bitbucket `secured` flag filtering, #138)
  - Past bug: It unconditionally PUT with the caller's default `masked: False` without checking an existing `masked: True` (secret), so `gfo variable set` downgraded existing secrets to plain text
- **Pipeline status in `list_pull_request_checks`** (`CheckRun.status`): A GitLab CI pipeline's `status` can officially take 11 values: `created`/`waiting_for_resource`/`preparing`/`pending`/`running`/`success`/`failed`/`canceled`/`skipped`/`manual`/`scheduled`. `status_map` must cover all of them (an unmapped value leaks into `CheckRun.status` as an off-contract raw value through the `.get(status, status)` fallback)
  - Past bug (#230): `waiting_for_resource` (when using `resource_group`), `preparing`, and `scheduled` (delayed job) were missing from `status_map` and leaked as raw values. Fixed by normalizing all of them to `"pending"`
- **`remove_issue_dependency`**: GitLab's Issue Links API needs the internal `issue_link_id` for deletion, which cannot be given directly from `depends_on` (the target issue's iid), so the procedure is: list → search for a matching `iid` → DELETE the matching link. If no matching link is found, raise `NotFoundError` (do not silently finish successfully)
  - Past bug (#218): There was no fallback for the no-match case, so it exited the `for` loop, implicitly returned `None`, and finished successfully. The CLI layer (`handle_depends`) does not check the return value and always prints a success message, so it displayed "deleted" even for a dependency that no longer existed. Azure DevOps has the same bug class, tracked in #242
- **`update_comment`/`delete_comment`**: The issue/MR number (`number`) is required in the URL (`/issues/:iid/notes/:id` or `/merge_requests/:iid/notes/:id`).
  `ConfigError` when `number` is not given (#197)

## Bitbucket Adapter Rules

Applies to `**/bitbucket.py`, `**/test_bitbucket.py`.

### Authentication

- Token format: `email:api-token` (colon-separated)
- Sent with Basic authentication (`Authorization: Basic {base64(email:api-token)}`)
- Environment variable: `BITBUCKET_TOKEN`

### Key Implementation Patterns

- **Every place that embeds a value into BQL (Bitbucket Query Language) must go through `_escape_bql_string()`**: Places that embed a string into the `q=` query parameter as `f'field="{value}"'` (`list_issues`/`list_pull_requests`/`search_repositories`, etc.) must all be escaped without exception, including branches that pass values directly
  - Past bug (#174/#180/#183): `author`/`base`/`head` (PR list) and the direct-value branch for `state` (issue list) were embedded into the literal unescaped, so a value containing `"` terminated the literal early and subsequent BQL expressions could be injected. When fixing, check existing similar branches across the code, not just newly added places (#183 was a branch "of the same class but overlooked", found during the review of #180)
- **list_issues label filter**: `component.name="{label}"` query parameter
  - Past bug: The parameter was left unused
- **state**: Uppercase format `OPEN`, `MERGED`, `DECLINED`
- **Fetching collaborators**: Use the `permissions-config/users` endpoint
  - Past bug: It used workspace members, which was wrong
- **assignee check**: Always check `isinstance(assignee, dict)`
  - Past bug: KeyError occurred when it was not a dict
- **create_or_update_file**: Return `None` (the Bitbucket API does not return a SHA)
- **`url` in `create_commit_status`**: Bitbucket's Build Status API requires `url`. When `--url` is omitted, the fallback must be `{_web_base_url()}/{owner}/{repo}/commits/{ref}` (the target commit's actual web UI page)
  - Past bug (#179): The fallback was a fixed, unrelated dummy value `https://example.com`, so status links in the Bitbucket UI led to an IANA reserved domain

### Branch Protection and Pipeline Variables

- **`get_branch_protection`**: Filtering with `params={"kind": "push"}` is forbidden (fetch all kinds)
  - Past bug: The kind filter caused missed results
- **`_find_pipeline_variable_uuid`**: Use `limit=0` (fetch all)
  - Past bug: With a 100-item cap, variables were not found
- **`_find_pipeline_variable_uuid`**: Secrets (`secured: True`) and variables (`secured: False`) share the same collection, so filter by the `secured` flag passed as an argument, not just by name
  - Past bug: It did not filter by the `secured` flag, so `variable set` with the same name as an existing secret overwrote the secret with `secured: False`, turning it into plain text
- **`set_variable` / `set_secret`**: The upsert pattern is required (check existence with GET → use PUT/POST accordingly)
  - Past bug: POST alone caused an API error for existing variables

### Repository Update

- **Unsupported parameters in `update_repository`**: `default_branch`/`archived` cannot be changed through the Bitbucket API. Include both in the `_warn_unsupported_params` call (do not put them in the payload, and do not silently ignore them)
  - Past bug (#232): `archived` was included in the warning, but `default_branch` was missed, leaving an in-between state where specifying `--default-branch` did nothing without a warning

### PR checkout

- **The refspec is a branch name**: Unlike GitHub's `refs/pull/{number}/head`, return the source branch name as is

### File Operations

- **multipart/form-data**: `create_or_update_file` sends `multipart/form-data`, not JSON

### Unsupported Features

Overridden with `NotSupportedError`: `releases`, `labels`, `milestones`

### Comment Update/Delete

`update_comment`/`delete_comment` require the issue/PR number (`number`) in the URL (`comment_id` alone cannot identify the target).
`ConfigError` when `number` is not given (#197).

### Deploy Key

- **`create_deploy_key`**: Bitbucket Cloud Access Keys (Deploy Keys) are fixed as read-only at the API level, and no parameter to choose read/write exists at all (that feature exists only in Bitbucket **Server** (the on-premises edition), not in Cloud). When `read_only=False` (equivalent to `--read-write`) is passed, add nothing to the payload and warn explicitly with `warnings.warn`
  - The truthy check in `_warn_unsupported_params` cannot be used (`read_only=False` is falsy and goes undetected), so it needs a separate warning through an explicit `if not read_only:` check (#200)

### SSH Key / GPG Key

- **Use the authenticated user's UUID for `{selected_user}`**: `/users/{selected_user}/ssh-keys` and `/users/{selected_user}/gpg-keys` are endpoints for personal accounts only, and `{selected_user}` must be the authenticated user's own UUID (or Atlassian Account ID), not a workspace slug. Use `_current_user_uuid()` (`get_current_user()["uuid"]`)
  - Past bug (#216): It embedded the owner segment of the repository spec (`self._owner`) directly as `{selected_user}`. For repositories owned by a personal account this could work because the owner happens to match the user's own username, but for repositories owned by a workspace (team) the owner is the workspace slug, which is invalid as a personal account identifier

## Azure DevOps Adapter Rules

Applies to `**/azure_devops.py`, `**/test_azure_devops.py`, `src/gfo/commands/init.py`, `src/gfo/commands/repo.py`.

### Required Parameters

- The constructor needs `organization` and `project_key`
- The manual setup path of `gfo init` has an extra input flow for `organization`
- Error message when URL construction fails: must include `'gfo init' を実行してください`

### Key Implementation Patterns

- **connectionData**: Call with the organization-level URL + `api-version=7.1-preview`
- **Content-Type**: `application/json-patch+json` (for Work Items operations)
- **Fetching issues**: Through WIQL queries
- **Branch names**: Strip the `refs/heads/` prefix before returning
- **create_or_update_file**: Return `commits[0].commitId` (pushes API response)
- **Authentication**: `AZURE_DEVOPS_PAT` with Basic authentication (empty username, password = PAT)

### Organizations

- **`list_org_repos`**: Fetch all with `limit=0` → filter by project name → apply `[:limit]`
  - Past bug: Applying limit before filtering yielded too few results
- **`_to_organization`**: Prefer `_links.web.href`; fall back to `https://dev.azure.com/{org}/{name}`
  - Past bug: It returned the API URL
- **`org members`**: `NotSupportedError` (Azure DevOps manages members by team and has no organization member list API)

### PR Merge

- **lastMergeSourceCommit is required**: Always GET the PR before merging and include `lastMergeSourceCommit` in the PATCH

### Issue (Work Items)

- **Determining state**: Open is determined as "NOT in closed states". State names differ by process template (Agile/Scrum/Basic), so they cannot be compared against fixed values
- **`close_issue`/`reopen_issue`**: For the same reason, the write side must not PATCH fixed state names ("Closed"/"New") either. Fetch the target work item type's state list with `GET /wit/workitemtypes/{type}/states`, resolve the target state by the template-independent `category` (Proposed/InProgress/Resolved/Completed/Removed), then PATCH
  - Past bug: It wrote the fixed value "Closed", which failed with the Scrum process template (which has no "Closed" state)
- **Default Work Item Type**: `Task` (not `Bug`)
- **`--state all`**: Omit the `searchCriteria.status` parameter (no catch-all value exists)

### Command-Side Notes

- `handle_create` in `commands/repo.py`: Checking `organization` / `project_key` for `None` is required

### changeType (diff / PR file list)

- `changeType` can be a comma-separated compound value (e.g. `"rename, edit"`). Both `list_pull_request_files()` and
  `compare()` must go through the module-level `_resolve_change_type()` (which takes the first element with
  `change_type.split(",")[0].strip().lower()` before mapping). Looking it up in the dictionary as a single value turns compound values into the fallback
  `"modified"`
  - Past bug (#137): Only `compare()` lacked this splitting, so files involving a rename were always
    misclassified as `"modified"` (`list_pull_request_files()` handled it correctly from the start)

### remove_issue_dependency

GET the work item's `relations`, find the relation matching `depends_on` (the target issue id),
and send a JSON Patch with `op: "remove"` (Azure DevOps needs the index in the relations array for deletion and
cannot target it directly by issue id). If no matching relation is found, raise `NotFoundError`
(do not silently finish successfully).

- Past bug (#242, the same bug class as GitLab's #218): There was no fallback for the no-match case, so it
  exited the `for` loop, implicitly returned `None`, and finished successfully. The CLI layer (`handle_depends` in
  `commands/issue.py`) does not check the return value and always prints a success message, so it displayed
  "deleted" even for a dependency that no longer existed

## Backlog Adapter Rules

Applies to `**/backlog.py`, `**/test_backlog.py`.

### Authentication

- Sent as the `apiKey` query parameter (not a header)
- Environment variable: `BACKLOG_API_KEY`

### Key Implementation Patterns

- **project_key is required**: Every operation needs `project_key`
- **issueKey format**: `PROJECT-123` (the numeric part is treated as `number`)
- **`_ensure_project_id`**: Converts and caches `project_key` → `project_id`
  - Wrap KeyError/TypeError in `GfoError`
- **`_resolve_merged_status_id`**: Resolves the merged status ID dynamically
  - Verify that the response is a list
  - On KeyError, skip and try the next element
- **`list_pull_requests`**: `params["statusId[]"] = [merged_id]` (pass as a list)
- **Issue statusId**: Besides the four standard statuses (1–4), each project may add custom statuses with ID 5 and above. Only `statusId == 4` is closed; everything else (including custom statuses) is open
- **`--state open` filter in `list_issues`**: Do not build `statusId[]` from a fixed list. Use `_resolve_all_status_ids()` (shares its cache with the result of `_fetch_statuses()`) to fetch all status IDs dynamically from `/projects/{projectKey}/statuses` (the issue status list), and use the IDs excluding closed
  - Past bug (#191): It always sent the fixed `statusId[] = [1, 2, 3]`, so issues with custom statuses were missed from the `--state open` list (including when omitted). Single fetch (`get_issue`) correctly determines open with `statusId != 4`, so the list and the single fetch behaved inconsistently
- **Keep the `--state open` filter in `list_pull_requests` fixed at `_PR_OPEN_STATUS_IDS = [1, 2, 3]`**. `/projects/{projectKey}/statuses` is the issue status list, and whether the PR status space is the same as the issue one is unconfirmed (the official documentation does not state it either). Do not apply the same dynamic resolution as `list_issues` to PRs
  - Past bug (#194): #191 also applied `_resolve_all_status_ids()` to PRs, so issue custom status IDs (e.g. id=6) were reused as is in the PR list's `statusId[]` filter
  - `_resolve_merged_status_id()` (used for `state="merged"`/`"all"`) also searches the same issue endpoint for a status whose name contains "merged", but whether this dynamic resolution actually works (whether issue status names containing "merged" exist in the real service) is unverified. It may always be falling back to the hard-coded `_STATUS_MERGED_ID = 5` (unconfirmed; needs verification against the real service)

### Automatic Resolution When Creating Issues

- **issueTypeId**: Use the first element of `/projects/{projectKey}/issueTypes`. `GfoError` if empty
- **priorityId**: From `/priorities`, prefer an element containing `"中"` or `"normal"`; otherwise the first element

### Comment Update/Delete

- **`update_comment`/`delete_comment`**: The issue/PR number (`number`) is required in the URL (the `issueIdOrKey`/PR number segment).
  `ConfigError` when `number` is not given (#197)
- **Deleting PR comments is unsupported**: The Backlog API has no endpoint equivalent to Delete Pull Request Comment, so
  it always raises `NotSupportedError` regardless of `number` (deleting issue comments and updating PR comments work when `number` is given)

### Webhook

- **events field**: Backlog's actual parameter name/response field is `activityTypeIds` (a numeric array using a fixed Activity Type ID scheme); no field of the form `events`/`type` exists. Conversion between gfo's generic event names (`events: list[str]`) and `activityTypeIds` is done by `_events_to_activity_type_ids()`/`_activity_type_ids_to_events()` (the `_ACTIVITY_TYPE_IDS` mapping)
  - Past bug (#198): It sent `payload["events"] = [{"type": e} for e in events]`, but Backlog does not recognize this field, and combined with `allEvent: false` it effectively created webhooks with "no event notifications"
- **secret is unsupported**: Backlog's Webhook API has no parameter for a signing secret. Warn about the `secret` argument of `create_webhook`/`update_webhook` with `_warn_unsupported_params` and do not include it in the payload
- **active is unsupported in update_webhook**: The Update Webhook API has no enable/disable parameter, so warn about the `active` argument with `_warn_unsupported_params` in the same way

## Gitea Family Rules

Applies to `**/gitea.py`, `**/forgejo.py`, `**/gogs.py`, `**/gitbucket.py`, `**/test_gitea.py`, `**/test_forgejo.py`, `**/test_gogs.py`, `**/test_gitbucket.py`.

### Common Patterns (Gitea / Forgejo / Gogs / GitBucket)

- **`_to_organization`**: Build the organization page URL as `{base_url}/{org_name}`, not from `data.get("website")`
  - Past bug: The `website` field is an external site URL, not the organization page URL
- **PR merge**: `Do` parameter (differs from GitHub's `merge_method`)
- **list_issues**: Filter with `type: "issues"` + `not r.get("pull_request")`
  - Gitea includes `pull_request: null` in issue responses
- **Pagination**: `per_page_key="limit"`
- **Milestones**: No `number` field → fall back to `id` (`github_like.py: _to_milestone`)
- **review state** (`github_like.py: _to_review`): Gitea's actual API values (`ReviewStateType` in `go-gitea/gitea`) use strings different from GitHub's. `state_map` must include both sets of values
  - `COMMENT` (Gitea) ≠ `COMMENTED` (GitHub)
  - `REQUEST_CHANGES` (Gitea) ≠ `CHANGES_REQUESTED` (GitHub)
  - `REQUEST_REVIEW` (Gitea-specific; review requested only, not submitted) → normalize to `pending`
  - Past bug (#187): Only GitHub values were mapped, so Gitea values did not match the map and became non-normalized strings (`comment`/`request_changes`) through the `raw_state.lower()` fallback. Existing tests (`test_gitea.py`) also tested only GitHub-style values, so the mismatch went unnoticed
- **`visibility`** (`github_like.py: _to_repository`): GitHub returns the `visibility` field (`"public"`/`"private"`/`"internal"`) directly, but Gitea/Forgejo have no such field and instead have two separate fields, `private` (bool) and `internal` (bool). The fallback check must look at `internal` as well as `private`
  - Past bug (#205): The fallback looked only at `private`, so Gitea internal repositories (`private: False, internal: True`) were always misclassified as `"public"`
- **issue dependency (`add_issue_dependency` / `remove_issue_dependency`)**: The request body is `{"index": ..., "owner": ..., "repo": ...}` (field names of the `IssueMeta` struct), not `{"id": ...}`
  - Past bug: It sent the `id` field, so Go's JSON binding left all fields at zero values
- **commit status "warning"** (`github_like.py: _to_check_run` / `_to_commit_status`): Gitea's commit status API returns five values: `pending`/`success`/`error`/`failure`/`warning`. `CheckRun.status` (`"success" | "failure" | "pending" | "running"`) and `CommitStatus.state` (`"success" | "failure" | "pending" | "error"`) each allow only their contract, so `warning`, which does not exist in GitHub, must be explicitly normalized to `failure` in both conversion functions (it is milder than failure in severity, but erring on the safe side is better than leaking the raw `"warning"` outside the contract)
  - Past bug (#227): `status_map` in `_to_check_run` had no mapping for `warning`, so the raw value `"warning"` leaked into `CheckRun.status` as is through the `.get(state, state)` fallback
  - Past bug (#229, adjacent to #227): `_to_commit_status` passed the raw `state`/`status` value through with no mapping at all, so `warning` likewise leaked into `CommitStatus.state`

### Gogs-Specific

- No `html_url` field → `data.get("html_url") or ""`
- Release API not supported → override with `NotSupportedError`
- Deploy key API not supported → `NotSupportedError` (`list/create/delete_deploy_key`)
- Repository creation: requires `readme: "Default"` in addition to `auto_init: True`
- `create_or_update_file`: `NotSupportedError`

### GitBucket-Specific

- **Parent class**: Subclass of `GitHubAdapter` (not `GiteaAdapter`)
- **Double JSON encoding**: PR create / release create responses are JSON strings → parse with `_parse_response()` (only create operations; list/get are normal)
- **close_issue**: PATCH /issues/{number} is not implemented → go through the web UI `POST /{owner}/{repo}/issue_comments/state`
- **Branch creation**: POST /git/refs returns 500 → use git clone + push instead
- **Default branch**: `master` (differs from GitHub's `main`)
- **`_to_release()` override**: Handles missing `created_at` / `html_url`
- **Deploy key API**: Endpoint not implemented (HTTP 500) → `NotSupportedError`
