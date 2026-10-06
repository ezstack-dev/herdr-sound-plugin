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


def test_committed_sounds_match_generator(tmp_path: pathlib.Path):
    """仓库里已提交的 sounds/ 必须与生成器的输出一致（防止手改 mp3）。"""
    repo_sounds = pathlib.Path(__file__).resolve().parents[1] / "sounds"
    if not repo_sounds.exists():
        pytest.skip("仓库里还没有 sounds/ 目录")
    fresh = {p.relative_to(tmp_path): p.read_bytes() for p in generate(tmp_path)}
    for rel, data in fresh.items():
        committed = repo_sounds / rel
        assert committed.exists(), f"缺少已提交的音效文件 {rel}"
        assert committed.read_bytes() == data, f"{rel} 与生成器输出不一致，请重新生成"
