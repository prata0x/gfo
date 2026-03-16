"""hatchling カスタムビルドフック: .po → .mo をビルド時に自動コンパイルする。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class MoCompileHook(BuildHookInterface):
    PLUGIN_NAME = "mo-compile"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        from build_mo import compile_all

        locale_dir = Path(self.root) / "src" / "gfo" / "locale"
        compiled = compile_all(locale_dir)
        for mo_path in compiled:
            rel = mo_path.relative_to(Path(self.root) / "src" / "gfo")
            build_data["force_include"][str(mo_path)] = f"gfo/{rel}"
