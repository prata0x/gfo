"""gfo.commands.config_cmd のテスト。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gfo.commands import config_cmd
from gfo.config import load_user_config
from gfo.exceptions import ConfigError
from tests.test_commands.conftest import make_args


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """一時的な設定ディレクトリ。"""
    d = tmp_path / "gfo_config"
    d.mkdir()
    with patch("gfo.config.get_config_dir", return_value=d):
        yield d


def _write_config(config_dir: Path, content: str) -> None:
    """テスト用の config.toml を書き込む。"""
    (config_dir / "config.toml").write_text(content, encoding="utf-8")


class TestHandleGet:
    """handle_get のテスト。"""

    def test_get_existing_key(self, config_dir, capsys):
        """既存キーの値を取得。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\n')
        args = make_args(key="defaults.output")
        config_cmd.handle_get(args, fmt="table")
        assert capsys.readouterr().out.strip() == "json"

    def test_get_nested_key(self, config_dir, capsys):
        """引用符記法でドット含みキーの値を取得。"""
        _write_config(config_dir, '[hosts."gitlab.example.com"]\ntype = "gitlab"\n')
        args = make_args(key='hosts."gitlab.example.com".type')
        config_cmd.handle_get(args, fmt="table")
        assert capsys.readouterr().out.strip() == "gitlab"

    def test_get_missing_key(self, config_dir):
        """存在しないキー → ConfigError。"""
        _write_config(config_dir, '[defaults]\noutput = "table"\n')
        args = make_args(key="defaults.nonexistent")
        with pytest.raises(ConfigError, match="Key not found"):
            config_cmd.handle_get(args, fmt="table")

    def test_get_json_format(self, config_dir, capsys):
        """fmt=json で JSON 出力。"""
        _write_config(config_dir, '[defaults]\noutput = "plain"\n')
        args = make_args(key="defaults.output")
        config_cmd.handle_get(args, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert result == {"key": "defaults.output", "value": "plain"}

    def test_get_empty_config(self, config_dir):
        """空の config → ConfigError。"""
        args = make_args(key="defaults.output")
        with pytest.raises(ConfigError, match="Key not found"):
            config_cmd.handle_get(args, fmt="table")

    def test_get_table_value(self, config_dir, capsys):
        """テーブル値を取得すると dict が返る。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\nhost = "github.com"\n')
        args = make_args(key="defaults")
        config_cmd.handle_get(args, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert result["value"] == {"output": "json", "host": "github.com"}


class TestHandleSet:
    """handle_set のテスト。"""

    def test_set_new_key(self, config_dir, capsys):
        """新しいキーを設定。"""
        args = make_args(key="defaults.output", value="json")
        config_cmd.handle_set(args, fmt="table")
        cfg = load_user_config()
        assert cfg["defaults"]["output"] == "json"
        # table フォーマットでは出力なし
        assert capsys.readouterr().out == ""

    def test_set_overwrites_existing(self, config_dir):
        """既存キーを上書き。"""
        _write_config(config_dir, '[defaults]\noutput = "table"\n')
        args = make_args(key="defaults.output", value="json")
        config_cmd.handle_set(args, fmt="table")
        cfg = load_user_config()
        assert cfg["defaults"]["output"] == "json"

    def test_set_creates_intermediate_tables(self, config_dir):
        """中間テーブルが自動作成される。"""
        args = make_args(key="hosts.myhost.type", value="gitlab")
        config_cmd.handle_set(args, fmt="table")
        cfg = load_user_config()
        assert cfg["hosts"]["myhost"]["type"] == "gitlab"

    def test_set_dotted_host_key(self, config_dir):
        """引用符記法でドット含みキーに値を設定できる。"""
        args = make_args(key='hosts."gitlab.example.com".type', value="gitlab")
        config_cmd.handle_set(args, fmt="table")
        cfg = load_user_config()
        assert cfg["hosts"]["gitlab.example.com"]["type"] == "gitlab"

    def test_set_json_format(self, config_dir, capsys):
        """fmt=json で JSON 出力。"""
        args = make_args(key="defaults.output", value="plain")
        config_cmd.handle_set(args, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert result == {"key": "defaults.output", "value": "plain"}

    def test_set_preserves_existing_values(self, config_dir):
        """既存の別キーが保持される。"""
        _write_config(config_dir, '[defaults]\noutput = "table"\nhost = "github.com"\n')
        args = make_args(key="defaults.output", value="json")
        config_cmd.handle_set(args, fmt="table")
        cfg = load_user_config()
        assert cfg["defaults"]["output"] == "json"
        assert cfg["defaults"]["host"] == "github.com"

    def test_set_single_part_key_error(self, config_dir):
        """単一パートのキー → ConfigError。"""
        args = make_args(key="output", value="json")
        with pytest.raises(ConfigError, match="at least two parts"):
            config_cmd.handle_set(args, fmt="table")

    def test_set_conflict_with_scalar(self, config_dir):
        """スカラー値のパスにテーブルを作ろうとすると ConfigError。"""
        _write_config(config_dir, '[defaults]\noutput = "table"\n')
        args = make_args(key="defaults.output.nested", value="x")
        with pytest.raises(ConfigError, match="not a table"):
            config_cmd.handle_set(args, fmt="table")


class TestHandleList:
    """handle_list のテスト。"""

    def test_list_empty(self, config_dir, capsys):
        """空の設定 → 「No configuration set.」メッセージ。"""
        args = make_args()
        config_cmd.handle_list(args, fmt="table")
        assert "No configuration set" in capsys.readouterr().out

    def test_list_flat_values(self, config_dir, capsys):
        """フラットな設定値を一覧表示。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\nhost = "github.com"\n')
        args = make_args()
        config_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "defaults.output=json" in out
        assert "defaults.host=github.com" in out

    def test_list_nested_values(self, config_dir, capsys):
        """ネストされた設定値を一覧表示（ドット含みキーは引用符付き）。"""
        _write_config(
            config_dir,
            '[defaults]\noutput = "table"\n\n[hosts."gitlab.example.com"]\ntype = "gitlab"\n',
        )
        args = make_args()
        config_cmd.handle_list(args, fmt="table")
        out = capsys.readouterr().out
        assert "defaults.output=table" in out
        assert 'hosts."gitlab.example.com".type=gitlab' in out

    def test_list_json_format(self, config_dir, capsys):
        """fmt=json で JSON 出力。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\n')
        args = make_args()
        config_cmd.handle_list(args, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert result == {"defaults": {"output": "json"}}

    def test_list_json_empty(self, config_dir, capsys):
        """空の設定で JSON 出力。"""
        args = make_args()
        config_cmd.handle_list(args, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert result == {}


class TestHandleUnset:
    """handle_unset のテスト。"""

    def test_unset_existing_key(self, config_dir):
        """既存キーを削除。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\nhost = "github.com"\n')
        args = make_args(key="defaults.output")
        config_cmd.handle_unset(args, fmt="table")
        cfg = load_user_config()
        assert "output" not in cfg.get("defaults", {})
        # host は残っている
        assert cfg["defaults"]["host"] == "github.com"

    def test_unset_removes_empty_parent(self, config_dir):
        """最後のキーを削除すると親テーブルも削除される。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\n')
        args = make_args(key="defaults.output")
        config_cmd.handle_unset(args, fmt="table")
        cfg = load_user_config()
        assert "defaults" not in cfg

    def test_unset_missing_key(self, config_dir):
        """存在しないキー → ConfigError。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\n')
        args = make_args(key="defaults.nonexistent")
        with pytest.raises(ConfigError, match="Key not found"):
            config_cmd.handle_unset(args, fmt="table")

    def test_unset_json_format(self, config_dir, capsys):
        """fmt=json で JSON 出力。"""
        _write_config(config_dir, '[defaults]\noutput = "json"\n')
        args = make_args(key="defaults.output")
        config_cmd.handle_unset(args, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert result == {"key": "defaults.output", "removed": True}

    def test_unset_single_part_key_error(self, config_dir):
        """単一パートのキー → ConfigError。"""
        args = make_args(key="output")
        with pytest.raises(ConfigError, match="at least two parts"):
            config_cmd.handle_unset(args, fmt="table")


class TestHandlePath:
    """handle_path のテスト。"""

    def test_path_table(self, config_dir, capsys):
        """パスが出力される。"""
        args = make_args()
        config_cmd.handle_path(args, fmt="table")
        out = capsys.readouterr().out.strip()
        assert "config.toml" in out

    def test_path_json(self, config_dir, capsys):
        """fmt=json で JSON 出力。"""
        args = make_args()
        config_cmd.handle_path(args, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert "path" in result
        assert "config.toml" in result["path"]


class TestConfigRoundtrip:
    """set → get → list → unset のラウンドトリップテスト。"""

    def test_full_roundtrip(self, config_dir, capsys):
        """set → get → list → unset が正しく動作する。"""
        # set
        config_cmd.handle_set(make_args(key="defaults.output", value="json"), fmt="table")
        config_cmd.handle_set(make_args(key="defaults.host", value="github.com"), fmt="table")

        # get
        config_cmd.handle_get(make_args(key="defaults.output"), fmt="table")
        assert capsys.readouterr().out.strip() == "json"

        config_cmd.handle_get(make_args(key="defaults.host"), fmt="table")
        assert capsys.readouterr().out.strip() == "github.com"

        # list
        config_cmd.handle_list(make_args(), fmt="table")
        out = capsys.readouterr().out
        assert "defaults.output=json" in out
        assert "defaults.host=github.com" in out

        # unset
        config_cmd.handle_unset(make_args(key="defaults.output"), fmt="table")
        with pytest.raises(ConfigError, match="Key not found"):
            config_cmd.handle_get(make_args(key="defaults.output"), fmt="table")

        # host はまだ残っている
        config_cmd.handle_get(make_args(key="defaults.host"), fmt="table")
        assert capsys.readouterr().out.strip() == "github.com"

    def test_list_output_usable_as_get_key(self, config_dir, capsys):
        """list 出力のキーをそのまま get に渡せる。"""
        _write_config(
            config_dir,
            '[hosts."gitlab.example.com"]\ntype = "gitlab"\n',
        )
        # list でキーを取得
        config_cmd.handle_list(make_args(), fmt="table")
        line = capsys.readouterr().out.strip()
        key_from_list = line.split("=", 1)[0]
        # そのキーで get できる
        config_cmd.handle_get(make_args(key=key_from_list), fmt="table")
        assert capsys.readouterr().out.strip() == "gitlab"
