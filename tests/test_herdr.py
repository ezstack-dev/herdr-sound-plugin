"""`herdr.py` 封装里的纯逻辑（不依赖真的 herdr 在跑）。"""

import json
import pathlib
import subprocess

import pytest

from herdr_sound_plugin import capture, herdr


def test_resolve_binary_prefers_env(tmp_path: pathlib.Path, monkeypatch):
    fake = tmp_path / "herdr"
    fake.write_text("#!/bin/bash\necho hi\n")
    monkeypatch.setenv("HERDR_BIN_PATH", str(fake))
    assert herdr.resolve_binary() == str(fake)


def test_resolve_binary_ignores_stale_env(tmp_path: pathlib.Path, monkeypatch):
    """环境变量指向不存在的文件时要继续往下找，而不是直接失败。"""
    monkeypatch.setenv("HERDR_BIN_PATH", str(tmp_path / "nope"))
    monkeypatch.setattr(herdr.shutil, "which", lambda _: "/found/herdr")
    assert herdr.resolve_binary() == "/found/herdr"


def test_resolve_binary_raises_when_missing(monkeypatch):
    monkeypatch.delenv("HERDR_BIN_PATH", raising=False)
    monkeypatch.setattr(herdr.shutil, "which", lambda _: None)
    monkeypatch.setattr(herdr.os.path, "exists", lambda _: False)
    with pytest.raises(FileNotFoundError):
        herdr.resolve_binary()


def _fake_call(monkeypatch, stdout: str, returncode: int = 0, stderr: str = ""):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=returncode,
                                           stdout=stdout, stderr=stderr)
    monkeypatch.setattr(herdr.subprocess, "run", run)


def test_call_parses_json_envelope(monkeypatch):
    _fake_call(monkeypatch, '{"id":"x","result":{"ok":true}}')
    assert herdr.call("pane", "list")["result"]["ok"] is True


def test_call_raises_on_failure(monkeypatch):
    _fake_call(monkeypatch, "", returncode=1, stderr="boom")
    with pytest.raises(RuntimeError, match="boom"):
        herdr.call("pane", "list")


def test_call_wraps_non_json_output(monkeypatch):
    """有的子命令输出纯文本，不应炸掉。"""
    _fake_call(monkeypatch, "just text")
    assert herdr.call("status")["raw"] == "just text"


def test_pane_status_finds_pane(monkeypatch):
    payload = {"result": {"panes": [{"pane_id": "w1:p2", "agent_status": "done"}]}}
    monkeypatch.setattr(herdr, "call", lambda *a, **k: payload)
    assert herdr.pane_status("w1:p2") == "done"


def test_pane_status_normalises_null(monkeypatch):
    payload = {"result": {"panes": [{"pane_id": "w1:p2", "agent_status": None}]}}
    monkeypatch.setattr(herdr, "call", lambda *a, **k: payload)
    assert herdr.pane_status("w1:p2") == "unknown"


def test_pane_status_raises_for_unknown_pane(monkeypatch):
    monkeypatch.setattr(herdr, "call", lambda *a, **k: {"result": {"panes": []}})
    with pytest.raises(KeyError):
        herdr.pane_status("w9:p9")


def test_wait_done_returns_none_on_timeout(monkeypatch):
    monkeypatch.setattr(herdr, "pane_status", lambda *a, **k: "working")
    monkeypatch.setattr(herdr.time, "sleep", lambda _: None)
    assert herdr.wait_done("w1:p1", timeout=0.01) is None


def test_wait_done_returns_status_when_reached(monkeypatch):
    monkeypatch.setattr(herdr, "pane_status", lambda *a, **k: "done")
    assert herdr.wait_done("w1:p1", timeout=5) == "done"


def test_use_pack_builds_action_id(monkeypatch):
    seen = {}

    def fake(*args, **kw):
        seen["args"] = args
        return {}

    monkeypatch.setattr(herdr, "call", fake)
    herdr.use_pack("zelda")
    assert seen["args"] == ("plugin", "action", "invoke", f"{herdr.PLUGIN_ID}.use-zelda")


# ------------------------------------------------------------------ capture

def test_capture_extracts_sound_paths(tmp_path: pathlib.Path):
    log = tmp_path / "hits.log"
    log.write_text(
        "afplay /opt/p/sounds/mario/done.mp3\n"
        "afplay /opt/p/sounds/mario/done.mp3\n"
        "afplay /opt/p/sounds/ff/blocked.mp3\n"
        "some unrelated line\n"
    )
    assert capture.files(log) == {"sounds/mario/done.mp3": 2, "sounds/ff/blocked.mp3": 1}


def test_capture_handles_missing_log(tmp_path: pathlib.Path):
    assert capture.files(tmp_path / "nope.log") == {}


def test_capture_sample_parses_ps_output(monkeypatch):
    calls = {"n": 0}

    def run(cmd, **kwargs):
        calls["n"] += 1
        out = "123\n456\n" if cmd[0] == "pgrep" else "afplay /x/sounds/mario/done.mp3\n"
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=out, stderr="")

    monkeypatch.setattr(capture.subprocess, "run", run)
    lines = capture.sample()
    assert lines == ["afplay /x/sounds/mario/done.mp3"] * 2
