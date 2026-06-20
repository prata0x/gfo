# Security audit (Claude + Copilot) — 2026-06-20

## Scope
- Target paths: `src/gfo/` (focus: `http.py`, `auth.py`, `config.py`, `detect.py`, `git_util.py`, `output.py`, `adapter/*`, `commands/api.py`, `commands/batch.py`, `commands/release.py`), `.github/workflows/*.yml`, `.github/dependabot.yml`, `uv.lock`, `pyproject.toml`
- Sources run: claude (sub-agent, Sonnet), copilot
- Source status: both completed
- CLAUDE.md considered: `./CLAUDE.md` (informational only)

## High-confidence findings

### [high] [claude] A · src/gfo/commands/release.py:176 — Path traversal in `--pattern` asset download (confidence: 80)
The `--pattern` download loop builds the output path as `os.path.join(output_dir, a.name)` using the asset name taken verbatim from the forge API response (`_to_release_asset` → `data["name"]`), with **no** `os.path.basename()` or `Path.resolve().is_relative_to()` guard. The single-asset `--asset-id` path (e.g. `github.py:~634`, `gitea.py`, `gitlab.py`) *does* sanitize, so this is an inconsistency in the shared pattern path. A malicious or compromised forge server returning an asset name like `../../<path>` or an absolute path causes a write outside `output_dir` (arbitrary file overwrite). Threat model is realistic for a tool that connects to arbitrary self-hosted forges. Verified directly in source.

## Below-threshold (recorded, not surfaced as confirmed) — disagreements worth noting

These scored < 80 and are NOT confirmed findings, but are logged because they represent cross-source disagreements, which are the main value of the dual review:

- **[copilot only] B · src/gfo/http.py:198 — Backlog apiKey leak on cross-origin 3xx redirect (score 30, dropped).** Copilot's headline finding. Orchestrator verified it as a **false positive**: the main `request()` path passes the apiKey via `params=`, and `requests` does not re-apply the `params=` dict to a redirect target — it follows the `Location` URL as-is and strips `Authorization` on cross-origin hops. A query-param credential is only forwarded if a server that already holds it echoes it into `Location`, which is not a novel leak. Claude did not flag this.
- **[claude only] E · src/gfo/http.py:72 — `objects.githubusercontent.com` (asset CDN) absent from the TLS-forced host set (score 45, dropped).** With `GFO_INSECURE=1`, cross-origin asset *content* downloads from the GitHub CDN have TLS verification disabled (integrity risk under an active network attacker; credentials are not leaked because cross-origin auth is stripped). Defense-in-depth gap gated behind an explicit opt-in env var; Copilot did not flag it.
- **[claude only] B · src/gfo/http.py:444 — apiKey forwarded to same-origin pagination URLs (score 5, dropped).** Same-origin is validated before `get_absolute()` is called, so expected behavior.
- **[claude only] E · src/gfo/http.py:107 — warning text "*.backlog.com/jp" wording (score 0, dropped).** Cosmetic/docs only; enforcement uses the correct two suffixes.

## Raw output
none — both sources returned valid structured JSON.

## Summary
- Findings before filter: 5 (claude 4, copilot 1)
- After filter (< 80 dropped): 1
- Cross-source agreements (`both`): 0 (no line-specific overlap; the two Backlog-apiKey items were at different lines and different mechanisms)
- Raw sources: none
- Failed sources: none

## Verified-secure (spot checks)
- Subprocess calls (`jq` in output.py, `git` in git_util.py, `icacls` in auth.py) use list form with `shell=False` → no command injection.
- POSIX credential file written `0o600`.
- `commands/api.py` validates headers for CRLF/NUL.
- CI workflows: actions SHA-pinned (with self-check step), `permissions: contents: read`, `persist-credentials: false`, no `pull_request_target`; CodeQL + dependency-review present.
- No `eval`/`exec`/`pickle`/`yaml.load`; no hardcoded secrets.
