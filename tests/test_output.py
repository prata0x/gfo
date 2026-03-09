"""output.py のテスト。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from gfo.output import format_json, format_plain, format_table, output, _display_width


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

    def test_newline_in_title_sanitized(self):
        """タイトルに改行が含まれる場合、テーブル表示用にエスケープされる。"""
        result = format_table(
            [SampleItem(1, "line1\nline2", "open", "alice")],
            ["number", "title"],
        )
        assert "\\n" in result
        assert "\n" not in result.split("\n")[2]  # データ行に生の改行なし

    def test_tab_in_title_replaced_with_space(self):
        """タイトルにタブが含まれる場合、テーブル表示ではスペースに置換される。"""
        result = format_table(
            [SampleItem(1, "col1\tcol2", "open", "alice")],
            ["number", "title"],
        )
        data_row = result.split("\n")[2]
        assert "\t" not in data_row

    def test_multibyte_title_width(self):
        """日本語タイトルの表示幅は文字数の2倍として計算される。"""
        assert _display_width("日本語") == 6

    def test_multibyte_column_alignment(self):
        """日本語タイトルを含む行が正しく整列される。"""
        items = [
            SampleItem(1, "日本語タイトル", "open", "alice"),
            SampleItem(2, "English", "closed", "bob"),
        ]
        result = format_table(items, ["number", "title"])
        lines = result.split("\n")
        # セパレーター行の幅は日本語タイトルの表示幅(12)以上
        assert len(lines[1].split("  ")[1]) >= 12


class TestFormatJson:
    def test_single_item_is_array(self):
        """単一アイテムでも JSON 配列として出力される。"""
        result = format_json([SampleItem(1, "Fix typo", "open", "alice")])
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["number"] == 1

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
        item = parsed[0] if isinstance(parsed, list) else parsed
        assert item["value"] is None


class TestFormatPlain:
    def test_tab_separated(self):
        result = format_plain(
            [SampleItem(1, "Fix typo", "open", "alice")],
            ["number", "title", "state", "author"],
        )
        assert result == "1\tFix typo\topen\talice"

    def test_tab_in_value_escaped(self):
        """値にタブが含まれる場合は \\t にエスケープされる。"""
        result = format_plain(
            [SampleItem(1, "col1\tcol2", "open", "alice")],
            ["number", "title"],
        )
        fields = result.split("\t")
        assert len(fields) == 2  # 区切りの \t のみ、値内の \t はエスケープ済み
        assert "\\t" in fields[1]

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
        """空リストは table 形式で stdout に 'No results found.' を出力する。"""
        output([])
        captured = capsys.readouterr()
        assert "No results found." in captured.out
        assert captured.err == ""

    def test_empty_list_json_outputs_brackets(self, capsys):
        """空リストを json フォーマットで出力すると '[]' が stdout に出る。"""
        output([], fmt="json")
        captured = capsys.readouterr()
        assert captured.out.strip() == "[]"

    def test_json_fmt(self, capsys):
        output(SampleItem(1, "Fix typo", "open", "alice"), fmt="json")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        item = parsed[0] if isinstance(parsed, list) else parsed
        assert item["number"] == 1

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
