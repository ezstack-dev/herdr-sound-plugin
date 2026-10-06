"""config.toml 读写：只碰 `[ui.sound]`，其余原样保留。"""

import pathlib

import pytest

from herdr_sound_plugin import config as cfg


@pytest.fixture()
def config_file(tmp_path: pathlib.Path) -> pathlib.Path:
    """一份带注释、带其它段落的真实形状配置。"""
    path = tmp_path / "config.toml"
    path.write_text(
        'onboarding = false\n'
        '\n'
        '[ui.toast]\n'
        'delivery = "terminal"   # 用户的注释不能被抹掉\n'
        '\n'
        '[ui]\n'
        'status_indicators = "dots"\n',
        encoding="utf-8",
    )
    return path


def test_config_path_prefers_env(tmp_path, monkeypatch):
    target = tmp_path / "custom.toml"
    monkeypatch.setenv("HERDR_CONFIG_PATH", str(target))
    assert cfg.config_path() == target


def test_config_path_uses_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("HERDR_CONFIG_PATH", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert cfg.config_path() == tmp_path / "herdr" / "config.toml"


def test_config_path_defaults_to_dot_config(tmp_path, monkeypatch):
    monkeypatch.delenv("HERDR_CONFIG_PATH", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(cfg.pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    assert cfg.config_path() == tmp_path / ".config" / "herdr" / "config.toml"


def test_sound_dir_sits_next_to_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HERDR_CONFIG_PATH", str(tmp_path / "config.toml"))
    assert cfg.sound_dir() == tmp_path / "sounds"


def test_read_missing_file_is_empty(tmp_path):
    assert cfg.read(tmp_path / "nope.toml") == {}


def test_get_sound_without_section(config_file):
    assert cfg.get_sound(config_file) == {}


def test_set_paths_creates_section_and_keeps_everything_else(config_file):
    cfg.set_paths("sounds/mario/done.mp3", "sounds/mario/blocked.mp3", config=config_file)
    text = config_file.read_text(encoding="utf-8")
    assert "# 用户的注释不能被抹掉" in text, "tomlkit 应保留注释"
    assert 'status_indicators = "dots"' in text
    assert cfg.get_sound(config_file) == {
        "enabled": True,
        "done_path": "sounds/mario/done.mp3",
        "request_path": "sounds/mario/blocked.mp3",
    }


def test_set_paths_on_missing_file(tmp_path):
    path = tmp_path / "config.toml"
    cfg.set_paths("sounds/ff/done.mp3", "sounds/ff/blocked.mp3", config=path)
    assert cfg.get_sound(path)["done_path"] == "sounds/ff/done.mp3"


def test_set_paths_is_idempotent(config_file):
    cfg.set_paths("a", "b", config=config_file)
    once = config_file.read_text(encoding="utf-8")
    cfg.set_paths("a", "b", config=config_file)
    assert config_file.read_text(encoding="utf-8") == once


def test_set_paths_can_override_existing_section(config_file):
    cfg.set_paths("sounds/mario/done.mp3", "sounds/mario/blocked.mp3", config=config_file)
    cfg.set_paths("sounds/zelda/done.mp3", "sounds/zelda/blocked.mp3", config=config_file)
    section = cfg.get_sound(config_file)
    assert section["done_path"] == "sounds/zelda/done.mp3"
    assert cfg.get_sound(config_file).get("path") is None


def test_unset_removes_paths_and_disables(config_file):
    cfg.set_paths("sounds/mario/done.mp3", "sounds/mario/blocked.mp3", config=config_file)
    cfg.unset(config_file)
    section = cfg.get_sound(config_file)
    assert section == {"enabled": False}
    assert 'delivery = "terminal"' in config_file.read_text(encoding="utf-8")


def test_unset_without_section_is_noop(config_file):
    before = config_file.read_text(encoding="utf-8")
    cfg.unset(config_file)
    assert config_file.read_text(encoding="utf-8") == before
