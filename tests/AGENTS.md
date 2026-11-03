# Testing conventions

Applies to `tests/**`.

## HTTP mocks

```python
@responses.activate
def test_something(adapter):
    responses.add(responses.GET, "https://api.example.com/...", json={...})
    result = adapter.some_method()
    assert result.field == "value"
```

- `@responses.activate` defaults to `assert_all_requests_are_fired=False`
  - The `mock_responses` fixture (`responses.RequestsMock()`) in `tests/test_adapters/conftest.py`
    defaults to `True`. Tests using this fixture fail if a registered mock is not called
  - With either approach, do not register unnecessary mocks

## Test file locations

| Test type | Location |
|---|---|
| Adapter tests | `tests/test_adapters/test_{service}.py` |
| Command tests | `tests/test_commands/test_{command}.py` |

## Command tests

- Create command argument objects with `make_args()` in `tests/test_commands/conftest.py`

## Adapter fixtures

- `tests/test_adapters/conftest.py` defines a `client` + `adapter` pair for every service

## Command tests: `patch_adapter`

- Use the shared helper `patch_adapter(module_path)` in `tests/test_commands/conftest.py`
- Do not define a duplicate custom `_patch` helper in each file

## Required test patterns

- **`fmt="json"` test**: at least one required for each command
- **Error propagation test**: verify propagation when the adapter raises `HttpError`
- **Adapter test minimum requirements**: 404/403 error tests + empty list `[]` test

## Integration tests

- **`safe_temporary_directory()`**: use the helper in `tests/integration/conftest.py` (do not use `TemporaryDirectory` directly)
  - Reason: Windows file-lock workaround + Python 3.11 compatibility (`ignore_cleanup_errors` not supported)
- **API propagation lag**: insert `time.sleep(3)` before a get/list that immediately follows a set/delete
  - Workaround for propagation delays confirmed on GitHub/Bitbucket
- **Private API dependencies**: keep them to a minimum, with TODO comments
- **Suppressing GCM during git operations**: when running `git clone`/`git push` etc. with `subprocess.run`, set the environment variables `GCM_INTERACTIVE=never` and `GIT_TERMINAL_PROMPT=0`
  - Reason: on Windows, Git Credential Manager (GCM) steps in before `GIT_ASKPASS` and opens an authentication page in the browser
