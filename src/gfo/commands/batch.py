"""gfo batch サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from gfo.commands import create_adapter_from_spec, parse_service_spec
from gfo.exceptions import ConfigError, GfoError
from gfo.i18n import _
from gfo.output import output


@dataclass(frozen=True, slots=True)
class BatchPrResult:
    repo: str
    number: int | None
    url: str | None
    status: str  # "created" | "failed" | "skipped"
    error: str | None = None


def handle_batch_pr(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo batch pr create のハンドラ。"""
    action = getattr(args, "batch_pr_action", None)
    if action is None:
        raise ConfigError(_("Specify a subcommand: create"))

    repo_specs_str = args.repos.split(",")
    results: list[BatchPrResult] = []
    dry_run = getattr(args, "dry_run", False)

    for spec_str in repo_specs_str:
        spec_str = spec_str.strip()
        if not spec_str:
            continue
        spec = None  # ループの except で再利用するためあらかじめ宣言
        try:
            spec = parse_service_spec(spec_str)
            adapter = create_adapter_from_spec(spec)
            repo_label = f"{spec.service_type}:{spec.owner}/{spec.repo}"

            if dry_run:
                results.append(
                    BatchPrResult(
                        repo=repo_label, number=None, url=None, status="skipped", error=None
                    )
                )
                continue

            pr = adapter.create_pull_request(
                title=args.title,
                body=args.body,
                head=args.head,
                base=args.base,
                draft=getattr(args, "draft", False),
            )
            results.append(
                BatchPrResult(
                    repo=repo_label, number=pr.number, url=pr.url, status="created", error=None
                )
            )
        except GfoError as e:
            # GfoError 系（HttpError / NetworkError / ConfigError / AuthError 等）のみ
            # 「failed」として記録する。AttributeError / TypeError / KeyError などの
            # プログラミングエラーは握りつぶさず再 raise する（実装バグを隠さない）。
            if spec is not None:
                repo_label = f"{spec.service_type}:{spec.owner}/{spec.repo}"
            else:
                repo_label = spec_str
            results.append(
                BatchPrResult(repo=repo_label, number=None, url=None, status="failed", error=str(e))
            )

    output(results, fmt=fmt, fields=["repo", "number", "url", "status", "error"], jq=jq)
