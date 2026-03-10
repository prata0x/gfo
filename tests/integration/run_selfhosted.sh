#!/usr/bin/env bash
# セルフホスト統合テストの実行
# Docker Compose で Gitea / Forgejo / Gogs / GitBucket を起動し、
# 初期セットアップ後にテストを実行する。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

cleanup() {
    echo ""
    echo "=== クリーンアップ ==="
    docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
}

# 正常終了・異常終了・Ctrl+C・SIGTERM すべてでクリーンアップ
trap cleanup EXIT INT TERM

echo "=== Docker Compose 起動 ==="
docker compose -f "$COMPOSE_FILE" up -d

echo ""
echo "=== ヘルスチェック待機 ==="
echo "  各サービスの起動を待っています..."

# 各サービスが healthy になるまで待機
for service in gitea forgejo gogs gitbucket; do
    echo -n "  $service: "
    timeout=120
    elapsed=0
    while [ $elapsed -lt $timeout ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "gfo-$service" 2>/dev/null || echo "unknown")
        if [ "$status" = "healthy" ]; then
            echo "ready"
            break
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done
    if [ $elapsed -ge $timeout ]; then
        echo "TIMEOUT"
        echo "  Warning: $service did not become healthy within ${timeout}s"
    fi
done

echo ""
echo "=== 初期セットアップ ==="
python "$SCRIPT_DIR/setup_services.py"

echo ""
echo "=== 統合テスト実行 ==="
cd "$SCRIPT_DIR/../.."
python -m pytest tests/integration/ -m selfhosted -v --tb=short --no-cov

echo ""
echo "=== テスト完了 ==="
