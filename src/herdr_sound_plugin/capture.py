"""抓取 `afplay` 播放记录——验证「到底播了哪个文件」的调试利器。

背景：herdr 插件只是异步 `nohup afplay ... &`，进程一闪而过，
直接 `ps | grep afplay` 往往抓不到（而且 grep 会匹配到自己的命令行）。
本模块用 `pgrep -x afplay` 精确取 pid（避免自匹配），高频采样并记录完整 argv。

命令行用法：
    uv run python -m herdr_sound_plugin.capture --seconds 20
    uv run python -m herdr_sound_plugin.capture --watch        # 持续采样，Ctrl-C 结束
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import time

DEFAULT_LOG = pathlib.Path("/tmp/afplay-hits.log")
_FILE_MARK = "sounds/"


def sample() -> "list[str]":
    """采样一次，返回当前所有 afplay 进程的完整命令行。

    用 `pgrep -x afplay`（精确匹配进程名）而非 `pgrep -f afplay`，
    以免匹配到采样器自身。
    """
    pids = subprocess.run(["pgrep", "-x", "afplay"],
                          capture_output=True, text=True).stdout.split()
    lines = []
    for pid in pids:
        out = subprocess.run(["ps", "-p", pid, "-o", "args="],
                             capture_output=True, text=True).stdout.strip()
        if out:
            lines.append(out)
    return lines


def files(log: "str | pathlib.Path") -> "dict[str, int]":
    """从采样日志里统计各音效文件被播放的次数。"""
    log = pathlib.Path(log)
    counts: dict[str, int] = {}
    if not log.exists():
        return counts
    for line in log.read_text(errors="replace").splitlines():
        idx = line.find(_FILE_MARK)
        if idx >= 0:
            name = line[idx:].split()[0]
            counts[name] = counts.get(name, 0) + 1
    return counts


def watch(log: "str | pathlib.Path" = DEFAULT_LOG, interval: float = 0.03,
          seconds: "float | None" = None) -> int:
    """高频采样 `interval` 秒一次，把命中追加进 `log`；`seconds=None` 表示一直跑。

    返回捕获到的总条数（仅当 `seconds` 有限时才有意义）。
    """
    log = pathlib.Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    deadline = None if seconds is None else time.monotonic() + seconds
    hits = 0
    with log.open("a") as fh:
        while deadline is None or time.monotonic() < deadline:
            for line in sample():
                fh.write(line + "\n")
                hits += 1
            fh.flush()
            time.sleep(interval)
    return hits


def _main(argv: "list[str] | None" = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    log = DEFAULT_LOG
    seconds: "float | None" = 10.0
    interval = 0.03

    it = iter(range(len(args)))
    for i in it:
        arg = args[i]
        if arg == "--watch":
            seconds = None
        elif arg == "--seconds":
            seconds = float(args[i + 1])
            next(it, None)
        elif arg == "--interval":
            interval = float(args[i + 1])
            next(it, None)
        elif arg == "--log":
            log = pathlib.Path(args[i + 1])
            next(it, None)
        elif arg in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            print(f"未知参数: {arg}", file=sys.stderr)
            return 2

    if seconds is None:
        print(f"Sampling continuously (every {interval}s). Press Ctrl-C to stop. Log: {log}")
    else:
        print(f"Sampling for {seconds}s (every {interval}s). Log: {log}")

    try:
        hits = watch(log, interval=interval, seconds=seconds)
    except KeyboardInterrupt:
        hits = -1

    counts = files(log)
    print(f"\nSamples captured: {hits if hits >= 0 else '(interrupted)'}. Playback by file:")
    for name, count in sorted(counts.items()):
        print(f"  {count:4d}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
