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
    """包内已提交的 sounds/ 必须能由生成器复现（防止手改 mp3）。

    这里不要求字节全等：libmp3lame 在不同 CPU 架构上会对个别量化决策取不同
    分支，实测 Linux/x86_64 与 macOS/arm64 之间有 1 个字节不同（差 1 bit），
    而这 1 bit 只来自编码器，谱子与 PCM 输入是逐字节相同的。若要求全等，
    仓库里由 macOS 生成的 mp3 在 Linux CI 上必然失败。
    手改音频（换音源、改音量、截断）会大面积改动字节，仍会被拦下。
    """
    repo_sounds = (pathlib.Path(__file__).resolve().parents[1]
                   / "src" / "herdr_sound_plugin" / "sounds")
    if not repo_sounds.exists():
        pytest.skip("仓库里还没有 sounds/ 目录")
    fresh = {p.relative_to(tmp_path): p.read_bytes() for p in generate(tmp_path)}
    for rel, data in fresh.items():
        committed = repo_sounds / rel
        assert committed.exists(), f"缺少已提交的音效文件 {rel}"
        got = committed.read_bytes()
        assert len(got) == len(data), (
            f"{rel} 长度不一致（{len(got)} vs {len(data)}），请重新生成")
        diff = sum(1 for a, b in zip(got, data) if a != b)
        assert diff / len(data) < 0.005, (
            f"{rel} 有 {diff}/{len(data)} 字节与生成器输出不同，请重新生成")
