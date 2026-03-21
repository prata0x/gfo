"""CLI 統合テスト用ヘルパー。

gfo.cli.main(argv) を呼び出し、stdout/stderr/exit_code をキャプチャする。
adapter は gfo.commands.get_adapter / get_adapter_with_config をパッチして注入する。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from io import StringIO
from typing import Any
from unittest.mock import patch

from gfo.adapter.base import GitServiceAdapter
from gfo.cli import main
from gfo.config import ProjectConfig
from tests.integration.conftest import ServiceTestConfig


@dataclass
class CLIResult:
    """CLI 実行結果を保持するデータクラス。"""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def lines(self) -> list[str]:
        """stdout を行に分割して返す（末尾空行除去）。"""
        text = self.stdout.rstrip("\n")
        return text.split("\n") if text else []

    def json(self) -> Any:
        """stdout を JSON としてパースして返す。"""
        return json.loads(self.stdout)


def make_project_config(test_config: ServiceTestConfig) -> ProjectConfig:
    """ServiceTestConfig から ProjectConfig を生成する。"""
    return ProjectConfig(
        service_type=test_config.service_type,
        host=test_config.host,
        api_url=test_config.api_url,
        owner=test_config.owner,
        repo=test_config.repo,
        organization=test_config.organization,
        project_key=test_config.project_key,
    )


def run_cli(
    argv: list[str],
    adapter: GitServiceAdapter,
    *,
    config: ProjectConfig | None = None,
) -> CLIResult:
    """gfo CLI を指定の adapter を注入して実行し、結果を返す。

    Args:
        argv: コマンドライン引数（例: ["repo", "view"]）
        adapter: テスト用のアダプターインスタンス
        config: get_adapter_with_config 用の ProjectConfig（省略時はダミー）

    Returns:
        CLIResult: exit_code, stdout, stderr を含む結果
    """
    if config is None:
        config = ProjectConfig(
            service_type=getattr(adapter, "service_name", "github"),
            host="test.example.com",
            api_url="https://test.example.com/api",
            owner=adapter.owner,
            repo=adapter.repo,
        )

    captured_out = StringIO()
    captured_err = StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = captured_out
        sys.stderr = captured_err

        with (
            patch("gfo.commands.get_adapter", return_value=adapter),
            patch("gfo.commands.get_adapter_with_config", return_value=(adapter, config)),
        ):
            exit_code = main(argv)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    return CLIResult(
        exit_code=exit_code,
        stdout=captured_out.getvalue(),
        stderr=captured_err.getvalue(),
    )
