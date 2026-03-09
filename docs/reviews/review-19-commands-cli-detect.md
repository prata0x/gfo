# gfo Review Report — Round 19: commands / cli / detect / tests 網羅確認

## 概要
- レビュー日: 2026-03-09
- 対象: `commands/milestone.py`, `commands/label.py`, `commands/repo.py`, `cli.py`, `adapter/base.py`, `tests/test_cli.py`, `tests/test_output.py`, `tests/test_detect.py`, `detect.py`
- 発見事項: 重大 1 / 中 2 / 軽微 3（OK 確認 4 件含む）

---

## 既知残課題の現状確認

| ID | 状態 |
|----|------|
| R16-02 | `auth.py` L140: `"host": f"env:{service_type}"` 形式のまま — **継続中** |
| R18-05 | `test_azure_devops.py`: PR URL フォールバックテスト欠落 — **継続中** |

---

## 修正済み・問題なし確認（OK）

| 項目 | 確認内容 |
|------|---------|
| `milestone.py` | list/create ハンドラ完全実装。title 空文字検証あり。テスト完備。 |
| `label.py` 色検証 | `re.fullmatch(r"[0-9a-fA-F]{6}", color)` で厳密検証実装済み。 |
| `repo.py` getattr 使用 | L73, L91 両方 `getattr(args, "host", None)` で一貫性あり。 |
| `cli.py` DISPATCH | 23 エントリ完全。全サブコマンド網羅済み。 |
| `detect.py` | URL パース、4 段階検出フロー、HTTP/HTTPS scheme 判別まで完全実装。 |

---

## 新規発見事項

---

### [R19-01] 🔴 `commands/repo.py` L80 — `adapter_cls(client, "", "")` に空 owner/repo を渡す安全性

- **ファイル**: `src/gfo/commands/repo.py` L80
- **現在のコード**:
  ```python
  adapter = adapter_cls(client, "", "")  # owner=="" repo==""
  ```
- **説明**: `handle_create` でリポジトリ作成前のアダプター生成時に owner/repo を空文字で渡している。`create_repository()` はこの値を使用しないため現状は問題ないが、コードを読んだだけでは意図が不明瞭で、将来このコードが別用途に転用された場合に空 owner/repo が API 呼び出しに混入するリスクがある。
- **影響**: 現在は実害なし。ただし意図がコメントなしでは把握できない。
- **推奨修正**: インラインコメントを追加して意図を明示。
  ```python
  # create_repository は owner/repo を使用しないため空文字を渡す
  adapter = adapter_cls(client, "", "")
  ```

---

### [R19-02] 🟡 `commands/label.py` L20 — `name` の空文字検証なし

- **ファイル**: `src/gfo/commands/label.py` L20
- **現在のコード**:
  ```python
  def handle_create(args: argparse.Namespace, *, fmt: str) -> None:
      color = args.color
      if color is not None:
          color = color.lstrip("#")
          if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
              raise ConfigError(...)
      adapter = get_adapter()
      label = adapter.create_label(name=args.name, ...)
  ```
- **説明**: `args.name` が空文字列の場合の検証がない。`commands/milestone.py` L21 では `if not args.title.strip():` で同等の検証が実装されており、一貫性を欠く。
- **推奨修正**:
  ```python
  if not args.name.strip():
      raise ConfigError("name must not be empty.")
  ```

---

### [R19-03] 🟡 `adapter/base.py` L185 — `GitServiceAdapter.__init__` の `**kwargs` にドキュメントなし

- **ファイル**: `src/gfo/adapter/base.py` L185
- **現在のコード**:
  ```python
  def __init__(self, client, owner: str, repo: str, **kwargs):
      self._client = client
      self._owner = owner
      self._repo = repo
  ```
- **説明**: `**kwargs` を受け取るが何もしない。サブクラス（`BacklogAdapter`, `AzureDevOpsAdapter`）では `project_key`, `organization` 等を引数として渡しており、それらを基底クラスで受け取るための設計。ただし意図がコメントなしでは不明。
- **影響**: 軽微。動作上の問題はない。
- **推奨修正**: 簡単なコメントで意図を明示。
  ```python
  def __init__(self, client, owner: str, repo: str, **kwargs):
      # **kwargs はサービス固有パラメータ（BacklogAdapter の project_key 等）を
      # サブクラスが super().__init__() 経由で渡す際に吸収するためのもの。
      self._client = client
  ```

---

### [R19-04] 🟢 `tests/test_azure_devops.py` — PR URL フォールバックテスト欠落（R18-05 継続）

- **ファイル**: `tests/test_adapters/test_azure_devops.py`
- **説明**: R12-03 修正で `repository.webUrl` が存在しない場合に `data.get("url", "")` を返すフォールバックを実装済みだが、このフォールバックパスのテストが存在しない。
- **推奨修正**: フォールバック時の `_to_pull_request` テストを追加。
  ```python
  def test_url_fallback_when_no_web_url(self):
      data = _pull_request_data(1)
      data["repository"] = {}  # webUrl を省略
      pr = AzureDevOpsAdapter._to_pull_request(data)
      assert pr.url == data["url"]
  ```

---

### [R19-05] 🟢 `commands/label.py` vs `commands/milestone.py` — 入力検証の一貫性（R19-02 補足）

- **ファイル**: `src/gfo/commands/label.py`, `src/gfo/commands/milestone.py`
- **説明**: `milestone.py` L21 は `title` の空文字検証あり。`label.py` は `name` の検証なし。同パターンのコマンドで検証が統一されていない。R19-02 の修正で対応済みとなる。

---

## 全問題サマリー（R19）

| ID | 重大度 | ファイル | 概要 |
|----|--------|---------|------|
| **R19-01** | 🔴 重大（将来リスク） | `commands/repo.py` L80 | `adapter_cls(client, "", "")` の意図未明示 |
| **R19-02** | 🟡 中 | `commands/label.py` L20 | `name` 空文字検証なし（milestone.py と不統一） |
| **R19-03** | 🟡 中 | `adapter/base.py` L185 | `**kwargs` の意図がコメントなしで不明 |
| R16-02 | 🟡 中 | `auth.py` L140 | host 形式混在（継続） |
| **R19-04** | 🟢 軽微 | `test_azure_devops.py` | PR URL フォールバックテスト欠落（R18-05 継続） |
| **R19-05** | 🟢 軽微 | `label.py` vs `milestone.py` | 入力検証の一貫性（R19-02 で対応） |

---

## 推奨アクション（優先度順）

1. **[R19-02]** `commands/label.py` L20 — `name` 空文字検証を追加（1行）
2. **[R19-01]** `commands/repo.py` L80 — インラインコメントを追加（1行）
3. **[R19-03]** `adapter/base.py` L185 — `**kwargs` コメント追加（2行）
4. **[R19-04/R18-05]** `test_azure_devops.py` — PR URL フォールバックテスト追加
