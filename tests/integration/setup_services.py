"""セルフホストサービスの初期セットアップ。

Usage: python tests/integration/setup_services.py

各サービスに管理者ユーザーを作成し、API トークンを生成する。
テスト用リポジトリとブランチも作成する。
生成されたトークンは .env ファイルに書き出す。
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

ENV_FILE = Path(__file__).parent / ".env"

ADMIN_USER = "gfo-admin"
ADMIN_PASS = "gfo-test-pass123"
ADMIN_EMAIL = "admin@test.local"
TEST_REPO = "gfo-integration-test"
TEST_BRANCH = "gfo-test-branch"

# GitBucket のデフォルト管理者
GITBUCKET_USER = "root"
GITBUCKET_PASS = "root"


def wait_for_health(url: str, *, timeout: int = 120, interval: int = 3) -> None:
    """サービスのヘルスチェック URL にアクセスできるまで待機する。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code < 500:
                return
        except requests.ConnectionError:
            pass
        time.sleep(interval)
    raise TimeoutError(f"Service at {url} did not become healthy within {timeout}s")


def append_env(key: str, value: str) -> None:
    """環境変数を .env ファイルに追記する。既存キーは上書き。"""
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()

    new_lines = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(new_lines) + "\n")


# ---------------------------------------------------------------------------
# Gitea / Forgejo 共通
# ---------------------------------------------------------------------------

def setup_gitea_like(
    base_url: str,
    prefix: str,
    *,
    container_name: str,
    admin_cmd: str = "gitea",
) -> str:
    """Gitea / Forgejo の初期セットアップを実行する。

    Returns:
        生成されたAPIトークン
    """
    import subprocess

    api_url = f"{base_url}/api/v1"
    print(f"  [{prefix}] Waiting for service at {base_url} ...")
    wait_for_health(f"{api_url}/version")
    print(f"  [{prefix}] Service is ready.")

    # 管理者ユーザー作成 (docker exec)
    print(f"  [{prefix}] Creating admin user ...")
    result = subprocess.run(
        [
            "docker", "exec", container_name,
            admin_cmd, "admin", "user", "create",
            "--username", ADMIN_USER,
            "--password", ADMIN_PASS,
            "--email", ADMIN_EMAIL,
            "--admin",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "already exists" not in result.stderr.lower():
        print(f"  [{prefix}] Warning: user creation: {result.stderr.strip()}")

    # API トークン生成
    print(f"  [{prefix}] Generating API token ...")
    r = requests.post(
        f"{api_url}/users/{ADMIN_USER}/tokens",
        auth=(ADMIN_USER, ADMIN_PASS),
        json={"name": "gfo-test", "scopes": ["all"]},
        timeout=10,
    )
    if r.status_code == 409:
        # トークン名が既に存在する場合 — 削除して再作成
        requests.delete(
            f"{api_url}/users/{ADMIN_USER}/tokens/gfo-test",
            auth=(ADMIN_USER, ADMIN_PASS),
            timeout=10,
        )
        r = requests.post(
            f"{api_url}/users/{ADMIN_USER}/tokens",
            auth=(ADMIN_USER, ADMIN_PASS),
            json={"name": "gfo-test", "scopes": ["all"]},
            timeout=10,
        )
    r.raise_for_status()
    token = r.json()["sha1"]
    print(f"  [{prefix}] Token generated.")

    # テスト用リポジトリ作成
    print(f"  [{prefix}] Creating test repository ...")
    headers = {"Authorization": f"token {token}"}
    r = requests.post(
        f"{api_url}/user/repos",
        headers=headers,
        json={
            "name": TEST_REPO,
            "auto_init": True,
            "default_branch": "main",
            "description": "gfo integration test repository",
        },
        timeout=10,
    )
    if r.status_code == 409:
        print(f"  [{prefix}] Repository already exists.")
    else:
        r.raise_for_status()
        print(f"  [{prefix}] Repository created.")

    # テスト用ブランチ作成
    print(f"  [{prefix}] Creating test branch ...")
    r = requests.post(
        f"{api_url}/repos/{ADMIN_USER}/{TEST_REPO}/branches",
        headers=headers,
        json={"new_branch_name": TEST_BRANCH, "old_branch_name": "main"},
        timeout=10,
    )
    if r.status_code == 409:
        print(f"  [{prefix}] Branch already exists.")
    elif r.ok:
        # テスト用ファイルを追加
        r2 = requests.post(
            f"{api_url}/repos/{ADMIN_USER}/{TEST_REPO}/contents/test-branch-file.txt",
            headers=headers,
            json={
                "message": "test: add branch file",
                "content": base64.b64encode(b"test content for PR").decode(),
                "branch": TEST_BRANCH,
            },
            timeout=10,
        )
        if r2.ok:
            print(f"  [{prefix}] Branch created with test file.")
        else:
            print(f"  [{prefix}] Branch created (file creation: {r2.status_code}).")
    else:
        print(f"  [{prefix}] Branch creation: {r.status_code}")

    # 環境変数を書き出し
    upper = prefix.upper()
    append_env(f"GFO_TEST_{upper}_TOKEN", token)
    append_env(f"GFO_TEST_{upper}_HOST", base_url.replace("http://", ""))
    append_env(f"GFO_TEST_{upper}_OWNER", ADMIN_USER)
    append_env(f"GFO_TEST_{upper}_REPO", TEST_REPO)

    return token


def setup_gitea() -> str:
    return setup_gitea_like(
        "http://localhost:3000",
        "GITEA",
        container_name="gfo-gitea",
        admin_cmd="gitea",
    )


def setup_forgejo() -> str:
    return setup_gitea_like(
        "http://localhost:3001",
        "FORGEJO",
        container_name="gfo-forgejo",
        admin_cmd="forgejo",
    )


# ---------------------------------------------------------------------------
# Gogs
# ---------------------------------------------------------------------------

def setup_gogs() -> str:
    """Gogs の初期セットアップを実行する。"""
    base_url = "http://localhost:3002"
    api_url = f"{base_url}/api/v1"
    prefix = "GOGS"

    print(f"  [{prefix}] Waiting for service at {base_url} ...")
    wait_for_health(base_url)
    print(f"  [{prefix}] Service is ready.")

    # インストール (POST /install)
    print(f"  [{prefix}] Running installation ...")
    r = requests.post(
        f"{base_url}/install",
        data={
            "db_type": "SQLite3",
            "db_path": "/data/gogs/gogs.db",
            "app_name": "Gogs",
            "repo_root_path": "/data/git/gogs-repositories",
            "run_user": "git",
            "domain": "localhost",
            "ssh_port": "22",
            "http_port": "3000",
            "app_url": f"{base_url}/",
            "log_root_path": "/data/gogs/log",
            "admin_name": ADMIN_USER,
            "admin_passwd": ADMIN_PASS,
            "admin_confirm_passwd": ADMIN_PASS,
            "admin_email": ADMIN_EMAIL,
        },
        timeout=30,
        allow_redirects=False,
    )
    if r.status_code in (200, 302):
        print(f"  [{prefix}] Installation complete.")
    else:
        print(f"  [{prefix}] Installation status: {r.status_code} (may already be installed)")

    # API トークン生成
    print(f"  [{prefix}] Generating API token ...")
    r = requests.post(
        f"{api_url}/users/{ADMIN_USER}/tokens",
        auth=(ADMIN_USER, ADMIN_PASS),
        json={"name": "gfo-test"},
        timeout=10,
    )
    if r.status_code == 422:
        # トークン名が既に存在する場合 — 削除して再作成（Gogs はトークン一覧 API が sha1 を返さない）
        requests.delete(
            f"{api_url}/users/{ADMIN_USER}/tokens/gfo-test",
            auth=(ADMIN_USER, ADMIN_PASS),
            timeout=10,
        )
        r = requests.post(
            f"{api_url}/users/{ADMIN_USER}/tokens",
            auth=(ADMIN_USER, ADMIN_PASS),
            json={"name": "gfo-test"},
            timeout=10,
        )
        r.raise_for_status()
        token = r.json()["sha1"]
    else:
        r.raise_for_status()
        token = r.json()["sha1"]
    print(f"  [{prefix}] Token generated.")

    # テスト用リポジトリ作成
    print(f"  [{prefix}] Creating test repository ...")
    headers = {"Authorization": f"token {token}"}
    r = requests.post(
        f"{api_url}/user/repos",
        headers=headers,
        json={
            "name": TEST_REPO,
            "auto_init": True,
            "description": "gfo integration test repository",
        },
        timeout=10,
    )
    if r.status_code == 409 or r.status_code == 422:
        print(f"  [{prefix}] Repository already exists.")
    else:
        r.raise_for_status()
        print(f"  [{prefix}] Repository created.")

    # Gogs は PR 非対応のためブランチ作成は不要

    # 環境変数を書き出し
    append_env(f"GFO_TEST_{prefix}_TOKEN", token)
    append_env(f"GFO_TEST_{prefix}_HOST", "localhost:3002")
    append_env(f"GFO_TEST_{prefix}_OWNER", ADMIN_USER)
    append_env(f"GFO_TEST_{prefix}_REPO", TEST_REPO)

    return token


# ---------------------------------------------------------------------------
# GitBucket
# ---------------------------------------------------------------------------

def setup_gitbucket() -> str:
    """GitBucket の初期セットアップを実行する。"""
    base_url = "http://localhost:3003"
    api_url = f"{base_url}/api/v3"
    prefix = "GITBUCKET"

    print(f"  [{prefix}] Waiting for service at {base_url} ...")
    wait_for_health(f"{api_url}/rate_limit")
    print(f"  [{prefix}] Service is ready.")

    # GitBucket はデフォルトで root/root の管理者が存在
    auth = (GITBUCKET_USER, GITBUCKET_PASS)

    # Personal access token 生成
    print(f"  [{prefix}] Generating API token ...")
    r = requests.post(
        f"{api_url}/authorizations",
        auth=auth,
        json={"scopes": ["repo"], "note": "gfo-test"},
        timeout=10,
    )
    if r.status_code == 422 or r.status_code == 409:
        # 既存トークンが存在するが取得できない — GitBucket は token 一覧 API がない
        raise RuntimeError(
            f"[{prefix}] Token 'gfo-test' already exists but cannot be retrieved. "
            "Please delete the token manually via GitBucket Web UI or restart the container."
        )
    elif r.ok:
        token = r.json().get("token", "")
        if not token:
            raise RuntimeError(f"[{prefix}] Token generation succeeded but token value is empty.")
        print(f"  [{prefix}] Token generated.")
    else:
        raise RuntimeError(f"[{prefix}] Token generation failed: {r.status_code} {r.text[:200]}")

    # テスト用リポジトリ作成
    print(f"  [{prefix}] Creating test repository ...")
    r = requests.post(
        f"{api_url}/user/repos",
        auth=auth,
        json={
            "name": TEST_REPO,
            "auto_init": True,
            "description": "gfo integration test repository",
            "private": False,
        },
        timeout=10,
    )
    if r.status_code == 422 or r.status_code == 409:
        print(f"  [{prefix}] Repository already exists.")
    elif r.ok:
        print(f"  [{prefix}] Repository created.")
    else:
        print(f"  [{prefix}] Repository creation: {r.status_code} {r.text[:200]}")

    # テスト用ブランチ作成 (API でファイルを作成してブランチを分岐)
    print(f"  [{prefix}] Creating test branch ...")
    # まず main の SHA を取得
    r = requests.get(
        f"{api_url}/repos/{GITBUCKET_USER}/{TEST_REPO}/git/refs/heads/main",
        auth=auth,
        timeout=10,
    )
    if r.ok:
        sha = r.json().get("object", {}).get("sha", "")
        if sha:
            r2 = requests.post(
                f"{api_url}/repos/{GITBUCKET_USER}/{TEST_REPO}/git/refs",
                auth=auth,
                json={"ref": f"refs/heads/{TEST_BRANCH}", "sha": sha},
                timeout=10,
            )
            if r2.ok or r2.status_code == 422:
                print(f"  [{prefix}] Branch ready.")
                # テスト用ファイルを追加
                content_b64 = base64.b64encode(b"test content for PR").decode()
                requests.put(
                    f"{api_url}/repos/{GITBUCKET_USER}/{TEST_REPO}/contents/test-branch-file.txt",
                    auth=auth,
                    json={
                        "message": "test: add branch file",
                        "content": content_b64,
                        "branch": TEST_BRANCH,
                    },
                    timeout=10,
                )
            else:
                print(f"  [{prefix}] Branch creation: {r2.status_code}")
    else:
        # master ブランチを試す
        r = requests.get(
            f"{api_url}/repos/{GITBUCKET_USER}/{TEST_REPO}/git/refs/heads/master",
            auth=auth,
            timeout=10,
        )
        if r.ok:
            sha = r.json().get("object", {}).get("sha", "")
            if sha:
                requests.post(
                    f"{api_url}/repos/{GITBUCKET_USER}/{TEST_REPO}/git/refs",
                    auth=auth,
                    json={"ref": f"refs/heads/{TEST_BRANCH}", "sha": sha},
                    timeout=10,
                )
                print(f"  [{prefix}] Branch created from master.")
        else:
            print(f"  [{prefix}] Could not find default branch.")

    # 環境変数を書き出し
    append_env(f"GFO_TEST_{prefix}_TOKEN", token)
    append_env(f"GFO_TEST_{prefix}_HOST", "localhost:3003")
    append_env(f"GFO_TEST_{prefix}_OWNER", GITBUCKET_USER)
    append_env(f"GFO_TEST_{prefix}_REPO", TEST_REPO)

    return token


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("gfo Integration Test - Service Setup")
    print("=" * 60)

    services = [
        ("Gitea", setup_gitea),
        ("Forgejo", setup_forgejo),
        ("Gogs", setup_gogs),
        ("GitBucket", setup_gitbucket),
    ]

    results: dict[str, str] = {}
    for name, setup_fn in services:
        print(f"\n--- {name} ---")
        try:
            token = setup_fn()
            results[name] = "OK"
            print(f"  [{name}] Setup complete.")
        except Exception as e:
            results[name] = f"FAILED: {e}"
            print(f"  [{name}] Setup FAILED: {e}")

    print("\n" + "=" * 60)
    print("Setup Results:")
    for name, status in results.items():
        print(f"  {name}: {status}")
    print("=" * 60)

    if ENV_FILE.exists():
        print(f"\nEnvironment variables written to: {ENV_FILE}")
    else:
        print("\nWarning: No .env file was created.")

    if any("FAILED" in s for s in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
