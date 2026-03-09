# gfo Review Report — Round 36: adapter/base / github / gitlab 精査

## 概要

- **レビュー日**: 2026-03-09
- **対象**:
  - `src/gfo/adapter/base.py`
  - `src/gfo/adapter/github.py`
  - `src/gfo/adapter/gitlab.py`
  - `src/gfo/adapter/gitea.py`（参照比較のみ）
  - `tests/test_github.py`（テスト追加対象）

- **発見事項**: 新規 3 件（重大 0 / 中 2 / 軽微 1）

---

## エージェントレビューで誤報された項目（問題なし確認）

| 確認項目 | 結果 |
|---------|------|
| `gitlab.py` `create_release` で `draft` が payload に未追加 | OK — GitLab Releases API は `draft` をサポートしていない（`upcoming_release` のみ）。GitHub API の `draft` と異なりサーバー側で無視されるため、意図的な省略 |
| `gitlab.py` `list_labels(*, limit: int = 0)` が base の抽象メソッドと不一致 | OK — Python ではデフォルト付きキーワード引数の追加は Liskov Substitution Principle に違反しない。基底クラスのシグネチャで呼び出す場合も正常動作する |

---

## 新規発見事項

---

### [R36-01] 🟡 `github.py` L155/L171 — `list_labels()`/`list_milestones()` が最大 30 件しか返さない

- **ファイル**: `src/gfo/adapter/github.py` L155-157, L171-173
- **現在のコード**:
  ```python
  def list_labels(self) -> list[Label]:
      results = paginate_link_header(self._client, f"{self._repos_path()}/labels")
      return [self._to_label(r) for r in results]

  def list_milestones(self) -> list[Milestone]:
      results = paginate_link_header(self._client, f"{self._repos_path()}/milestones")
      return [self._to_milestone(r) for r in results]
  ```
- **説明**: `paginate_link_header` のデフォルトは `limit=30`。ラベル/マイルストーンが 30 件を超えるリポジトリでは全件取得できない。一方 `gitea.py` では `limit=0`（全件）、`gitlab.py` では `limit=0` がデフォルトで設定されており、アダプター間で挙動が一致しない。基底クラス `GitServiceAdapter.list_labels(self)` / `list_milestones(self)` にも `limit` 引数がないため、拡張の余地がなく修正には base も変更が必要。
- **推奨修正**:
  ```python
  # base.py
  @abstractmethod
  def list_labels(self, *, limit: int = 0) -> list[Label]: ...

  @abstractmethod
  def list_milestones(self, *, limit: int = 0) -> list[Milestone]: ...

  # github.py
  def list_labels(self, *, limit: int = 0) -> list[Label]:
      results = paginate_link_header(self._client, f"{self._repos_path()}/labels", limit=limit)
      return [self._to_label(r) for r in results]

  def list_milestones(self, *, limit: int = 0) -> list[Milestone]:
      results = paginate_link_header(self._client, f"{self._repos_path()}/milestones", limit=limit)
      return [self._to_milestone(r) for r in results]
  ```

---

### [R36-02] 🟡 `base.py` L21 — `PullRequest.updated_at` に default 値なし（`Issue` との非対称）

- **ファイル**: `src/gfo/adapter/base.py` L21, L35
- **現在のコード**:
  ```python
  @dataclass(frozen=True, slots=True)
  class PullRequest:
      ...
      updated_at: str | None      # デフォルトなし

  @dataclass(frozen=True, slots=True)
  class Issue:
      ...
      updated_at: str | None = None  # デフォルトあり
  ```
- **説明**: `Issue.updated_at` は `= None` がデフォルトとして設定されているが、`PullRequest.updated_at` には設定されていない。実際の `_to_pull_request` では `updated_at=data.get("updated_at")` と明示的に渡すため実行時エラーにはならないが、テストや将来の利用コードで `PullRequest` を直接インスタンス化する際に `updated_at` を省略できず不便。`Issue` と同様の設計に揃えるべき。
- **推奨修正**:
  ```python
  @dataclass(frozen=True, slots=True)
  class PullRequest:
      ...
      updated_at: str | None = None
  ```

---

### [R36-03] 🟢 テスト — R36-01〜02 の修正確認テストなし

- **ファイル**: `tests/test_github.py`
- **説明**:
  - R36-01: `list_labels()` が 30 件超のラベルを全件取得することのテスト
  - R36-01: `list_milestones()` が 30 件超のマイルストーンを全件取得することのテスト
  - R36-02: `PullRequest` を `updated_at` なしでインスタンス化できることのテスト
- **推奨修正**: R36-01〜02 修正後に対応テストを追加する。

---

## 全問題サマリー（R36）

| ID | 重大度 | ファイル | 概要 | 状態 |
|----|--------|---------|------|------|
| **R36-01** | 🟡 中 | `github.py` L155/L171 | `list_labels()`/`list_milestones()` が最大 30 件 | ✅ 修正済み |
| **R36-02** | 🟡 中 | `base.py` L21 | `PullRequest.updated_at` に default なし | ✅ 修正済み |
| **R36-03** | 🟢 軽微 | テスト各種 | R36-01〜02 の修正確認テストなし | ✅ 修正済み |

---

## 推奨アクション（優先度順）

1. ~~**[R36-01]**~~ ✅ 修正済み
2. ~~**[R36-02]**~~ ✅ 修正済み
3. ~~**[R36-03]**~~ ✅ 修正済み

## 修正コミット（R36）

| コミット | 修正内容 |
|---------|---------|
| （次のコミット） | R36-01〜03 — base/github list_labels/milestones limit 修正・テスト追加 |
