"""gfo user サブコマンドのハンドラ。"""

from __future__ import annotations

import argparse
import json

from gfo.commands import get_adapter


def handle_whoami(args: argparse.Namespace, *, fmt: str) -> None:
    """gfo user whoami のハンドラ。"""
    adapter = get_adapter()
    user = adapter.get_current_user()
    if fmt == "json":
        print(json.dumps(user, ensure_ascii=False, indent=2))
    else:
        for key, value in user.items():
            print(f"{key}: {value}")
