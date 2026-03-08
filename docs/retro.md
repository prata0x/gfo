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

### 今後のタスクへの申し送り

- pyproject.toml の requires-python は `>=3.9` だが、plan.md では Python 3.11+ と記載。tomllib は 3.11+ 標準なので、後続タスクで TOML 読み込みを実装する際に整合性を確認する必要がある
