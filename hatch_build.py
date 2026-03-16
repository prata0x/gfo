"""hatchling カスタムビルドフック: .po → .mo をビルド時に自動コンパイルする。"""

from __future__ import annotations

import array
import ast
import struct
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def _parse_po(po_path: Path) -> dict[str, str]:
    """PO ファイルをパースして {msgid: msgstr} を返す。"""
    messages: dict[str, str] = {}
    lines = po_path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        if line.startswith("msgid "):
            msgid_str = ast.literal_eval(line[6:])
            i += 1
            while i < len(lines) and lines[i].strip().startswith('"'):
                msgid_str += ast.literal_eval(lines[i].strip())
                i += 1
            line2 = lines[i].strip()
            if line2.startswith("msgstr "):
                msgstr_str = ast.literal_eval(line2[7:])
                i += 1
                while i < len(lines) and lines[i].strip().startswith('"'):
                    msgstr_str += ast.literal_eval(lines[i].strip())
                    i += 1
                if msgstr_str:
                    messages[msgid_str] = msgstr_str
            else:
                i += 1
        else:
            i += 1
    return messages


def _generate_mo(messages: dict[str, str], mo_path: Path) -> None:
    """メッセージ辞書から .mo バイナリを生成する。"""
    keys = sorted(messages.keys())
    offsets: list[tuple[int, int, int, int]] = []
    ids = strs = b""
    for key in keys:
        id_bytes = key.encode("utf-8")
        str_bytes = messages[key].encode("utf-8")
        offsets.append((len(ids), len(id_bytes), len(strs), len(str_bytes)))
        ids += id_bytes + b"\x00"
        strs += str_bytes + b"\x00"

    keystart = 7 * 4 + 16 * len(keys)
    valuestart = keystart + len(ids)

    koffsets: list[int] = []
    voffsets: list[int] = []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]

    offsets_data = array.array("i", koffsets + voffsets)

    output = struct.pack(
        "Iiiiiii",
        0x950412DE,
        0,
        len(keys),
        7 * 4,
        7 * 4 + len(keys) * 8,
        0,
        0,
    )
    output += offsets_data.tobytes()
    output += ids
    output += strs

    mo_path.parent.mkdir(parents=True, exist_ok=True)
    mo_path.write_bytes(output)


def _compile_all(locale_dir: Path) -> list[Path]:
    """locale_dir 配下の全 .po を .mo にコンパイルする。"""
    compiled: list[Path] = []
    for po_path in locale_dir.rglob("*.po"):
        mo_path = po_path.with_suffix(".mo")
        messages = _parse_po(po_path)
        _generate_mo(messages, mo_path)
        compiled.append(mo_path)
    return compiled


class MoCompileHook(BuildHookInterface):
    PLUGIN_NAME = "mo-compile"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        locale_dir = Path(self.root) / "src" / "gfo" / "locale"
        compiled = _compile_all(locale_dir)
        for mo_path in compiled:
            rel = mo_path.relative_to(Path(self.root) / "src" / "gfo")
            build_data["force_include"][str(mo_path)] = f"gfo/{rel.as_posix()}"
