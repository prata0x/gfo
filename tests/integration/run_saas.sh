#!/usr/bin/env bash
# SaaS 統合テストの実行
# 事前に .env ファイルに各サービスのトークンを設定しておくこと。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# .env ファイルから環境変数を読み込み
if [ -f "$ENV_FILE" ]; then
    echo "=== .env ファイルを読み込み ==="
    set -a
    # コメント行と空行を除外して読み込み
    while IFS= read -r line; do
        line=$(echo "$line" | sed 's/#.*//' | xargs)
        if [ -n "$line" ]; then
            export "$line"
        fi
    done < "$ENV_FILE"
    set +a
else
    echo "Warning: $ENV_FILE が見つかりません。"
    echo "  .env.example をコピーしてトークンを設定してください:"
    echo "  cp $SCRIPT_DIR/.env.example $ENV_FILE"
    exit 1
fi

echo ""
echo "=== SaaS 統合テスト実行 ==="
pytest tests/integration/ -m saas -v --tb=short --no-cov

echo ""
echo "=== テスト完了 ==="
