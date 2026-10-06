"""合成与编码的自检。

不需要 lameenc 的部分（音高、PCM 长度、波形形状）总是跑；
需要 lameenc 的编码断言在缺少依赖时自动跳过。
"""

import struct

import pytest

from herdr_sound_plugin import synth


def test_freq_uses_a4_440_as_reference():
    assert round(synth.freq("A4"), 2) == 440.0
    assert round(synth.freq("C5"), 2) == 523.25
    assert round(synth.freq("C4"), 2) == 261.63


def test_freq_doubles_each_octave():
    assert synth.freq("C6") == pytest.approx(synth.freq("C5") * 2)
    assert synth.freq("A3") == pytest.approx(220.0)


def test_freq_of_rest_is_zero():
    assert synth.freq("-") == 0.0


def test_square_length_matches_duration():
    for dur in (0.05, 0.25, 0.5):
        pcm = synth.square(440.0, dur)
        assert len(pcm) == int(synth.SR * dur) * 2  # 16bit 单声道


def test_square_stays_within_headroom():
    """默认音量下不应削顶（|sample| < 32767）。"""
    pcm = synth.square(440.0, 0.1)
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    assert max(abs(s) for s in samples) < 32767


def test_square_is_bipolar():
    """方波必须正负都有值，否则说明合成逻辑坏了。"""
    pcm = synth.square(440.0, 0.1)
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    assert any(s > 0 for s in samples) and any(s < 0 for s in samples)


def test_fade_in_ramps_up_from_silence():
    """淡入生效：开头极安静，峰值出现在淡入之后（默认淡入只有 2ms）。"""
    pcm = synth.square(440.0, 0.2)
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    assert abs(samples[0]) < 1000  # 第一个采样接近静音
    peak_at = max(range(len(samples)), key=lambda i: abs(samples[i]))
    assert peak_at > int(synth.SR * synth.FADE) - 1  # 峰值在淡入结束之后


def test_fade_out_at_the_end():
    """淡出生效：最后一个采样接近静音，不会以爆音收尾。"""
    pcm = synth.square(440.0, 0.2)
    samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    assert abs(samples[-1]) < 1000


def test_rest_produces_silence():
    pcm = synth.square(0.0, 0.1)
    assert pcm == bytes(len(pcm))
    assert set(pcm) == {0}


def test_render_concatenates_notes():
    notes = [("C5", 0.1), ("E5", 0.2)]
    pcm = synth.render(notes)
    assert len(pcm) == (int(synth.SR * 0.1) + int(synth.SR * 0.2)) * 2
    assert round(synth.duration(pcm), 2) == 0.30


def test_render_handles_rest():
    pcm = synth.render([("C5", 0.1), ("-", 0.1), ("E5", 0.1)])
    assert round(synth.duration(pcm), 2) == 0.30


def test_encode_mp3_has_frame_sync_header():
    lameenc = pytest.importorskip("lameenc", reason="需要 lameenc 才能编码")
    assert lameenc is not None  # 明确使用，避免被当成未使用导入
    data = synth.encode_mp3(synth.render([("C5", 0.1)]))
    assert synth.is_mp3(data)
    assert len(data) > 200


def test_is_mp3_rejects_non_mp3():
    assert not synth.is_mp3(b"not an mp3 at all")
    assert not synth.is_mp3(b"")
