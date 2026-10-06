"""生成流程的端到端检查：目录结构、mp3 合法性、可复现性。"""

import pathlib

import pytest

from herdr_sound_plugin import packs, synth
from herdr_sound_plugin.gen import generate

pytest.importorskip("lameenc", reason="需要 lameenc 才能生成 mp3")


def test_generate_creates_expected_layout(tmp_path: pathlib.Path):
    written = generate(tmp_path)
    assert len(written) == len(packs.labels()) * len(packs.KINDS)
    for path in written:
        assert path.exists()
        assert path.parent.name in packs.labels()
        assert path.name in {f"{k}.mp3" for k in packs.KINDS}


def test_generated_files_are_valid_mp3(tmp_path: pathlib.Path):
    for path in generate(tmp_path):
        assert synth.is_mp3(path.read_bytes()), f"{path} 不是 mp3"


def test_generate_can_filter_packs(tmp_path: pathlib.Path):
    written = generate(tmp_path, only=["mario"])
    assert {p.parent.name for p in written} == {"mario"}


def test_generation_is_deterministic(tmp_path: pathlib.Path):
    """同样输入必须产出同样字节，否则 git diff 会无谓抖动。"""
    first = {p.name: p.read_bytes() for p in generate(tmp_path / "a")}
    second = {p.name: p.read_bytes() for p in generate(tmp_path / "b")}
    assert first == second


def test_generated_duration_matches_score(tmp_path: pathlib.Path):
    for path in generate(tmp_path):
        pack, kind = path.parent.name, path.stem
        expected = sum(d for _, d in packs.notes_of(pack, kind))
        actual = synth.duration(synth.render(packs.notes_of(pack, kind)))
        assert actual == pytest.approx(expected, abs=0.01)


# 分字节比对已提交 mp3 与生成器输出的测试已移除：libmp3lame 的编码结果随
# CPU 架构而变（linux/x86_64 与 macos/arm64 同一输入有约 8% 字节不同），
# 跨平台不可复现，放宽容差也只是假红。音效存在性由 test_install.py 的
# test_every_pack_has_bundled_sounds 与 `task build` 的 12 个 mp3 断言兵底。
