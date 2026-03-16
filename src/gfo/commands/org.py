"""gfo org サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import json

from gfo.commands import get_adapter
from gfo.output import apply_jq_filter, output


def handle_list(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo org list のハンドラ。"""
    adapter = get_adapter()
    orgs = adapter.list_organizations(limit=args.limit)
    output(orgs, fmt=fmt, fields=["name", "display_name", "url"], jq=jq)


def handle_view(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo org view <name> のハンドラ。"""
    adapter = get_adapter()
    org = adapter.get_organization(args.name)
    output(org, fmt=fmt, jq=jq)


def handle_members(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo org members <name> のハンドラ。"""
    adapter = get_adapter()
    members = adapter.list_org_members(args.name, limit=args.limit)
    if fmt == "json":
        json_str = json.dumps(members, ensure_ascii=False)
        if jq is not None:
            print(apply_jq_filter(json_str, jq))
        else:
            print(json_str)
        return
    for member in members:
        print(member)


def handle_repos(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo org repos <name> のハンドラ。"""
    adapter = get_adapter()
    repos = adapter.list_org_repos(args.name, limit=args.limit)
    output(repos, fmt=fmt, fields=["name", "full_name", "private", "url"], jq=jq)
