"""herdr 二进制封装的单元测试（不真的调用 herdr）。"""

import json
import pathlib
import subprocess

import pytest

from herdr_sound_plugin import herdr


def test_resolve_binary_prefers_env(tmp_path: pathlib.Path, monkeypatch):
    fake = tmp_path / "herdr"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setenv("HERDR_BIN_PATH", str(fake))
    assert herdr.resolve_binary() == str(fake)


def test_resolve_binary_ignores_stale_env(tmp_path: pathlib.Path, monkeypatch):
    """HERDR_BIN_PATH 指向不存在的文件时应继续往 PATH 里找。"""
    monkeypatch.setenv("HERDR_BIN_PATH", str(tmp_path / "nope"))
    monkeypatch.setattr(herdr.shutil, "which", lambda _: "/usr/bin/herdr")
    assert herdr.resolve_binary() == "/usr/bin/herdr"


def test_resolve_binary_raises_when_missing(monkeypatch):
    monkeypatch.delenv("HERDR_BIN_PATH", raising=False)
    monkeypatch.setattr(herdr.shutil, "which", lambda _: None)
    monkeypatch.setattr(herdr.os.path, "exists", lambda _: False)
    with pytest.raises(FileNotFoundError):
        herdr.resolve_binary()


def _fake_call(monkeypatch, stdout: str, returncode: int = 0, stderr: str = ""):
    """把 subprocess.run 换掉，返回一个假的 CompletedProcess。"""
    monkeypatch.setattr(herdr, "resolve_binary", lambda: "herdr")

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)

    monkeypatch.setattr(herdr.subprocess, "run", fake_run)


def test_call_parses_json_envelope(monkeypatch):
    _fake_call(monkeypatch, json.dumps({"id": "x", "result": {"status": "applied"}}))
    assert herdr.call("server", "reload-config")["result"]["status"] == "applied"


def test_call_raises_on_failure(monkeypatch):
    _fake_call(monkeypatch, "", returncode=1, stderr="boom")
    with pytest.raises(RuntimeError, match="boom"):
        herdr.call("nope")


def test_call_wraps_non_json_output(monkeypatch):
    _fake_call(monkeypatch, "not json at all")
    assert herdr.call("mystery") == {"raw": "not json at all"}


def test_call_stringifies_int_args(monkeypatch):
    """`--limit 200` 这种 int 参数不能把 subprocess 弄崩。"""
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(herdr, "resolve_binary", lambda: "herdr")
    monkeypatch.setattr(herdr.subprocess, "run", fake_run)
    herdr.call("plugin", "log", "list", "--limit", 200)
    assert seen["cmd"] == ["herdr", "plugin", "log", "list", "--limit", "200"]


def test_reload_config_reports_status(monkeypatch):
    _fake_call(monkeypatch, json.dumps({"result": {"status": "applied"}}))
    assert "applied" in herdr.reload_config()


def test_reload_config_tolerates_server_down(monkeypatch):
    """server 没跑时不该抛异常，只提示下次启动生效。"""
    _fake_call(monkeypatch, "", returncode=1, stderr="no server")
    message = herdr.reload_config()
    assert "下次启动时生效" in message
