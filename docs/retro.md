# 振り返り (Retrospective)

タスクごとの振り返りを蓄積するファイル。

---

## T-01: パッケージ構造・プロジェクト設定

### 発生した問題

1. **hatchling の build-backend パス誤り**
   - `build-backend = "hatchling.backends"` と書いたが正しくは `"hatchling.build"`
   - `pip install -e ".[dev]"` が `BackendUnavailable: Cannot import 'hatchling.backends'` で失敗
   - 教訓: hatchling の正しいエントリポイントは `hatchling.build`

2. **`__pycache__` をコミットに含めてしまった**
   - `.gitignore` を作成せずにコミットしたため `src/gfo/__pycache__/*.pyc` がトラッキング対象に
   - 追加コミットで `.gitignore` 作成 + `git rm -r --cached` で除外
   - 教訓: プロジェクト初期セットアップでは `.gitignore` をファイル作成と同時に用意する

### うまくいった点

- `src/` レイアウト + hatchling の組み合わせは問題なく動作
- `__main__.py` に暫定バージョン表示を入れる方針で `python -m gfo --version` 検証をクリア

---

## T-02: exceptions.py — 全エラー型の定義

### 発生した問題

- 特になし

### うまくいった点

- design.md に完全なコードが記載されていたため、そのまま移植するだけで実装が完了した
- テスト 28 件が全パスし、スムーズに完了

---

## T-03: git_util.py — git コマンドラッパー関数

### 発生した問題

- 特になし

### うまくいった点

- プランが明確で実装・テスト共にスムーズに完了（18テスト全パス）

---

## T-04: http.py — HttpClient + ページネーション関数

### 発生した問題

1. **`paginate_link_header` の重複リクエストバグ**
   - 初回実装時に分岐ロジックが重複し、同じリクエストが2回発行されるコードになっていた
   - 変数名を `next_url` に統一し、分岐を整理して解消

2. **`responses` ライブラリの URL マッチング**
   - `responses.add()` でクエリパラメータ付きURLを登録しても、ベースURLの部分一致で先に登録したモックがマッチし続ける問題
   - `query_param_matcher` でも解決せず、最終的にコールバックベース (`add_callback`) でリクエスト回数に基づく分岐に変更して解決
   - 教訓: `responses` ライブラリでページネーションのマルチページテストを書く際は `add_callback` が確実

### うまくいった点

- design.md の仕様が詳細で、HttpClient の構造・ページネーション関数のシグネチャをそのまま実装できた
- 43テスト全パス、既存テスト (89件) にも影響なし

---

## T-05: detect.py — サービス自動検出

### 発生した問題

1. **`import gfo.config` による `gfo` 名前空間の衝突**
   - `detect_service()` 内で `import gfo.config` を関数内 import したところ、モジュールレベルの `import gfo.git_util` と衝突し `UnboundLocalError` が発生
   - Python は関数内に `import gfo.config` があると `gfo` をローカル変数と見なし、それ以前の `gfo.git_util` 参照が失敗する
   - 解決: `import gfo.git_util` → `from gfo.git_util import get_remote_url, git_config_get` に変更
   - 教訓: 関数内 import でパッケージ名を使う場合、同じパッケージ名のモジュールレベル import との衝突に注意

2. **`_AZURE_PATH_RE` のオプショナルグループによる誤マッチ**
   - design.md の正規表現 `(?:_git/)?` がオプショナルだったため、`project/_git/repo` が `org=project, project=_git, repo=repo` と誤パースされた
   - 解決: `_AZURE_GIT_PATH_RE` (`_git/` 必須) と `_AZURE_V3_PATH_RE` (`v3/` プレフィックス) の2つに分離
   - さらに `*.visualstudio.com` では path に org がないため `(?:(?P<org>[^/]+)/)?` でオプショナル化
   - 教訓: design.md の正規表現をそのまま使う前に、各パターンの実際の URL でマッチ結果を検証すべき

### うまくいった点

- URL パース 18件 + API プローブ 8件 + 統合フロー 5件 = 31テスト全パス、既存テスト (89件) にも影響なし
- Backlog SSH 特殊処理 (ホスト名正規化 + path lstrip) がプラン通りに動作

---

## T-06: config.py — 3層設定解決 + TOML読み込み

### 発生した問題

1. **Windows で環境変数全クリア時に `Path.home()` が失敗するテスト問題**
   - テストで `monkeypatch.delenv()` を使い環境変数を全クリアすると、Windows 環境では `Path.home()` が `USERPROFILE` / `HOMEDRIVE`+`HOMEPATH` を参照できず `RuntimeError` になる
   - テスト側で必要な環境変数を保持するよう調整して解決

### うまくいった点

- design.md の仕様が明確で、3層設定解決 (デフォルト → TOML → 環境変数) の実装がスムーズに進んだ
- 32テスト全パス、既存テスト (120件) にも影響なし

---

## T-07: auth.py — トークン解決 + credentials.toml 管理

### 発生した問題

1. **`get_auth_status()` の型アノテーションバグ**
   - `result: list[dict[str, str]] = {}` と dict リテラルで初期化してしまった
   - 正しくは `= []`。実装直後に気づいて即修正

2. **Windows での `os.chmod` テスト失敗**
   - `sys.platform` を `"linux"` に mock して POSIX パーミッションテストを書いたが、Windows では `os.chmod(path, 0o600)` が実際には POSIX パーミッションを設定しない
   - 解決: `os.chmod` 自体を mock し、引数 `0o600` で呼ばれたことを検証する方式に変更

### うまくいった点

- design.md の仕様が明確で、4段フォールバック (`credentials.toml` → サービス別環境変数 → `GFO_TOKEN` → `AuthError`) の実装がスムーズ
- T-06 の retro で学んだ「Windows 環境変数全クリアで `Path.home()` が失敗する」問題を回避できた（`monkeypatch.delenv` で必要変数のみ操作）
- 16テスト全パス、既存152テストにも影響なし（計168テスト）

---

## T-08: adapter/base.py — データクラス

### 発生した問題

- 特になし

### うまくいった点

- design.md に完全なコード定義があり、6つの frozen dataclass をそのまま実装するだけで完了
- 15テスト全パス、既存テストにも影響なし

---

## T-09: adapter/base.py — ABC 定義

### 発生した問題

- 特になし

### うまくいった点

- design.md L1043-1170 に ABC の完全な定義があり、そのまま移植するだけで完了
- 抽象メソッド18個 + 具象メソッド `get_pr_checkout_refspec` のデフォルト実装を追加
- 4テスト全パス、既存テストにも影響なし

---

## T-10: adapter/registry.py + output.py

### 発生した問題

- 特になし

### うまくいった点

- design.md の擬似コードがほぼそのまま実装に使えた
- output.py: table/json/plain の3フォーマッタ + output 関数を実装。dataclasses.asdict/fields を活用しシンプルに
- registry.py: register デコレータ + get_adapter_class + create_adapter ファクトリを実装。9サービスの認証方式を網羅
- 29テスト全パス、既存テストにも影響なし
