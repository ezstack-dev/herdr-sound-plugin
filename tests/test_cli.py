"""CLI 层：命令输出与退出码。"""

import pathlib

import pytest
from typer.testing import CliRunner

from herdr_sound_plugin import __version__, config as cfg
from herdr_sound_plugin import install
from herdr_sound_plugin.cli import app

runner = CliRunner()


@pytest.fixture()
def env(tmp_path: pathlib.Path, monkeypatch) -> pathlib.Path:
    """隔离 herdr 配置目录，并让 reload 不真的去调 herdr。"""
    monkeypatch.setenv("HERDR_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr("herdr_sound_plugin.herdr.reload_config",
                        lambda: "reload: applied")
    return tmp_path


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("list", "use", "status", "doctor", "restore", "version"):
        assert command in result.stdout


def test_version_is_not_a_stale_literal():
    """版本号只有 pyproject 一处来源；这里挡住硬编码回归。"""
    major, minor, patch = __version__.split(".")[:3]
    assert major.isdigit() and minor.isdigit(), __version__
    assert __version__ != "0.0.0+unknown", "测试环境应能读到已安装的包元数据"
    assert patch.split("+")[0].isdigit(), __version__


def test_list_marks_nothing_when_inactive(env):
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "(no pack active)" in result.stdout
    for pack in ("mario", "zelda", "sonic", "tetris", "pacman", "ff"):
        assert pack in result.stdout


def test_use_then_list_marks_current(env):
    runner.invoke(app, ["use", "zelda"])
    result = runner.invoke(app, ["list"])
    assert "* zelda" in result.stdout
    assert "* mario" not in result.stdout


def test_use_reports_files_and_reload(env):
    result = runner.invoke(app, ["use", "mario"])
    assert result.exit_code == 0
    assert "已切换音色包：mario" in result.stdout
    assert "sounds/mario/done.mp3" in result.stdout
    assert "reload: applied" in result.stdout


def test_use_quiet_prints_nothing(env):
    result = runner.invoke(app, ["use", "mario", "--quiet"])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""


def test_use_rejects_unknown_pack(env):
    result = runner.invoke(app, ["use", "nope"])
    assert result.exit_code == 1
    assert "未知音色包" in result.output


def test_status_when_inactive(env):
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "无" in result.stdout


def test_status_shows_active_pack(env):
    install.use("sonic")
    result = runner.invoke(app, ["status"])
    assert "sonic" in result.stdout
    assert "sounds/sonic/done.mp3" in result.stdout


def test_status_warns_when_files_missing(env):
    install.use("mario")
    (env / "sounds" / "mario" / "done.mp3").unlink()
    result = runner.invoke(app, ["status"])
    assert "缺失" in result.output


def test_restore_needs_confirmation(env):
    install.use("mario")
    result = runner.invoke(app, ["restore"], input="n\n")
    assert result.exit_code != 0
    assert install.current_pack() == "mario", "拒绝确认时不该动配置"


def test_restore_yes_is_non_interactive(env):
    install.use("mario")
    result = runner.invoke(app, ["restore", "--yes"])
    assert result.exit_code == 0
    assert cfg.get_sound() == {"enabled": False}
    assert not (env / "sounds" / "mario").exists()


def test_doctor_ok_when_consistent(env, monkeypatch):
    monkeypatch.setattr("herdr_sound_plugin.herdr.resolve_binary", lambda: "/usr/bin/herdr")
    install.use("mario")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "[ok] herdr" in result.stdout


def test_doctor_fails_when_herdr_missing(env, monkeypatch):
    def explode():
        raise FileNotFoundError("找不到 herdr 可执行文件")

    monkeypatch.setattr("herdr_sound_plugin.herdr.resolve_binary", explode)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1


def test_doctor_fails_when_active_pack_files_missing(env, monkeypatch):
    monkeypatch.setattr("herdr_sound_plugin.herdr.resolve_binary", lambda: "/usr/bin/herdr")
    install.use("mario")
    (env / "sounds" / "mario" / "blocked.mp3").unlink()
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1


def test_version_matches_distribution_metadata():
    """`hsp version` 报的版本必须与分发包一致（别再手写第二份版本号）。"""
    from importlib.metadata import version

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == version("herdr-sound")
