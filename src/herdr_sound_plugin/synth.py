"""音符合成：把「音名 + 时长」的谱子渲染成 16bit PCM，并编码为 mp3。

只用标准库做合成，只有 mp3 编码一步依赖 `lameenc`（见 `encode_mp3`）。
"""

from __future__ import annotations

SR = 44100  # 采样率
FADE = 0.002  # 每个音符的淡入淡出时长（秒），用于消除爆音
DECAY = 0.85  # 音符衰减幅度：结束时保留 15% 音量，避免过于干硬

_BASE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
         "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def freq(note: str) -> float:
    """音名 -> 频率(Hz)，以 A4=440Hz 为基准。`"-"` 表示休止，返回 0.0。

    >>> round(freq("A4"), 2)
    440.0
    >>> round(freq("C5"), 2)
    523.25
    """
    if note == "-":
        return 0.0
    name, octave = note[:-1], int(note[-1])
    semitones = _BASE[name] + (octave - 4) * 12 - 9  # 相对 A4
    return 440.0 * 2 ** (semitones / 12)


def square(f: float, dur: float, vol: float = 0.42) -> bytes:
    """合成单个方波音符，返回 16bit 小端单声道 PCM 字节。

    方波是 8-bit 芯片音（chiptune）的招牌音色；`vol` 默认 0.42 留足余量，
    叠加多音也不会削顶。
    """
    n = max(1, int(SR * dur))
    if f <= 0:
        return bytes(n * 2)  # 休止
    fade = max(1, int(SR * FADE))
    period = SR / f
    out = bytearray()
    for i in range(n):
        s = 1.0 if (i % period) < period / 2 else -1.0
        env = 1.0 - DECAY * (i / n)
        if i < fade:
            env *= i / fade
        elif i > n - fade:
            env *= (n - i) / fade
        out += _pack(s, env, vol)
    return bytes(out)


def _pack(s: float, env: float, vol: float) -> bytes:
    import struct

    return struct.pack("<h", int(s * env * vol * 32767))


def render(notes: "list[tuple[str, float]]") -> bytes:
    """把谱子 `[("B5", 0.09), ("E6", 0.30)]` 渲染成连续 PCM。"""
    return b"".join(square(freq(note), dur) for note, dur in notes)


def duration(pcm: bytes) -> float:
    """PCM 时长（秒）。"""
    return len(pcm) / 2 / SR


def encode_mp3(pcm: bytes, bitrate: int = 128) -> bytes:
    """PCM -> mp3。

    herdr 只接受 `.mp3`（wav 会报 `unsupported sound file format ... expected an
    mp3 file`），而 macOS 自带的 afconvert 已不再提供 mp3 编码器，故用 lameenc。
    """
    import lameenc

    enc = lameenc.Encoder()
    enc.set_bit_rate(bitrate)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(2)
    return enc.encode(pcm) + enc.flush()


def is_mp3(data: bytes) -> bool:
    """粗查 mp3 帧同步头（MPEG-1 Layer III 首字节 0xFF）。"""
    return data[:1] == b"\xff"
