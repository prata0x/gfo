# gfo package

The exception hierarchy and the configuration and authentication rules. The root AGENTS.md maps their paths, tests included, to this file.

## Exception hierarchy

Applies to `src/gfo/**`, `tests/**`.

### Exception tree

```
GfoError
├── GitCommandError         # git command execution failed
├── DetectionError          # automatic service detection failed
├── ConfigError             # configuration resolution failed / validation error
├── AuthError               # no credentials
├── HttpError               # HTTP error base
│   ├── AuthenticationError # 401/403
│   ├── NotFoundError       # 404
│   ├── RateLimitError      # 429
│   ├── ValidationError     # 400/422 (with details parsed from the JSON body)
│   └── ServerError         # 5xx
├── NetworkError            # ConnectionError/Timeout/SSLError
├── NotSupportedError       # operation the service does not support
├── PartialFailureError     # one or more items failed in bulk processing (batch / migrate)
└── UnsupportedServiceError # unknown service type
```

### Which exception to use

| Situation | Exception |
|---|---|
| Validation failure (invalid configuration value) | `ConfigError` |
| Token not set | `AuthError` |
| Unexpected API response structure | `GfoError` (wrapping KeyError/TypeError/AttributeError) |
| Validation inside the HTTP layer | `ValueError` (OK as is) |
| Partial failure in bulk processing (exit code signal after results are output) | `PartialFailureError` |

### Wrapping pattern in `_to_*` (required)

Wrap `_to_*` conversion methods with the `@_wrap_conversion_error` decorator:

```python
@staticmethod
@_wrap_conversion_error
def _to_pull_request(data: dict) -> PullRequest:
    return PullRequest(number=data["number"], ...)
```

The decorator catches `(KeyError, TypeError, AttributeError)` and converts them to
`GfoError("Unexpected API response: missing field {e}")`.
`AttributeError` is included because a differently shaped API response can raise it,
for example when `data["user"]` unexpectedly arrives as a `str` or similar and
`.get("login")` raises `AttributeError`, and we want to wrap it in `GfoError` consistently.

Keep a hand-written try/except only where additional exceptions such as `ValueError`
or `IndexError` must also be caught (the decorator does not catch them).

### i18n of error messages and warnings (required)

Messages passed to user-facing exceptions (`GfoError` / `ConfigError` / `AuthError` / `DetectionError` /
`HttpError` family) and to `warnings.warn()` must always go through `_()`, with a ja
translation added to `.po` (`warnings.warn()` is included because it is also shown directly
to the user, making it a "user-facing message" just like exception messages):

```python
raise ConfigError(_("No tokens configured for host: {host}").format(host=host))
warnings.warn(_("{service} does not support {param} on {resource}").format(...), stacklevel=2)
```

- Do not pass f-strings directly (the msgid must be a literal; use `_("...").format(...)`)
- `tests/test_i18n_lint.py` enforces this across all modules under `src/gfo/` by AST inspection,
  and also checks that every `_()` msgid is registered in `gfo.po` (no untranslated entries slip in)
- Internal contract errors (`ValueError` etc.; see the table above) and `NotSupportedError` /
  `UnsupportedServiceError` (which take identifiers and embed them in internally i18n-ed templates) are exempt

## Configuration and authentication rules

Applies to `src/gfo/config.py`, `src/gfo/auth.py`, `src/gfo/detect.py`, `tests/test_config.py`, `tests/test_auth.py`.

### Host name normalization (required)

**Normalize every host name with `lower()`.**
- `auth.py`: `resolve_token` / `save_token`
- `detect.py`: `get_known_service_type` / `_KNOWN_HOSTS`
- `config.py`: `get_host_config` / `get_hosts_config`

Past bug: token resolution failed because `GitHub.com` ≠ `github.com`

### Saving configuration values

- **Run `git_config_set` even for an empty string** (do not skip it with `if value:`)
- Past bug: `save_project_config` skipped owner/repo when they were empty strings

### Configuration resolution priority

1. `git config --local` (per repository)
2. `~/.config/gfo/config.toml` (global)
3. Automatic detection from the remote URL

By default (`require_repo=True`), `resolve_project_config()` raises `ConfigError` (with a
hint suggesting `gfo init`) when `owner`/`repo` are empty strings, just as it does for
`service_type`/`host`. When there is no remote and no `gfo.owner`/`gfo.repo`, such as in a
bare repository, `detect_service()` is contracted to return a `DetectResult` with
`owner=""`/`repo=""`.

`resolve_project_config()`/`get_adapter()`/`get_adapter_with_config()` are also called by
account- and host-level commands that never reference owner/repo (`org`, `user`,
`notification`, `ssh-key`, `gpg-key`, `api`). These pass `require_repo=False` explicitly and
do not raise `ConfigError` even when owner/repo are unresolved. When adding a new command,
decide by whether the adapter methods it implements actually reference
`self._owner`/`self._repo` (commands such as `auth login` do not call
`resolve_project_config()` at all and are out of scope).

Past bug (#150): the empty-string fallback above was returned as is as a `ProjectConfig`,
and API requests were actually sent to invalid paths such as `/repos//`

### Token resolution priority

1. **Account name resolution** (use the first value found, from top to bottom):
   1. `--account` global option (via ContextVar `cli_account`)
   2. `gfo.account` in `.git/config`
   3. `hosts.{host}.account` in `config.toml`
   4. `tokens.{host}._default` in `credentials.toml`
   5. Fallback: `"default"`
2. `tokens.{host}.{account}` in `credentials.toml`
3. Service-specific environment variable (e.g. `GITHUB_TOKEN`)
4. `GFO_TOKEN` (generic fallback)

### Platform-specific paths

| Platform | Configuration directory |
|---|---|
| Linux / macOS | `~/.config/gfo/` |
| Windows | `%APPDATA%/gfo/` |

On Windows, `icacls` grants full control (`:F`) to the current user only (best effort).

### `--jq` empty string check

- Check with `if jq_expr is not None:`, not `if jq_expr:`
- Fail early when an empty string `""` is passed
- Past bug: with `if jq_expr:`, an empty string was falsy and slipped through

### Avoiding argparse `dest` collisions

- When a name collides with a Python built-in (`all`, `type`, etc.), change it to something like `dest="mark_all"`
- Past bug: `--all` became `args.all`, which was easy to confuse with the built-in `all()`

### Impact of changing the authentication method

It affects four places: `auth.py`, `registry.py`, test files, and documentation.

### `--remote` global option

- `cli.main()` sets the value in a `contextvars.ContextVar` (`cli_remote`)
- `detect_service()` / `resolve_project_config()` read the ContextVar
- When specified → skip the git config shortcut (`gfo.type`/`gfo.host`)
- Call `get_remote_url(remote=...)` to use the specified remote's URL
- `dest` is `global_remote` (to avoid colliding with `init --host`)

### `--repo` global option

- `cli.main()` sets the value in a `contextvars.ContextVar` (`cli_repo`)
- Mutually exclusive with `--remote` (`ConfigError` when both are specified)
- `_parse_repo_option()` in `detect_service()` parses the value
- Accepted formats: HTTPS URL, SSH URL, SCP-style, `HOST/OWNER/REPO`
- Parsing strategy: `detect_from_url(value)` → on failure, `detect_from_url(f"https://{value}")` → `ConfigError` if both fail
- When specified → skip the git config shortcut and detect the service automatically from the URL
- `dest` is `global_repo`

### Remote resolution fallback

- Default remote resolution order for `get_remote_url()` / `get_default_branch()`: origin → first non-origin remote
- On fallback, notify with `warnings.warn()` (`get_remote_url` only)
- No fallback when `remote=` is passed explicitly
