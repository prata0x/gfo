"""SaaS 統合テストで作成したテスト用リソースを削除するクリーンアップスクリプト。

Usage:
    python tests/integration/cleanup_saas.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tests.integration.conftest import create_test_adapter, get_service_config  # noqa: E402

TEST_LABEL = "gfo-test-label"
TEST_MILESTONE = "gfo-test-milestone"
TEST_RELEASE_TAG = "v0.0.1-test"


def _safe(label: str, fn, *args, **kwargs) -> None:
    """エラーを無視して fn を実行し、結果をログ出力する。"""
    try:
        fn(*args, **kwargs)
        print(f"  [OK] {label}")
    except Exception as e:
        print(f"  [--] {label}: {e}")


def cleanup_github() -> None:
    config = get_service_config("github")
    if config is None:
        print("GitHub: 設定なし、スキップ")
        return
    print("GitHub クリーンアップ中...")
    adapter = create_test_adapter(config)

    _safe("delete release", adapter.delete_release, tag=TEST_RELEASE_TAG)
    # git タグを削除（リリース削除ではタグが残る）
    _safe(
        "delete git tag",
        adapter._client.delete,  # type: ignore[attr-defined]
        f"{adapter._repos_path()}/git/refs/tags/{TEST_RELEASE_TAG}",  # type: ignore[attr-defined]
    )
    _safe("delete label", adapter.delete_label, name=TEST_LABEL)
    # マイルストーンは番号が必要なので一覧から解決する
    try:
        milestones = adapter.list_milestones()
        for ms in milestones:
            if ms.title == TEST_MILESTONE:
                _safe(f"delete milestone #{ms.number}", adapter.delete_milestone, number=ms.number)
                break
        else:
            print(f"  [--] milestone '{TEST_MILESTONE}': 見つからない（スキップ）")
    except Exception as e:
        print(f"  [--] list milestones: {e}")


def cleanup_gitlab() -> None:
    config = get_service_config("gitlab")
    if config is None:
        print("GitLab: 設定なし、スキップ")
        return
    print("GitLab クリーンアップ中...")
    adapter = create_test_adapter(config)

    _safe("delete release", adapter.delete_release, tag=TEST_RELEASE_TAG)
    # GitLab はリリース削除でもタグは残る
    _safe(
        "delete git tag",
        adapter._client.delete,  # type: ignore[attr-defined]
        f"{adapter._project_path()}/repository/tags/{TEST_RELEASE_TAG}",  # type: ignore[attr-defined]
    )
    _safe("delete label", adapter.delete_label, name=TEST_LABEL)
    try:
        milestones = adapter.list_milestones()
        for ms in milestones:
            if ms.title == TEST_MILESTONE:
                _safe(f"delete milestone #{ms.number}", adapter.delete_milestone, number=ms.number)
                break
        else:
            print(f"  [--] milestone '{TEST_MILESTONE}': 見つからない（スキップ）")
    except Exception as e:
        print(f"  [--] list milestones: {e}")


if __name__ == "__main__":
    cleanup_github()
    cleanup_gitlab()
    print("完了")
