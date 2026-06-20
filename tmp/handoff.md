# Handoff — 2026-06-20

> Next session: read this file fully before acting. This file IS your first prompt.

## Status

テスト基盤整備の issue #27〜#30 を**全て完了・CLOSED**（PR #31〜#39、9 本すべて CI green・merge 済み）。テスト高速化（cov 分離 + pytest-xdist）・CI uv キャッシュ・実ロジックの穴埋め・冗長/脆弱テストの整理（#28 の全 6 カテゴリ）を実施。main は `86f80cd`、全スイート **3793 passed / カバレッジ 92%**。**現在、着手中のタスクは無い。** 残る open issue は #1（Backlog 動作確認・要実トークン）のみ。

## Decisions made this session

- #27: カバレッジは `addopts` に焼き込まず明示付与（開発ループ高速化）。CI は `-n 4 --cov`、3.13 のみ `COVERAGE_CORE=sysmon`。xdist × cov は `[tool.coverage.run] parallel/relative_files/source` が無いと CI で 0% 化するため必須。
- #28 全般: 「回帰検出力を落とさず」を厳守。削除箇所はすべて他テスト/追加ガードでカバレッジ非劣化を実測確認（github_like.py は gitea テストのみで 100%、Forgejo は新ガード `TestNoBehavioralOverrides` で override 追加を検知）。
- #28 で**意図的に残置**: schema の description 網羅・`_OUTPUT_MAP` カバレッジ・`__abstractmethods__` ガード（有用な不変条件）、full-kwargs `assert_called_once_with`（アダプタ契約の明示）、table 出力の安定 substring。これらは「契約の明示」であり弱体化させない方針。
- 共通スタブは `tests/conftest.py` の `StubAdapter` + `make_stub_adapter` に一元化（`from tests.conftest import StubAdapter` で参照）。

## Remaining tasks

- [ ] (blocked・別件) issue #1: Backlog 動作確認 — blocker: 実 Backlog API トークンが必要。

## Gotchas

- **toolchain**: WSL に `python` コマンドは無い。`mise exec -- uv run <cmd>` で実行。依存は `uv sync --locked`。
- **コミット署名必須**（ruleset）: SSH 署名設定済みで GitHub 上 Verified。ローカル `git log --show-signature` は "No signature" と誤表示するが GitHub API の `.commit.verification.verified` で確認すること。
- **push は SSH**（origin は `git@github.com:...`）。OAuth トークンは `workflow` scope が無く HTTPS では workflow ファイル push 不可（[[git-push-requires-ssh]]）。
- **マージは merge commit のみ**（squash/rebase 無効）: `gh pr merge <n> --merge --delete-branch`。`--admin` は使わない。
- **必須ステータスチェックは `ci`**（aggregate gate）。CI 名は維持すること。
- **CI 完了待ち**: `gh pr checks <n> --watch --interval 15`（`gh pr checks` に `--json` は無い）。
- **`gh issue view` の本文取得**: GraphQL deprecation warning で表示が空になることがある。`gh issue view <n> --json number,title,body` で取得すると確実。
- **public repo**: 秘密情報・private リポジトリへの言及を issue/PR/コミット/コードに出さない。

## References

- Closed issues: `#27`（高速化）, `#28`（冗長整理・全6カテゴリ）, `#29`（穴埋め）, `#30`（uv キャッシュ）。残 open: `#1`（Backlog・別件）。
- PRs（本セッション）: `#31`〜`#39`（すべて merged）。
- 主要変更: `pyproject.toml`（`[tool.coverage.run]` / `addopts`）, `.github/workflows/ci.yml`（cache + pytest 行）, `tests/conftest.py`（共通 `StubAdapter`）, `tests/test_adapters/test_forgejo.py`（`TestNoBehavioralOverrides` ガード）。
- main HEAD: `86f80cd`。
- ワークフロー規律・開発手順は CLAUDE.md に記載（auto-loaded・restate 不要）。

## Suggested first action

着手中タスクは無い。ユーザーに次の作業（新規 issue 起票 / #1 の Backlog 動作確認 / 別タスク）を確認してから動く。
