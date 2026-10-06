# ============================================================================
# ⚠️ 已失效的归档代码 —— 不要使用，不要修改。
#
# 这是 herdr 插件方案的遗留实现，2026-10-06 被「直接改 herdr 原生配置」取代。
# 详见同目录 README.md。将来若需要，请重新实现，不要复活此处代码。
# ============================================================================
"""端到端验证：让每个音色包真的响一次，并核对播的是哪个 mp3。

这需要 herdr 正在运行，且插件已 link。流程：
  1. 建一个**后台** workspace（后台才触发通知，当前聚焦的 workspace 不触发）
  2. 分两个 pane：一个起真 agent（验 done），一个纯 shell（验 blocked）
  3. 开始采样 afplay；逐包切换并分别触发 done / blocked
  4. 汇总实际播放的文件，与期望比对

为什么不共用一个 pane：**`report-agent` 在已跑着 agent 的 pane 上会被忽略**
（状态不会变），只有空 shell pane 才能被置为 blocked。反过来，`done` 必须
靠真 agent 跑完一轮才能得到，无法用 `report-agent --state done` 伪造。

用法：
    uv run python -m herdr_sound_plugin.e2e                 # 全部包、两个类别
    uv run python -m herdr_sound_plugin.e2e --packs mario zelda
    uv run python -m herdr_sound_plugin.e2e --kinds blocked  # 只验异常音
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
    """用于触发状态变化的试验 workspace。

    - `pane_id`：跑着真 pi agent，用于触发 done
    - `shell_pane_id`：纯 shell（无 agent），用于触发 blocked
    """

    def __init__(self, cwd: str = "/tmp") -> None:
        self.cwd = cwd
        self.workspace_id = ""
        self.pane_id = ""
        self.shell_pane_id = ""

    def __enter__(self) -> "Probe":
        data = herdr.call("workspace", "create", "--label", WORKSPACE_LABEL,
                          "--cwd", self.cwd, "--no-focus")
        self.workspace_id = data["result"]["workspace"]["workspace_id"]
        root = data["result"]["root_pane"]["pane_id"]
        # 根 pane 是 shell，不能承载 agent（会报 agent_pane_busy），必须 split 一个
        self.pane_id = herdr.call("pane", "split", root,
                                  "--direction", "right")["result"]["pane"]["pane_id"]
        # 第二个 pane 留作空 shell，用来伪造 blocked
        self.shell_pane_id = herdr.call(
            "pane", "split", root, "--direction", "down")["result"]["pane"]["pane_id"]
        _start_agent(self.pane_id)
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

    def block(self) -> str:
        """把**空 shell** pane 置为 blocked，触发「需要介入」路径。

        必须用 `shell_pane_id`：对已跑着 agent 的 pane 调 report-agent 会被忽略。
        且必须**先复位成 idle**再置 blocked——同样状态重复上报不产生状态迁移，
        也就不会触发事件（第二次及以后的包都会静默无声）。
        复位产生的 idle 事件不会放音（notify.sh 只处理 done/blocked），无副作用。
        """
        for state in ("idle", "blocked"):
            herdr.call("pane", "report-agent", "--source", "e2e", "--agent", "pi",
                       "--state", state, self.shell_pane_id)
            time.sleep(1.0)
        return herdr.pane_status(self.shell_pane_id)


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


def _start_agent(pane_id: str, attempts: int = 5) -> None:
    """起 agent，带重试。

    刚 `pane split` 出来的 shell 可能还没就绪，直接 start 会报
    `agent_pane_busy: ... is not an available shell`，等一下再试即可。
    """
    last: "Exception | None" = None
    for _ in range(attempts):
        try:
            herdr.call("agent", "start", AGENT_NAME, "--kind", "pi", "--pane", pane_id)
            return
        except RuntimeError as err:
            if "agent_pane_busy" not in str(err):
                raise
            last = err
            time.sleep(1.0)
    raise RuntimeError(f"起 agent 失败（重试 {attempts} 次）: {last}")


def run(selected: "list[str] | None" = None, per_pack_timeout: float = 90.0,
        kinds: "tuple[str, ...]" = ("done", "blocked")) -> int:
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

                if "done" in kinds:
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

                if "blocked" in kinds:
                    before = sum(capture.files(log).values())
                    status = probe.block()
                    after = capture.files(log)
                    delta = sum(after.values()) - before
                    expected = f"sounds/{pack}/blocked.mp3"
                    got = [n for n, c in after.items() if n.endswith(f"{pack}/blocked.mp3")]
                    mark = "✓" if delta and got else "✗"
                    if mark == "✗":
                        failures += 1
                    print(f"{mark} {pack:8s} status={status:8s} "
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
    parser.add_argument("--kinds", nargs="*", default=list(packs.KINDS),
                        choices=list(packs.KINDS), help="只测这些类别（默认 done + blocked）")
    args = parser.parse_args(argv)

    try:
        return run(args.packs, args.timeout, tuple(args.kinds))
    except FileNotFoundError as err:
        print(f"跳过：{err}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
