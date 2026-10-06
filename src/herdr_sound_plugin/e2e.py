"""端到端验证：让每个音色包真的响一次，并核对播的是哪个 mp3。

这需要 herdr 正在运行，且插件已 link。流程：
  1. 建一个**后台** workspace（后台才触发通知，当前聚焦的 workspace 不触发）
  2. 起一个真 agent（`herdr pane report-agent` 不会触发状态机，必须用真 agent）
  3. 开始采样 afplay；逐个切换音色包 → prompt agent → 等 done
  4. 汇总实际播放的文件，与期望比对

用法：
    uv run python -m herdr_sound_plugin.e2e                 # 全部包
    uv run python -m herdr_sound_plugin.e2e --packs mario zelda
    uv run python -m herdr_sound_plugin.e2e --keep          # 保留 workspace 便于手工看
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile
import time

from . import capture, herdr, packs

WORKSPACE_LABEL = "sound-e2e"
AGENT_NAME = "sounder"


class Probe:
    """一个用于触发状态变化的试验 workspace + agent。"""

    def __init__(self, cwd: str = "/tmp") -> None:
        self.cwd = cwd
        self.workspace_id = ""
        self.pane_id = ""

    def __enter__(self) -> "Probe":
        data = herdr.call("workspace", "create", "--label", WORKSPACE_LABEL,
                          "--cwd", self.cwd, "--no-focus")
        self.workspace_id = data["result"]["workspace"]["workspace_id"]
        root = data["result"]["root_pane"]["pane_id"]
        # 根 pane 是 shell，不能承载 agent（会报 agent_pane_busy），必须 split 一个
        self.pane_id = herdr.call("pane", "split", root,
                                  "--direction", "right")["result"]["pane"]["pane_id"]
        herdr.call("agent", "start", AGENT_NAME, "--kind", "pi", "--pane", self.pane_id)
        _wait_agent_ready(self.pane_id)
        return self

    def __exit__(self, *exc) -> None:
        try:
            herdr.call("workspace", "close", self.workspace_id)
        except Exception as err:  # 清理失败不该掩盖真正的错误
            print(f"清理 workspace 失败: {err}", file=sys.stderr)

    def trigger(self) -> "str | None":
        """prompt 一下 agent，等它走完 working -> done 一整轮。

        必须先等它离开 done（进 working），否则会读到上一轮的旧状态就返回。
        """
        herdr.call("agent", "prompt", AGENT_NAME, "回复两个字：好的")
        if not _wait_status(self.pane_id, "working", timeout=30.0):
            return None
        return herdr.wait_done(self.pane_id)


def _wait_status(pane_id: str, wanted: str, timeout: float = 30.0) -> bool:
    """轮询等待 pane 进入某个状态（用于等 agent 真正开始干活）。"""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if herdr.pane_status(pane_id) == wanted:
            return True
        time.sleep(0.5)
    return False


def _wait_status(pane_id: str, wanted: str, timeout: float = 30.0) -> bool:
    """轮询等待 pane 进入某个状态（用于等 agent 真正开始干活）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if herdr.pane_status(pane_id) == wanted:
            return True
        time.sleep(0.5)
    return False


def _wait_agent_ready(pane_id: str, timeout: float = 30.0) -> None:
    """等 agent 的 TUI 起来（否则 prompt 会石沉大海）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if herdr.pane_status(pane_id) in ("idle", "done"):
            return
        time.sleep(1)


def run(selected: "list[str] | None" = None, per_pack_timeout: float = 90.0) -> int:
    packs_to_test = selected or packs.labels()
    log = pathlib.Path(tempfile.gettempdir()) / "afplay-e2e.log"
    log.write_text("")

    sampler = subprocess.Popen(
        [sys.executable, "-m", "herdr_sound_plugin.capture", "--watch",
         "--interval", "0.03", "--log", str(log)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    failures = 0
    try:
        with Probe() as probe:
            print(f"probe workspace={probe.workspace_id} pane={probe.pane_id}\n")
            for pack in packs_to_test:
                herdr.use_pack(pack)
                time.sleep(1)
                before = sum(capture.files(log).values())
                status = probe.trigger()
                time.sleep(1)
                after = capture.files(log)
                delta = sum(after.values()) - before
                expected = f"sounds/{pack}/done.mp3"
                got = [n for n, c in after.items() if n.endswith(f"{pack}/done.mp3")]
                mark = "✓" if delta and got else "✗"
                if mark == "✗":
                    failures += 1
                print(f"{mark} {pack:8s} status={status or 'timeout':8s} "
                      f"hits={delta:3d}  expected {expected}")
    finally:
        sampler.terminate()
        sampler.wait(timeout=5)

    print("\nPlayback by file:")
    for name, count in sorted(capture.files(log).items()):
        print(f"  {count:4d}  {name}")
    return 1 if failures else 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--packs", nargs="*", default=None,
                        help=f"只测这些包（默认全部：{' '.join(packs.labels())}）")
    parser.add_argument("--timeout", type=float, default=90.0, help="每个包等 done 的超时秒数")
    args = parser.parse_args(argv)

    try:
        return run(args.packs, args.timeout)
    except FileNotFoundError as err:
        print(f"跳过：{err}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
