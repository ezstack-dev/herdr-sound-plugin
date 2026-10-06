"""install：音效落到 herdr 侧、切换、卸载。"""

import pathlib

import pytest

from herdr_sound_plugin import config as cfg
from herdr_sound_plugin import install, packs


@pytest.fixture()
def env(tmp_path: pathlib.Path, monkeypatch) -> pathlib.Path:
    """把 herdr 配置目录指到临时目录，避免污染真机配置。"""
    monkeypatch.setenv("HERDR_CONFIG_PATH", str(tmp_path / "config.toml"))
    return tmp_path


def test_every_pack_has_bundled_sounds():
    for pack in packs.labels():
        for kind in packs.KINDS:
            path = install.source_file(pack, kind)
            assert path.exists(), f"包内缺 {pack}/{kind}.mp3"
            assert path.stat().st_size > 1000, f"{pack}/{kind}.mp3 太小，不像是真音频"


def test_source_file_rejects_unknown_pack():
    with pytest.raises(KeyError):
        install.source_file("nope", "done")


def test_rel_path_matches_herdr_layout():
    assert install.rel_path("mario", "done") == "sounds/mario/done.mp3"
    assert install.rel_path("ff", "blocked") == "sounds/ff/blocked.mp3"


def test_copy_sounds_places_both_kinds(env):
    copied = install.copy_sounds("mario")
    assert set(copied) == set(packs.KINDS)
    for kind, target in copied.items():
        assert target == env / "sounds" / "mario" / f"{kind}.mp3"
        assert target.read_bytes() == install.source_file("mario", kind).read_bytes()


def test_use_writes_config_and_files(env):
    result = install.use("zelda")
    assert result["pack"] == "zelda"
    assert cfg.get_sound() == {
        "enabled": True,
        "done_path": "sounds/zelda/done.mp3",
        "request_path": "sounds/zelda/blocked.mp3",
    }
    assert (env / "sounds" / "zelda" / "done.mp3").exists()


def test_use_rejects_unknown_pack(env):
    with pytest.raises(KeyError):
        install.use("nope")


def test_use_switches_between_packs(env):
    install.use("mario")
    install.use("sonic")
    assert install.current_pack() == "sonic"
    assert (env / "sounds" / "mario" / "done.mp3").exists(), "旧包文件保留，便于来回切"


def test_current_pack_reads_back(env):
    install.use("tetris")
    assert install.current_pack() == "tetris"


def test_current_pack_none_when_disabled(env):
    install.use("mario")
    cfg.set_paths("sounds/mario/done.mp3", "sounds/mario/blocked.mp3",
                  enabled=False, config=cfg.config_path())
    assert install.current_pack() is None


def test_current_pack_none_for_foreign_path(env):
    """用户自己手写的路径不该被误认成我们的包。"""
    cfg.set_paths("/abs/somewhere/done.mp3", "sounds/request.mp3", config=cfg.config_path())
    assert install.current_pack() is None


def test_current_pack_none_when_unset(env):
    assert install.current_pack() is None


def test_installed_packs_lists_complete_ones_only(env):
    install.use("mario")
    install.use("ff")
    (env / "sounds" / "sonic").mkdir(parents=True)  # 半成品目录
    assert install.installed_packs() == ["ff", "mario"]


def test_uninstall_removes_copied_dirs_and_disables(env):
    install.use("mario")
    install.use("ff")
    removed = install.uninstall()
    assert [p.name for p in removed] == ["ff", "mario"]
    assert not (env / "sounds" / "mario").exists()
    assert cfg.get_sound() == {"enabled": False}


def test_uninstall_keeps_foreign_files(env):
    """herdr 自带的 sounds/ 文件不能被删掉。"""
    install.use("mario")
    stray = env / "sounds" / "notification.mp3"
    stray.write_bytes(b"x")
    install.uninstall()
    assert stray.exists()
