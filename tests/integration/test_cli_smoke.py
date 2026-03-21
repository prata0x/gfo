"""CLI スモークテスト: 読み取り系コマンドを CLI 経由で実行し、導線を検証する。

CLI → argparse → handler → adapter → output の統合テスト。
各サービスの読み取り専用コマンドを実行し、exit_code=0 と基本的な出力形式を検証する。
"""

from __future__ import annotations

import json

import pytest

from gfo.exceptions import ExitCode
from tests.integration.cli_helper import CLIResult, make_project_config, run_cli
from tests.integration.conftest import (
    ServiceTestConfig,
    create_test_adapter,
    get_service_config,
)

# ── サービス非対応マッピング ──
# label list が NotSupportedError になるサービス
_LABEL_NOT_SUPPORTED = {"bitbucket", "backlog", "azure-devops", "gogs"}
# PR list が NotSupportedError になるサービス
_PR_NOT_SUPPORTED = {"gogs"}


def _make_cli_test_class(
    service_type: str,
    *,
    marker: str,
    skip_reason: str,
):
    """サービスごとの CLI スモークテストクラスを動的に生成するファクトリ。"""
    config = get_service_config(service_type)

    marks = [
        pytest.mark.integration,
        pytest.mark.cli,
        getattr(pytest.mark, marker),
        pytest.mark.skipif(config is None, reason=skip_reason),
    ]

    class CLISmokeBase:
        """CLI スモークテスト基底クラス。"""

        CONFIG: ServiceTestConfig | None = config

        @classmethod
        def setup_class(cls) -> None:
            assert cls.CONFIG is not None
            cls.adapter = create_test_adapter(cls.CONFIG)
            cls.project_config = make_project_config(cls.CONFIG)

        def _run(self, argv: list[str]) -> CLIResult:
            return run_cli(argv, self.adapter, config=self.project_config)

        # ── 読み取り系テスト ──

        def test_repo_view(self) -> None:
            result = self._run(["repo", "view", "--format", "json"])
            assert result.exit_code == 0
            data = result.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert "name" in data[0]

        def test_repo_list(self) -> None:
            result = self._run(["repo", "list", "--limit", "3", "--format", "json"])
            assert result.exit_code == 0
            data = result.json()
            assert isinstance(data, list)

        def test_issue_list(self) -> None:
            result = self._run(["issue", "list", "--limit", "5", "--format", "json"])
            assert result.exit_code == 0

        def test_pr_list(self) -> None:
            result = self._run(["pr", "list", "--limit", "5", "--format", "json"])
            if service_type in _PR_NOT_SUPPORTED:
                assert result.exit_code == ExitCode.NOT_SUPPORTED
            else:
                assert result.exit_code == 0

        def test_branch_list(self) -> None:
            result = self._run(["branch", "list", "--limit", "5", "--format", "json"])
            assert result.exit_code == 0
            data = result.json()
            assert isinstance(data, list)

        def test_tag_list(self) -> None:
            result = self._run(["tag", "list", "--limit", "5", "--format", "json"])
            assert result.exit_code == 0

        def test_label_list(self) -> None:
            if service_type in _LABEL_NOT_SUPPORTED:
                result = self._run(["label", "list", "--format", "json"])
                assert result.exit_code == ExitCode.NOT_SUPPORTED
            else:
                result = self._run(["label", "list", "--format", "json"])
                assert result.exit_code == 0

        def test_user_whoami(self) -> None:
            result = self._run(["user", "whoami", "--format", "json"])
            assert result.exit_code == 0

        # ── 出力整形テスト ──

        def test_format_json(self) -> None:
            result = self._run(["repo", "view", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert isinstance(data, list)

        def test_format_json_jq(self) -> None:
            result = self._run(["repo", "view", "--format", "json", "--jq", ".[0].name"])
            assert result.exit_code == 0
            # jq の結果は引用符付き文字列
            assert result.stdout.strip()

        def test_format_plain(self) -> None:
            result = self._run(["repo", "view", "--format", "plain"])
            assert result.exit_code == 0
            # plain はタブ区切り
            assert "\t" in result.stdout

        def test_issue_list_jq(self) -> None:
            result = self._run(
                ["issue", "list", "--limit", "5", "--format", "json", "--jq", ".[].title"]
            )
            assert result.exit_code == 0

    # マーカーを適用
    for mark in marks:
        CLISmokeBase = mark(CLISmokeBase)

    return CLISmokeBase


# ── SaaS サービス ──


class TestCLISmokeGitHub(
    _make_cli_test_class("github", marker="saas", skip_reason="GitHub credentials not configured")
):
    pass


class TestCLISmokeGitLab(
    _make_cli_test_class("gitlab", marker="saas", skip_reason="GitLab credentials not configured")
):
    pass


class TestCLISmokeAzureDevOps(
    _make_cli_test_class(
        "azure-devops",
        marker="saas",
        skip_reason="Azure DevOps credentials not configured",
    )
):
    pass


class TestCLISmokeBitbucket(
    _make_cli_test_class(
        "bitbucket", marker="saas", skip_reason="Bitbucket credentials not configured"
    )
):
    pass


class TestCLISmokeBacklog(
    _make_cli_test_class(
        "backlog",
        marker="saas",
        skip_reason="Backlog credentials not configured (paid service)",
    )
):
    pass


# ── セルフホスト サービス ──


class TestCLISmokeGitea(
    _make_cli_test_class(
        "gitea", marker="selfhosted", skip_reason="Gitea credentials not configured"
    )
):
    pass


class TestCLISmokeForgejo(
    _make_cli_test_class(
        "forgejo", marker="selfhosted", skip_reason="Forgejo credentials not configured"
    )
):
    pass


class TestCLISmokeGogs(
    _make_cli_test_class("gogs", marker="selfhosted", skip_reason="Gogs credentials not configured")
):
    pass


class TestCLISmokeGitBucket(
    _make_cli_test_class(
        "gitbucket", marker="selfhosted", skip_reason="GitBucket credentials not configured"
    )
):
    pass
