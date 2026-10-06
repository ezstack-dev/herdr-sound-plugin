"""音色包的完整性约束。

这些断言保证「新增一个包」不会漏掉某个用途，也保证文件能被 notify.sh 找到。
"""

from herdr_sound_plugin import packs

EXPECTED = {"mario", "zelda", "sonic", "tetris", "pacman", "ff"}


def test_expected_packs_present():
    assert EXPECTED <= set(packs.labels())


def test_labels_are_sorted():
    assert packs.labels() == sorted(packs.PACKS)


def test_every_pack_defines_every_kind():
    for pack in packs.labels():
        for kind in packs.KINDS:
            notes = packs.notes_of(pack, kind)
            assert notes, f"{pack}/{kind} 是空的"


def test_unknown_pack_or_kind_raises():
    import pytest

    with pytest.raises(KeyError):
        packs.notes_of("nope", "done")
    with pytest.raises(KeyError):
        packs.notes_of("mario", "nope")


def test_notes_are_well_formed():
    valid = set("ABCDEFG") | {"C#", "D#", "F#", "G#", "A#"}
    for pack in packs.labels():
        for kind in packs.KINDS:
            for note, dur in packs.notes_of(pack, kind):
                assert note == "-" or note[:-1] in valid, f"{pack}/{kind}: 非法音名 {note}"
                assert 0 < dur <= 2.0, f"{pack}/{kind}: 时长异常 {dur}"


def test_done_is_shorter_than_blocked_on_average():
    """设计约定：成功音短促明快，异常音更长（下坠感）。"""
    for pack in packs.labels():
        done = sum(d for _, d in packs.notes_of(pack, "done"))
        blocked = sum(d for _, d in packs.notes_of(pack, "blocked"))
        assert done < blocked, f"{pack}: done({done:.2f}s) 应短于 blocked({blocked:.2f}s)"


def test_packs_sound_distinct():
    """不能有两组听着一模一样的音效。"""
    signatures = {}
    for pack in packs.labels():
        sig = tuple(notes for kind in packs.KINDS for notes in packs.notes_of(pack, kind))
        assert sig not in signatures, f"{pack} 与 {signatures[sig]} 完全雷同"
        signatures[sig] = pack
