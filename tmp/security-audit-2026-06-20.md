# Security audit — 2026-06-20

## Scope
- Target paths: `src/gfo/` (http.py, auth.py, config.py, detect.py, git_util.py, output.py, adapter/*, commands/*), `.github/workflows/*.yml`, `.github/dependabot.yml`, `.gitignore`, `uv.lock`, `pyproject.toml`
- Axes run: A B C D E F G H (8/8)
- Sub-agent status: 8/8 completed (0 raw, 0 failed)
- CLAUDE.md considered: `./CLAUDE.md` (informational only)

## High-confidence findings (score ≥ 80)

### [low→medium] E · src/gfo/http.py:393-394 — `upload_file_absolute` sends session auth + uses init-time TLS verify on a caller-supplied absolute URL (confidence: 85, cross_axis: yes — B+E)
`upload_file_absolute` issues `self._session.post(url, ...)` against a caller-supplied absolute URL, (a) merging `_auth_params` and the session's auth header without a same-origin check, and (b) using `session.verify` (fixed from `base_url` at construction) instead of the per-URL `_verify_for_url`. The streaming read path (`request_stream`) already does both correctly. Real impact requires `GFO_INSECURE=1` on a self-hosted base while uploading to a cloud endpoint (e.g. `uploads.github.com`): the upload then proceeds with TLS verification disabled for a cloud host. The only current caller passes a GitHub-derived `uploads.github.com` URL, so this is a defense-in-depth gap, not an active credential leak — but it diverges from the hardened read path. Independently flagged by axis B (auth) and axis E (TLS).

## Notable findings just below threshold (score 75 — recorded for transparency)

The strict < 80 filter drops these, but they are genuine and several were independently corroborated (the path-traversal item scored 80 in the parallel `/copilot-security-audit` run on the same date and is verified in source). Surfaced deliberately rather than buried:

- **[high] A · src/gfo/commands/release.py:176 (75)** — Path traversal in `--pattern` asset download. `os.path.join(output_dir, a.name)` uses the server-supplied asset name with no `basename`/`is_relative_to` guard, unlike the `--asset-id` path. A malicious/compromised forge returning `../../…` or an absolute name writes outside `output_dir`. **Verified in source. This is the strongest real defect in the audit** (it landed at 80 / kept in the parallel Copilot audit; score variance straddles the threshold).
- **[high] B · src/gfo/adapter/azure_devops.py:1623 (75)** — `search_code` calls `_session.post()` to `almsearch.dev.azure.com` (cross-origin from `dev.azure.com`), sending the Basic PAT without going through the central same-origin guard. Mitigating: the destination is a hardcoded, legitimate first-party Microsoft host, so the PAT is not exposed to an attacker — the issue is bypassing the central guard, not a leak to an untrusted party.
- **[medium] B/E · src/gfo/http.py:88 & :94 (75 each)** — Trailing-dot hostname bypass. `urlparse('https://github.com./').hostname` → `github.com.`, which matches neither `_CLOUD_HOSTS_TLS_FORCED` nor the suffix set, so `GFO_INSECURE=1` disables TLS for a cloud host written in FQDN-trailing-dot form. Flagged independently by axis B (line 94, `_verify_for_url`) and axis E (line 88, `_is_cloud_host_tls_forced`) — same root cause, but 6 lines apart so outside the ±3 cross-axis window (no auto-bonus). Fix: strip trailing dot before the set/suffix check.
- **[low→medium] C · src/gfo/.gitignore:20 (75)** — Only `tests/integration/.env` is git-ignored. A project-root `.env` holding tokens (common with dotenv tooling) is not ignored — accidental-commit risk in a public repo. Recommend a root `.env` / `.env*` pattern.
- **[medium] H · src/gfo/adapter/gitlab.py:2480 (75)** — `create_push_mirror` accepts `auth_token` but never adds it to the `/remote_mirrors` payload (silently discarded); other adapters wire it as `remote_password`. Functional/auth defect from a copy-paste of the signature without the wiring — the mirror credential is dropped.

## Other lower-confidence items (score < 75, not surfaced as findings)
- C · http.py:166 (50) — `NetworkError` chains the original requests exception as `__cause__`, which holds the unmasked URL (Backlog apiKey in query) even though the `NetworkError` message is masked; leaks only if a traceback walking `__cause__` is printed.
- D · dependabot.yml:43 (50) — github-actions block lacks the 7-day `cooldown` the uv block has (actions are SHA-pinned, mitigating).
- B · http.py:444 (35, +cross) / http.py:393 auth-angle — `get_absolute` / `upload_file_absolute` auth-on-absolute-URL with no current cross-origin caller.
- D · pyproject.toml:7 (25) — `requests` unbounded (pinned in uv.lock).
- F · http.py:315 (25) — partial download file not unlinked on network/HTTP error (no secret written).
- H · gitlab.py:616 (30) — inline token masking instead of the shared `_mask_token_in_exception` helper (maintainability).
- G · dependency-review.yml:17 (10), codeql.yml:22 (10) — jobs missing `timeout-minutes` (resource hygiene, not security).

## Raw axis output
none — all 8 axes returned valid structured JSON.

## Summary
- Findings before filter: 16
- After filter (< 80 dropped): 1
- Cross-axis agreements: 1 (`http.py:393/394`, axes B+E; the trailing-dot pair at :88/:94 is the same defect but fell outside the ±3 window)
- Raw axes: none
- Failed axes: none

## Verified-secure (spot checks)
- Subprocess (`jq`, `git`, `icacls`) use list form, `shell=False` — no command injection.
- POSIX credential file `0o600`; `_mask_api_key` applied on surfaced error messages.
- `requests` 2.34.2 pinned with hashes in uv.lock; no eval/exec/pickle/yaml.load; no hardcoded secrets.
- CI: all `uses:` SHA-pinned (with self-check step), `permissions: contents: read`, `persist-credentials: false`, no `pull_request_target`; CodeQL + dependency-review present; no secrets echoed; cache keys hash-scoped + `uv sync --locked`.
