"""gfo review サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse

from gfo.commands import get_adapter
from gfo.exceptions import ConfigError
from gfo.i18n import _
from gfo.output import output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo review list <number> のハンドラ。"""
    adapter = get_adapter()
    reviews = adapter.list_reviews(args.number)
    output(reviews, fmt=fmt, fields=["id", "state", "author", "body"], jq=jq)


def handle_create(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo review create <number> --approve|--request-changes|--comment のハンドラ。"""
    adapter = get_adapter()
    if args.approve:
        state = "APPROVE"
    elif args.request_changes:
        state = "REQUEST_CHANGES"
    else:
        state = "COMMENT"
    if state == "COMMENT" and not args.body:
        raise ConfigError(_("--body is required when using --comment"))
    review = adapter.create_review(args.number, state=state, body=args.body or "")
    output(review, fmt=fmt, jq=jq)
