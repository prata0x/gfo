# gfo Review Report — Round 37: Issue.updated_at 未設定の統一修正

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/base.py` (`GitHubLikeAdapter._to_issue()`)
  - `src/gfo/adapter/gitlab.py` (`GitLabAdapter._to_issue()`)
  - `src/gfo/adapter/bitbucket.py` (`BitbucketAdapter._to_issue()`)
  - `src/gfo/adapter/backlog.py` (`BacklogAdapter._to_issue()`)
  - `src/gfo/commands/init.py`、`src/gfo/commands/repo.py`（偽陽性確認）
  - `tests/test_adapter_base.py`（テスト追加対象）

- **発見事項**: 新規 2 件（重大 0 / 中 1 / 軽微 1）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `init.py` L99 — `if service_type is None:` チェックが冗長 | OK — `DetectResult.service_type` は `detect.py` L191 で `service_type=None` として返されるケースがある（未知ホストの場合）。チェックは必要 |
| `repo.py` L80 — `adapter_cls(client, "", "")` が空文字で adapter 生成 | OK — `create_repository()` は `_owner`/`_repo` を使わない。コメントも意図を説明済みで設計上正しい |

---

## 新規発見事項

---

### [R37-01] 🟡 複数アダプター `_to_issue()` で `updated_at` が未設定

- **ファイル**:
  - `src/gfo/adapter/base.py` L112-122（GitHubLikeAdapter — GitHub/Gitea/GitBucket/Forgejo に影響）
  - `src/gfo/adapter/gitlab.py` L59-69
  - `src/gfo/adapter/bitbucket.py` L68-78
  - `src/gfo/adapter/backlog.py` L105-115
- **説明**: 各アダプターの `_to_pull_request()` では `updated_at=data.get("updated_at")` 等で設定されているのに、同じアダプターの `_to_issue()` では `updated_at` を設定していない。`Issue.updated_at` のデフォルトは `None`（R36-02 で追加）なのでエラーにはならないが、各サービスの API が `updated_at` を返しているのにデータが失われる。テーブル/JSON 出力でも `updated_at` 列が常に空になる。

| アダプター | `_to_pull_request()` での `updated_at` キー | `_to_issue()` での状態 |
|-----------|-------------------------------|----------------------|
| GitHub/Gitea（base.py） | `data.get("updated_at")` | 未設定（L122 で終了） |
| GitLab | `data.get("updated_at")` | 未設定（L68 で終了） |
| Bitbucket | `data.get("updated_on")` | 未設定（L77 で終了） |
| Backlog | `data.get("updated")` | 未設定（L114 で終了） |
| Azure DevOps | `fields.get("System.ChangedDate")` | ✅ 設定済み |

- **推奨修正**:
  ```python
  # base.py（GitHubLikeAdapter）
  return Issue(
      ...
      created_at=data["created_at"],
      updated_at=data.get("updated_at"),  # 追加
  )

  # gitlab.py
  return Issue(
      ...
      created_at=data["created_at"],
      updated_at=data.get("updated_at"),  # 追加
  )

  # bitbucket.py
  return Issue(
      ...
      created_at=data["created_on"],
      updated_at=data.get("updated_on"),  # 追加（PR と同じキー）
  )

  # backlog.py
  return Issue(
      ...
      created_at=data.get("created", ""),
      updated_at=data.get("updated"),  # 追加（PR と同じキー）
  )
  ```

---

### [R37-02] 🟢 テスト — R37-01 の修正確認テストなし

- **ファイル**: `tests/test_adapter_base.py`
- **説明**: `GitHubLikeAdapter._to_issue()` で `updated_at` が正しく設定されることのテストが不足している。
- **推奨修正**: R37-01 修正後に `_to_issue()` が `updated_at` を設定することを確認するテストを追加する。

---

## 全問題サマリー（R37）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R37-01** | 🟡 中 | base/gitlab/bitbucket/backlog | `_to_issue()` で `updated_at` 未設定 | ✅ 修正済み |
| **R37-02** | 🟢 軽微 | `test_adapter_base.py` | R37-01 の修正確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R37-01]**~~ ✅ 修正済み
2. ~~**[R37-02]**~~ ✅ 修正済み

## 修正コミット（R37）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R37-01〜02 — 全アダプター _to_issue() に updated_at を追加・テスト追加 |
