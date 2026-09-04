"""gfo user サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import json

from gfo.commands import get_adapter
from gfo.output import apply_jq_filter


def handle_whoami(args: argparse.Namespace, *, fmt: str, jq: str | None = None) -> None:
    """gfo user whoami のハンドラ。"""
    adapter = get_adapter(require_repo=False)
    user = adapter.get_current_user()
    if fmt == "json":
        json_str = json.dumps(user, ensure_ascii=False, indent=2)
        if jq is not None:
            print(apply_jq_filter(json_str, jq))
        else:
            print(json_str)
    elif fmt == "plain":
        for value in user.values():
            plain_value = "" if value is None else str(value)
            print(plain_value.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t"))
    else:
        for key, value in user.items():
            print(f"{key}: {value}")
