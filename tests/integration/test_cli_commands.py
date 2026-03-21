"""commands 層固有ロジックの統合テスト。

adapter テストでは検証不能な commands 層のロジックを CLI 経由で検証する:
- エラー JSON フォーマット (format_error_json)
- NotSupportedError の exit_code
- --jq フィルタ適用
- --limit オプション
- --state フィルタ
- schema / api コマンド
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

# ── label 非対応サービスを使ってエラー出力をテスト ──
_LABEL_NOT_SUPPORTED_SERVICES = ["bitbucket", "azure-devops", "gogs", "backlog"]

# ── repo languages / topics 対応サービス ──
_LANGUAGES_SUPPORTED = {"github", "gitlab", "gitea", "forgejo"}

# ── repo star 対応サービス ──
_STAR_SUPPORTED = {"github", "gitlab", "gitea", "forgejo"}

# ── 各サービスの SaaS/selfhosted マーカー ──
_SERVICE_MARKER = {
    "github": "saas",
    "gitlab": "saas",
    "bitbucket": "saas",
    "azure-devops": "saas",
    "backlog": "saas",
    "gitea": "selfhosted",
    "forgejo": "selfhosted",
    "gogs": "selfhosted",
    "gitbucket": "selfhosted",
}


def _make_commands_test_class(
    service_type: str,
    *,
    marker: str,
    skip_reason: str,
):
    """サービスごとの commands 層テストクラスを動的に生成する。"""
    config = get_service_config(service_type)

    marks = [
        pytest.mark.integration,
        pytest.mark.cli,
        getattr(pytest.mark, marker),
        pytest.mark.skipif(config is None, reason=skip_reason),
    ]

    class CommandsTestBase:
        """commands 層テスト基底クラス。"""

        CONFIG: ServiceTestConfig | None = config

        @classmethod
        def setup_class(cls) -> None:
            assert cls.CONFIG is not None
            cls.adapter = create_test_adapter(cls.CONFIG)
            cls.project_config = make_project_config(cls.CONFIG)

        def _run(self, argv: list[str]) -> CLIResult:
            return run_cli(argv, self.adapter, config=self.project_config)

        # ── --jq フィルタ ──

        def test_jq_filter_issue_list(self) -> None:
            result = self._run(
                [
                    "issue",
                    "list",
                    "--limit",
                    "5",
                    "--format",
                    "json",
                    "--jq",
                    ".[].title",
                ]
            )
            assert result.exit_code == 0

        def test_jq_filter_repo_name(self) -> None:
            result = self._run(
                [
                    "repo",
                    "view",
                    "--jq",
                    ".[0].name",
                ]
            )
            assert result.exit_code == 0
            # jq 出力はリポジトリ名
            assert result.stdout.strip()

        # ── --limit オプション ──

        def test_limit_option(self) -> None:
            result = self._run(
                [
                    "repo",
                    "list",
                    "--limit",
                    "2",
                    "--format",
                    "json",
                ]
            )
            assert result.exit_code == 0
            data = result.json()
            assert isinstance(data, list)
            assert len(data) <= 2

        # ── --state フィルタ ──

        def test_state_filter_closed(self) -> None:
            result = self._run(
                [
                    "issue",
                    "list",
                    "--state",
                    "closed",
                    "--limit",
                    "5",
                    "--format",
                    "json",
                ]
            )
            assert result.exit_code == 0
            data = result.json()
            for item in data:
                assert item["state"] in ("closed", "resolved", "Closed")

        # ── repo 高度機能 ──

        def test_repo_languages(self) -> None:
            result = self._run(["repo", "languages", "--format", "json"])
            if service_type in _LANGUAGES_SUPPORTED:
                assert result.exit_code == 0
            else:
                assert result.exit_code == ExitCode.NOT_SUPPORTED

        def test_repo_topics_list(self) -> None:
            result = self._run(["repo", "topics", "list", "--format", "json"])
            if service_type in _LANGUAGES_SUPPORTED:
                assert result.exit_code == 0
            else:
                assert result.exit_code == ExitCode.NOT_SUPPORTED

        def test_repo_star_unstar(self) -> None:
            if service_type not in _STAR_SUPPORTED:
                result = self._run(["repo", "star"])
                assert result.exit_code == ExitCode.NOT_SUPPORTED
                return
            # star
            result = self._run(["repo", "star"])
            assert result.exit_code == 0
            # unstar
            result = self._run(["repo", "unstar"])
            assert result.exit_code == 0

        # ── schema コマンド ──

        def test_schema_list(self) -> None:
            result = self._run(["schema", "--list"])
            assert result.exit_code == 0
            assert result.stdout.strip()

    for mark in marks:
        CommandsTestBase = mark(CommandsTestBase)

    return CommandsTestBase


def _make_error_test_class(
    service_type: str,
    *,
    marker: str,
    skip_reason: str,
):
    """エラー系テストクラスを動的に生成する（非対応コマンドのエラー出力検証）。"""
    config = get_service_config(service_type)

    marks = [
        pytest.mark.integration,
        pytest.mark.cli,
        getattr(pytest.mark, marker),
        pytest.mark.skipif(config is None, reason=skip_reason),
        pytest.mark.skipif(
            service_type not in _LABEL_NOT_SUPPORTED_SERVICES,
            reason=f"{service_type} supports labels, no error to test",
        ),
    ]

    class ErrorTestBase:
        """エラー出力テスト基底クラス。"""

        CONFIG: ServiceTestConfig | None = config

        @classmethod
        def setup_class(cls) -> None:
            assert cls.CONFIG is not None
            cls.adapter = create_test_adapter(cls.CONFIG)
            cls.project_config = make_project_config(cls.CONFIG)

        def _run(self, argv: list[str]) -> CLIResult:
            return run_cli(argv, self.adapter, config=self.project_config)

        def test_error_json_format(self) -> None:
            """非対応コマンドを --format json で呼んだ場合、構造化 JSON エラーが stderr に出力される。"""
            result = self._run(["label", "list", "--format", "json"])
            assert result.exit_code == ExitCode.NOT_SUPPORTED
            error = json.loads(result.stderr)
            assert error["error"] == "not_supported"
            assert "exit_code" in error

        def test_not_supported_exit_code(self) -> None:
            """非対応コマンドの exit_code が NOT_SUPPORTED と一致する。"""
            result = self._run(["label", "list"])
            assert result.exit_code == ExitCode.NOT_SUPPORTED

    for mark in marks:
        ErrorTestBase = mark(ErrorTestBase)

    return ErrorTestBase


# ── commands 層テスト: 全サービス ──


class TestCommandsGitHub(
    _make_commands_test_class(
        "github", marker="saas", skip_reason="GitHub credentials not configured"
    )
):
    pass


class TestCommandsGitLab(
    _make_commands_test_class(
        "gitlab", marker="saas", skip_reason="GitLab credentials not configured"
    )
):
    pass


class TestCommandsBitbucket(
    _make_commands_test_class(
        "bitbucket", marker="saas", skip_reason="Bitbucket credentials not configured"
    )
):
    pass


class TestCommandsAzureDevOps(
    _make_commands_test_class(
        "azure-devops", marker="saas", skip_reason="Azure DevOps credentials not configured"
    )
):
    pass


class TestCommandsBacklog(
    _make_commands_test_class(
        "backlog",
        marker="saas",
        skip_reason="Backlog credentials not configured (paid service)",
    )
):
    pass


class TestCommandsGitea(
    _make_commands_test_class(
        "gitea", marker="selfhosted", skip_reason="Gitea credentials not configured"
    )
):
    pass


class TestCommandsForgejo(
    _make_commands_test_class(
        "forgejo", marker="selfhosted", skip_reason="Forgejo credentials not configured"
    )
):
    pass


class TestCommandsGogs(
    _make_commands_test_class(
        "gogs", marker="selfhosted", skip_reason="Gogs credentials not configured"
    )
):
    pass


class TestCommandsGitBucket(
    _make_commands_test_class(
        "gitbucket", marker="selfhosted", skip_reason="GitBucket credentials not configured"
    )
):
    pass


# ── エラー出力テスト: 非対応サービスのみ ──


class TestErrorBitbucket(
    _make_error_test_class(
        "bitbucket", marker="saas", skip_reason="Bitbucket credentials not configured"
    )
):
    pass


class TestErrorAzureDevOps(
    _make_error_test_class(
        "azure-devops", marker="saas", skip_reason="Azure DevOps credentials not configured"
    )
):
    pass


class TestErrorBacklog(
    _make_error_test_class(
        "backlog",
        marker="saas",
        skip_reason="Backlog credentials not configured (paid service)",
    )
):
    pass


class TestErrorGogs(
    _make_error_test_class(
        "gogs", marker="selfhosted", skip_reason="Gogs credentials not configured"
    )
):
    pass
