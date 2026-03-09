"""output.py のテスト。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from gfo.output import format_json, format_plain, format_table, output


@dataclass(frozen=True)
class SampleItem:
    number: int
    title: str
    state: str
    author: str


class TestFormatTable:
    def test_single_item(self):
        result = format_table(
            [SampleItem(1, "Fix typo", "open", "alice")],
            ["number", "title", "state", "author"],
        )
        lines = result.split("\n")
        assert len(lines) == 3
        assert "NUMBER" in lines[0]
        assert "TITLE" in lines[0]
        assert "---" in lines[1]
        assert "1" in lines[2]
        assert "Fix typo" in lines[2]

    def test_multiple_items(self):
        items = [
            SampleItem(1, "Fix typo", "open", "alice"),
            SampleItem(42, "Add feature", "merged", "bob"),
        ]
        result = format_table(items, ["number", "title", "state", "author"])
        lines = result.split("\n")
        assert len(lines) == 4  # header + sep + 2 data rows

    def test_fields_selection(self):
        result = format_table(
            [SampleItem(1, "Fix typo", "open", "alice")],
            ["number", "title"],
        )
        assert "NUMBER" in result
        assert "TITLE" in result
        assert "STATE" not in result
        assert "AUTHOR" not in result

    def test_column_width_adjustment(self):
        items = [
            SampleItem(1, "Short", "open", "a"),
            SampleItem(999, "A much longer title here", "closed", "bob"),
        ]
        result = format_table(items, ["number", "title"])
        lines = result.split("\n")
        # separator width should match the longest value
        assert len(lines[1]) >= len("A much longer title here")

    def test_header_width_dominates_when_value_shorter(self):
        """ヘッダー名が値より長い場合、セパレーターはヘッダー幅に合わせる。"""
        result = format_table(
            [SampleItem(1, "X", "Y", "Z")],
            ["number", "title", "state", "author"],
        )
        lines = result.split("\n")
        # "NUMBER" は 6文字、値 "1" は 1文字 → セパレーターは "------" を含む
        assert "------" in lines[1]

    def test_empty_field_value_pads_to_header_width(self):
        """空の値でもヘッダー幅でパディングされる。"""
        result = format_table(
            [SampleItem(1, "", "open", "alice")],
            ["number", "title"],
        )
        assert "NUMBER" in result
        assert "TITLE" in result

    def test_table_trailing_whitespace_stripped(self):
        """末尾に余分な空白が付かないことを確認する。"""
        result = format_table(
            [SampleItem(1, "Short", "x", "y")],
            ["number", "title"],
        )
        for line in result.split("\n"):
            assert line == line.rstrip()


class TestFormatJson:
    def test_single_item_is_object(self):
        result = format_json([SampleItem(1, "Fix typo", "open", "alice")])
        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed["number"] == 1

    def test_multiple_items_is_array(self):
        items = [
            SampleItem(1, "Fix typo", "open", "alice"),
            SampleItem(2, "Update", "closed", "bob"),
        ]
        result = format_json(items)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_ensure_ascii_false(self):
        result = format_json([SampleItem(1, "日本語タイトル", "open", "太郎")])
        assert "日本語タイトル" in result
        assert "太郎" in result

    def test_none_becomes_null(self):
        @dataclass(frozen=True)
        class WithNone:
            name: str
            value: str | None

        result = format_json([WithNone("test", None)])
        parsed = json.loads(result)
        assert parsed["value"] is None


class TestFormatPlain:
    def test_tab_separated(self):
        result = format_plain(
            [SampleItem(1, "Fix typo", "open", "alice")],
            ["number", "title", "state", "author"],
        )
        assert result == "1\tFix typo\topen\talice"

    def test_no_header(self):
        result = format_plain(
            [SampleItem(1, "Fix typo", "open", "alice")],
            ["number", "title"],
        )
        assert "NUMBER" not in result
        assert "TITLE" not in result

    def test_fields_selection(self):
        result = format_plain(
            [SampleItem(1, "Fix typo", "open", "alice")],
            ["number", "state"],
        )
        assert result == "1\topen"


class TestOutput:
    def test_default_fmt_is_table(self, capsys):
        output(SampleItem(1, "Fix typo", "open", "alice"))
        captured = capsys.readouterr()
        assert "NUMBER" in captured.out
        assert "Fix typo" in captured.out

    def test_empty_list_no_output(self, capsys):
        output([])
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_json_fmt(self, capsys):
        output(SampleItem(1, "Fix typo", "open", "alice"), fmt="json")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["number"] == 1

    def test_plain_fmt(self, capsys):
        output(SampleItem(1, "Fix typo", "open", "alice"), fmt="plain")
        captured = capsys.readouterr()
        assert "1\tFix typo\topen\talice" in captured.out

    def test_unknown_fmt_falls_back_to_table(self, capsys):
        """未知の fmt 値はテーブルフォーマットにフォールバックする。"""
        output(SampleItem(1, "Fix typo", "open", "alice"), fmt="csv")
        captured = capsys.readouterr()
        assert "NUMBER" in captured.out  # テーブルフォーマットにフォールバック

    def test_list_input(self, capsys):
        items = [
            SampleItem(1, "A", "open", "x"),
            SampleItem(2, "B", "closed", "y"),
        ]
        output(items, fmt="json")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
