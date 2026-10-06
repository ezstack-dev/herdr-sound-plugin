"""shell 脚本与插件清单的行为检查。

这几个断言对应的都是真踩过的坑，回归价值高：
  - 清单里的 action 列表必须和音色包一一对应（新增包忘了加 action）
  - notify.sh 对 done/blocked 播放不同文件，对其他状态静默
  - 状态文件缺失/非法时回退到 mario，而不是不响
  - 切包脚本拒绝未知包名并以非零退出
"""

import os
import pathlib
import shutil
import stat
import subprocess
import sys
import time
import tomllib

import pytest

from herdr_sound_plugin import packs

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN_ID = "mario-sound"


# ------------------------------------------------------------------ 夹具

@pytest.fixture
def fake_plugin(tmp_path: pathlib.Path) -> pathlib.Path:
    """一个最小可用的插件目录：拷脚本 + 造空的 sounds 结构。"""
    root = tmp_path / "plugin"
    root.mkdir()
    for name in ("notify.sh", "switch.sh"):
        shutil.copy(ROOT / name, root / name)
        (root / name).chmod(0o755)
    for pack in packs.labels():
        (root / "sounds" / pack).mkdir(parents=True)
        for kind in packs.KINDS:
            (root / "sounds" / pack / f"{kind}.mp3").write_bytes(b"\xff\xfb fake")
    return root


@pytest.fixture
def recorder(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """假的 afplay：把收到的文件路径追加到一个记录文件里。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "played.log"
    afplay = bin_dir / "afplay"
    afplay.write_text(f'#!/bin/bash\necho "$1" >> "{log}"\n')
    afplay.chmod(afplay.stat().st_mode | stat.S_IEXEC)
    return bin_dir, log


def run_script(script: pathlib.Path, *, root: pathlib.Path,
               state: "pathlib.Path | None" = None, env: "dict | None" = None,
               bin_dir: "pathlib.Path | None" = None) -> subprocess.CompletedProcess:
    full_env = {
        **os.environ,
        "HERDR_PLUGIN_ROOT": str(root),
        "HERDR_PLUGIN_STATE_DIR": str(state or (root / ".state")),
    }
    if bin_dir:
        full_env["PATH"] = f"{bin_dir}:{os.environ['PATH']}"
    full_env.update(env or {})
    return subprocess.run(["bash", str(script)], capture_output=True, text=True,
                          env=full_env, timeout=30)


def played(log: pathlib.Path, timeout: float = 5.0) -> "list[str]":
    """等后台 afplay 落盘后读记录（notify.sh 是异步播放的）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if log.exists() and log.read_text().strip():
            return log.read_text().split()
        time.sleep(0.05)
    return []


# ------------------------------------------------------------------ 清单

def test_manifest_action_per_pack():
    manifest = tomllib.loads((ROOT / "herdr-plugin.toml").read_text())
    action_ids = {a["id"] for a in manifest["actions"]}
    assert action_ids == {"list-sounds"} | {f"use-{p}" for p in packs.labels()}


def test_manifest_event_subscription():
    manifest = tomllib.loads((ROOT / "herdr-plugin.toml").read_text())
    events = manifest["events"]
    assert [e["on"] for e in events] == ["pane.agent_status_changed"]
    # command 必须是 argv 数组且经 bash 调用（相对路径不能直接执行，见 README）
    assert events[0]["command"] == ["bash", "notify.sh"]


def test_manifest_declares_plugin_id_consistently():
    manifest = tomllib.loads((ROOT / "herdr-plugin.toml").read_text())
    assert manifest["id"] == PLUGIN_ID
    # Python 侧的 herdr.py 里硬编码了插件 id，必须与清单一致
    sys.path.insert(0, str(ROOT / "src"))
    from herdr_sound_plugin import herdr

    assert herdr.PLUGIN_ID == manifest["id"]


def test_manifest_all_commands_are_argv_arrays():
    manifest = tomllib.loads((ROOT / "herdr-plugin.toml").read_text())
    for section in ("events", "actions"):
        for entry in manifest.get(section, []):
            cmd = entry["command"]
            assert isinstance(cmd, list) and cmd, f"{section}/{entry.get('id')} command 必须是数组"
            assert all(isinstance(part, str) for part in cmd)


# ------------------------------------------------------------------ notify.sh

@pytest.mark.parametrize(("status", "kind"), [("done", "done"), ("blocked", "blocked")])
def test_notify_plays_matching_sound(fake_plugin, recorder, status, kind):
    bin_dir, log = recorder
    state = fake_plugin / ".state"
    state.mkdir()
    (state / "pack").write_text("zelda\n")

    result = run_script(fake_plugin / "notify.sh", root=fake_plugin, state=state,
                        bin_dir=bin_dir,
                        env={"HERDR_PLUGIN_EVENT_JSON": f'{{"data":{{"agent_status":"{status}"}}}}'})
    assert result.returncode == 0
    assert played(log) == [str(fake_plugin / "sounds" / "zelda" / f"{kind}.mp3")]


@pytest.mark.parametrize("status", ["working", "idle", "unknown", ""])
def test_notify_silent_for_other_states(fake_plugin, recorder, status):
    bin_dir, log = recorder
    payload = f'{{"data":{{"agent_status":"{status}"}}}}' if status else "{}"
    result = run_script(fake_plugin / "notify.sh", root=fake_plugin, bin_dir=bin_dir,
                        env={"HERDR_PLUGIN_EVENT_JSON": payload})
    assert result.returncode == 0
    assert played(log, timeout=0.5) == []


def test_notify_falls_back_to_default_pack(fake_plugin, recorder):
    """状态文件缺失时回退 mario——不能变成哑巴。"""
    bin_dir, log = recorder
    result = run_script(fake_plugin / "notify.sh", root=fake_plugin, bin_dir=bin_dir,
                        env={"HERDR_PLUGIN_EVENT_JSON": '{"data":{"agent_status":"done"}}'})
    assert result.returncode == 0
    assert played(log) == [str(fake_plugin / "sounds" / "mario" / "done.mp3")]


def test_notify_falls_back_when_pack_is_invalid(fake_plugin, recorder):
    bin_dir, log = recorder
    state = fake_plugin / ".state"
    state.mkdir()
    (state / "pack").write_text("no-such-pack\n")
    result = run_script(fake_plugin / "notify.sh", root=fake_plugin, state=state,
                        bin_dir=bin_dir,
                        env={"HERDR_PLUGIN_EVENT_JSON": '{"data":{"agent_status":"done"}}'})
    assert result.returncode == 0
    assert played(log) == [str(fake_plugin / "sounds" / "mario" / "done.mp3")]


def test_notify_tolerates_missing_file(fake_plugin, recorder):
    """sounds/ 被删空时不能报错（herdr 会把非零退出记成失败）。"""
    bin_dir, _ = recorder
    shutil.rmtree(fake_plugin / "sounds")
    result = run_script(fake_plugin / "notify.sh", root=fake_plugin, bin_dir=bin_dir,
                        env={"HERDR_PLUGIN_EVENT_JSON": '{"data":{"agent_status":"done"}}'})
    assert result.returncode == 0


# ------------------------------------------------------------------ switch.sh

def test_switch_sets_pack(fake_plugin):
    state = fake_plugin / ".state"
    result = run_script(fake_plugin / "switch.sh", root=fake_plugin, state=state,
                        env={"HERDR_PLUGIN_ACTION_ID": "use-sonic"})
    assert result.returncode == 0
    assert (state / "pack").read_text().strip() == "sonic"
    assert "sonic" in result.stdout


def test_switch_rejects_unknown_pack(fake_plugin):
    state = fake_plugin / ".state"
    result = run_script(fake_plugin / "switch.sh", root=fake_plugin, state=state,
                        env={"HERDR_PLUGIN_ACTION_ID": "use-nope"})
    assert result.returncode != 0
    assert "Unknown sound pack" in result.stderr
    assert not (state / "pack").exists()


def test_switch_list_shows_all_packs(fake_plugin):
    result = run_script(fake_plugin / "switch.sh", root=fake_plugin,
                        env={"HERDR_PLUGIN_ACTION_ID": "list-sounds"})
    assert result.returncode == 0
    for pack in packs.labels():
        assert pack in result.stdout


def test_switch_defaults_to_listing(fake_plugin):
    """HERDR_PLUGIN_ACTION_ID 缺失时按「列出来」处理，不误改状态。"""
    result = run_script(fake_plugin / "switch.sh", root=fake_plugin)
    assert result.returncode == 0
    assert "Available sound packs" in result.stdout
