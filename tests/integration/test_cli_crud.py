"""CLI CRUD ライフサイクルテスト: 書き込み系コマンドを CLI 経由で実行し、導線を検証する。

Issue のライフサイクル (create → view → list → close) と
Label のライフサイクル (create → list → delete) を CLI 経由で検証する。
"""

from __future__ import annotations

import time

import pytest

from gfo.exceptions import ExitCode
from tests.integration.cli_helper import CLIResult, make_project_config, run_cli
from tests.integration.conftest import (
    ServiceTestConfig,
    create_test_adapter,
    get_service_config,
)

# ── issue close が非対応のサービス ──
_ISSUE_CLOSE_NOT_SUPPORTED = {"gitbucket"}

# ── label CRUD が対応しているサービス ──
_LABEL_SUPPORTED = {"github", "gitlab", "gitea", "forgejo"}


def _make_issue_lifecycle_class(
    service_type: str,
    *,
    marker: str,
    skip_reason: str,
):
    """サービスごとの Issue ライフサイクルテストクラスを動的に生成する。"""
    config = get_service_config(service_type)

    marks = [
        pytest.mark.integration,
        pytest.mark.cli,
        getattr(pytest.mark, marker),
        pytest.mark.skipif(config is None, reason=skip_reason),
    ]

    class IssueLifecycleBase:
        """Issue ライフサイクル CLI テスト基底クラス。テスト間の順序依存あり。"""

        CONFIG: ServiceTestConfig | None = config
        _issue_number: int | None = None

        @classmethod
        def setup_class(cls) -> None:
            assert cls.CONFIG is not None
            cls.adapter = create_test_adapter(cls.CONFIG)
            cls.project_config = make_project_config(cls.CONFIG)

        @classmethod
        def teardown_class(cls) -> None:
            if cls._issue_number is not None and cls.CONFIG is not None:
                try:
                    adapter = create_test_adapter(cls.CONFIG)
                    adapter.close_issue(cls._issue_number)
                except Exception:
                    pass

        def _run(self, argv: list[str]) -> CLIResult:
            return run_cli(argv, self.adapter, config=self.project_config)

        def test_01_issue_create(self) -> None:
            result = self._run(
                [
                    "issue",
                    "create",
                    "--title",
                    "cli-test-issue",
                    "--body",
                    "Created by CLI integration test",
                    "--format",
                    "json",
                ]
            )
            assert result.exit_code == 0, f"stderr: {result.stderr}"
            data = result.json()
            assert isinstance(data, list)
            assert len(data) == 1
            number = data[0]["number"]
            assert isinstance(number, int)
            self.__class__._issue_number = number

        def test_02_issue_view(self) -> None:
            assert self._issue_number is not None
            result = self._run(
                [
                    "issue",
                    "view",
                    str(self._issue_number),
                    "--format",
                    "json",
                ]
            )
            assert result.exit_code == 0
            data = result.json()
            assert isinstance(data, list)
            assert data[0]["title"] == "cli-test-issue"

        def test_03_issue_list_contains(self) -> None:
            assert self._issue_number is not None
            import time

            for _ in range(5):
                result = self._run(
                    [
                        "issue",
                        "list",
                        "--state",
                        "open",
                        "--format",
                        "json",
                    ]
                )
                assert result.exit_code == 0
                data = result.json()
                numbers = [item["number"] for item in data]
                if self._issue_number in numbers:
                    break
                time.sleep(3)
            assert self._issue_number in numbers

        def test_04_issue_close(self) -> None:
            assert self._issue_number is not None
            if service_type in _ISSUE_CLOSE_NOT_SUPPORTED:
                result = self._run(["issue", "close", str(self._issue_number)])
                assert result.exit_code == ExitCode.NOT_SUPPORTED
            else:
                result = self._run(["issue", "close", str(self._issue_number)])
                assert result.exit_code == 0
                self.__class__._issue_number = None  # teardown 不要

    for mark in marks:
        IssueLifecycleBase = mark(IssueLifecycleBase)

    return IssueLifecycleBase


def _make_label_lifecycle_class(
    service_type: str,
    *,
    marker: str,
    skip_reason: str,
):
    """サービスごとの Label ライフサイクルテストクラスを動的に生成する。"""
    config = get_service_config(service_type)

    skip_not_supported = service_type not in _LABEL_SUPPORTED

    marks = [
        pytest.mark.integration,
        pytest.mark.cli,
        getattr(pytest.mark, marker),
        pytest.mark.skipif(config is None, reason=skip_reason),
        pytest.mark.skipif(skip_not_supported, reason=f"{service_type} does not support labels"),
    ]

    class LabelLifecycleBase:
        """Label ライフサイクル CLI テスト基底クラス。"""

        CONFIG: ServiceTestConfig | None = config
        _label_created: bool = False

        @classmethod
        def setup_class(cls) -> None:
            assert cls.CONFIG is not None
            cls.adapter = create_test_adapter(cls.CONFIG)
            cls.project_config = make_project_config(cls.CONFIG)

        @classmethod
        def teardown_class(cls) -> None:
            if cls._label_created and cls.CONFIG is not None:
                try:
                    adapter = create_test_adapter(cls.CONFIG)
                    adapter.delete_label(name="cli-test-label")
                except Exception:
                    pass

        def _run(self, argv: list[str]) -> CLIResult:
            return run_cli(argv, self.adapter, config=self.project_config)

        def test_01_label_create(self) -> None:
            result = self._run(
                [
                    "label",
                    "create",
                    "cli-test-label",
                    "--color",
                    "00ff00",
                    "--format",
                    "json",
                ]
            )
            assert result.exit_code == 0, f"stderr: {result.stderr}"
            self.__class__._label_created = True

        def test_02_label_list_contains(self) -> None:
            time.sleep(3)  # API 反映ラグ対策
            result = self._run(["label", "list", "--format", "json"])
            assert result.exit_code == 0
            data = result.json()
            names = [item["name"] for item in data]
            assert "cli-test-label" in names

        def test_03_label_delete(self) -> None:
            result = self._run(["label", "delete", "cli-test-label"])
            assert result.exit_code == 0
            self.__class__._label_created = False

    for mark in marks:
        LabelLifecycleBase = mark(LabelLifecycleBase)

    return LabelLifecycleBase


# ── Issue ライフサイクル: SaaS サービス ──


class TestCLIIssueGitHub(
    _make_issue_lifecycle_class(
        "github", marker="saas", skip_reason="GitHub credentials not configured"
    )
):
    pass


class TestCLIIssueGitLab(
    _make_issue_lifecycle_class(
        "gitlab", marker="saas", skip_reason="GitLab credentials not configured"
    )
):
    pass


class TestCLIIssueBitbucket(
    _make_issue_lifecycle_class(
        "bitbucket", marker="saas", skip_reason="Bitbucket credentials not configured"
    )
):
    pass


class TestCLIIssueAzureDevOps(
    _make_issue_lifecycle_class(
        "azure-devops", marker="saas", skip_reason="Azure DevOps credentials not configured"
    )
):
    pass


class TestCLIIssueBacklog(
    _make_issue_lifecycle_class(
        "backlog",
        marker="saas",
        skip_reason="Backlog credentials not configured (paid service)",
    )
):
    pass


# ── Issue ライフサイクル: セルフホスト ──


class TestCLIIssueGitea(
    _make_issue_lifecycle_class(
        "gitea", marker="selfhosted", skip_reason="Gitea credentials not configured"
    )
):
    pass


class TestCLIIssueForgejo(
    _make_issue_lifecycle_class(
        "forgejo", marker="selfhosted", skip_reason="Forgejo credentials not configured"
    )
):
    pass


class TestCLIIssueGogs(
    _make_issue_lifecycle_class(
        "gogs", marker="selfhosted", skip_reason="Gogs credentials not configured"
    )
):
    pass


class TestCLIIssueGitBucket(
    _make_issue_lifecycle_class(
        "gitbucket", marker="selfhosted", skip_reason="GitBucket credentials not configured"
    )
):
    pass


# ── Label ライフサイクル（対応サービスのみ） ──


class TestCLILabelGitHub(
    _make_label_lifecycle_class(
        "github", marker="saas", skip_reason="GitHub credentials not configured"
    )
):
    pass


class TestCLILabelGitLab(
    _make_label_lifecycle_class(
        "gitlab", marker="saas", skip_reason="GitLab credentials not configured"
    )
):
    pass


class TestCLILabelGitea(
    _make_label_lifecycle_class(
        "gitea", marker="selfhosted", skip_reason="Gitea credentials not configured"
    )
):
    pass


class TestCLILabelForgejo(
    _make_label_lifecycle_class(
        "forgejo", marker="selfhosted", skip_reason="Forgejo credentials not configured"
    )
):
    pass
