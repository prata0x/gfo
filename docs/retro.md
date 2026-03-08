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
