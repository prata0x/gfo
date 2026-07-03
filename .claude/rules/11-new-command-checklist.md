---
paths:
  - "src/gfo/cli.py"
  - "src/gfo/commands/**"
  - "tests/test_cli.py"
---

# 新規サブコマンド追加チェックリスト

`src/gfo/cli.py` は登録とディスパッチが離れた場所にあり、`tests/test_cli.py` にも
決め打ちの期待値がある。新規サブコマンド（または既存コマンドへの新規サブアクション）
を追加する際は、最低でも以下 4 箇所を同じ PR で変更すること。

1. **`create_parser()`（`cli.py` 冒頭〜）**: argparse への `add_parser` / `add_argument` 登録
2. **`_DISPATCH`（`cli.py` 末尾付近の `_DISPATCH: dict[...] = {...}`）**: `(command, subcommand)` タプルをキーにハンドラを登録
3. **`commands/*.py`**: ハンドラ本体の実装
4. **`tests/test_cli.py`**:
   - `assert len(_DISPATCH) == N` の件数リテラルを更新
   - `test_dispatch_table_all_keys()` の `expected_keys` に新規キーを追加

(1) と (2) は対応関係にあるが定義位置が離れているため、片方だけ更新すると
`argparse` はコマンドを受け付けるのに `_DISPATCH` に無くエラーになる、または
逆に到達不能なハンドラが残る、という不整合が起きる。(4) を見落とすと CI が
件数不一致・キー不足で fail する。

コマンドの引数体系や出力形式に変更がある場合は、`docs/commands.md`（英語）/
`docs/commands.ja.md`（日本語）も同じ PR で更新する（CLAUDE.md 参照）。
