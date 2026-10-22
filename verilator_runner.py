"""Verilator 编译 + 仿真流程控制（QProcess 异步执行）。

复刻典型 Verilator 仿真的两步流程（如 run_sim.sh 类脚本）：
  1. verilator --Mdir tb/obj_dir --binary --timing --assert --trace-fst <源文件...> <tb文件>
  2. ./tb/obj_dir/V<top>

全部通过 QProcess 异步执行，输出逐行回传给界面，不阻塞 GUI。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

# 参与编译的源文件后缀
SOURCE_EXTS = {".sv", ".v", ".svh", ".vh"}


@dataclass
class SimConfig:
    """一次仿真的完整参数。"""

    files: list[str] = field(default_factory=list)  # 源文件绝对路径（已展开）
    workdir: str = ""           # 运行目录（Mdir、tb 里的相对路径都相对它）
    mdir: str = "tb/obj_dir"    # Verilator 输出目录
    top_module: str = ""        # 顶层模块名，空 = 不传 --top-module
    timing: bool = True         # --timing
    assert_: bool = True        # --assert
    trace_fst: bool = True      # --trace-fst
    extra_args: str = ""        # 追加给 verilator 的原始参数串
    timeout_s: int = 0          # 整个流程超时秒数，0 = 不限制

    def verilator_command(self) -> list[str]:
        argv = ["--Mdir", self.mdir, "--binary"]
        if self.timing:
            argv.append("--timing")
        if self.assert_:
            argv.append("--assert")
        if self.trace_fst:
            argv.append("--trace-fst")
        if self.top_module:
            argv += ["--top-module", self.top_module]
        if self.extra_args.strip():
            argv += self.extra_args.split()
        argv += self.files
        return argv

    def binary_path(self) -> Path:
        """编译产物可执行文件路径（顶层模块由用户手动指定，必填）。"""
        return Path(self.workdir) / self.mdir / f"V{self.top_module or 'top'}"


# ---------------------------------------------------------------------------
# 纯工具函数（便于以后单元测试）
# ---------------------------------------------------------------------------

def collect_source_files(paths: list[str]) -> list[str]:
    """把“文件/文件夹混合”的选择展开为源文件列表。

    文件夹递归收集 SOURCE_EXTS 后缀的文件，不做目录排除
    （由用户自行选择所需目录）。结果按路径去重，保持选择顺序。
    """
    out: list[str] = []
    for p in paths:
        path = Path(p).expanduser()
        if path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file() and f.suffix.lower() in SOURCE_EXTS:
                    out.append(str(f))
        elif path.is_file():
            out.append(str(path))
    seen: set[str] = set()
    unique: list[str] = []
    for f in out:
        key = str(Path(f).resolve())
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def parse_module_names(path: str) -> list[str]:
    """解析单个文件里声明的所有 module 名（按出现顺序，去重，容错处理噪声行）。"""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    names: list[str] = []
    for m in re.finditer(r"\bmodule\s+(\\?[\w$]+)", text):
        name = m.group(1).lstrip("\\")
        if name and name not in names:
            names.append(name)
    return names


def classify_line(text: str) -> str:
    """给一行输出分类，界面据此着色。返回 'error' | 'warn' | 'info' | 'out'。"""
    if "%Error" in text or "%Fatal" in text or "Assertion failed" in text:
        return "error"
    if "%Warning" in text:
        return "warn"
    if text.startswith("%Info") or re.match(r"^\s*-\s*\S", text):
        return "info"
    return "out"


# ---------------------------------------------------------------------------
# 流程控制
# ---------------------------------------------------------------------------

class VerilatorRunner(QObject):
    """两阶段（编译 → 仿真）异步执行器。

    信号：
      line_out(text, kind)   一行输出，kind 用于着色：out/err/info/warn/error/status
      stage_changed(stage)   idle / compiling / simulating
      tick(elapsed_s)        每秒一次，用于界面显示耗时
      finished(ok, summary)  全流程结束（成功/失败/停止/超时）
    """

    line_out = Signal(str, str)
    stage_changed = Signal(str)
    tick = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self._reset()

    # -- 状态 ---------------------------------------------------------------

    def _reset(self) -> None:
        self._stage = "idle"
        self._cfg: SimConfig | None = None
        self._elapsed = 0
        self._aborted = False
        self._stdout_buf = b""
        self._stderr_buf = b""

    def is_running(self) -> bool:
        return self._stage in ("compiling", "simulating")

    def elapsed(self) -> int:
        return self._elapsed

    # -- 启动 / 停止 ---------------------------------------------------------

    def start(self, cfg: SimConfig) -> None:
        """校验参数并启动编译阶段。失败原因直接发到 line_out/finished。"""
        self._reset()
        self._cfg = cfg

        verilator = shutil.which("verilator")
        if verilator is None:
            self._fail("未找到 verilator 可执行文件，请确认它已在 PATH 中。")
            return
        if not cfg.files:
            self._fail("没有可编译的源文件。")
            return
        if not cfg.top_module:
            self._fail("未指定顶层模块：请在「顶层模块」中手动填写（编译产物为 V<顶层模块名>）。")
            return
        workdir = Path(cfg.workdir).expanduser()
        if not workdir.is_dir():
            self._fail(f"工作目录不存在: {workdir}")
            return

        self.line_out.emit(f"$ cd {workdir}", "status")
        self.line_out.emit(f"$ verilator {' '.join(cfg.verilator_command())}", "status")

        self._set_stage("compiling")
        self._proc = QProcess(self)
        self._proc.setProgram(verilator)
        self._proc.setArguments(cfg.verilator_command())
        self._proc.setWorkingDirectory(str(workdir))
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.readyReadStandardError.connect(self._on_stderr)
        self._proc.finished.connect(self._on_compile_finished)
        self._proc.errorOccurred.connect(self._on_error)
        self._proc.start()
        self._timer.start()

    def stop(self) -> None:
        """手动停止当前进程。"""
        if not self.is_running() or self._proc is None:
            return
        self._aborted = True
        self.line_out.emit("⏹ 已请求停止，正在终止进程…", "status")
        self._proc.kill()

    # -- 内部 ---------------------------------------------------------------

    def _fail(self, msg: str) -> None:
        self.line_out.emit(f"❌ {msg}", "error")
        self.finished.emit(False, msg)

    def _set_stage(self, stage: str) -> None:
        self._stage = stage
        self.stage_changed.emit(stage)

    def _on_tick(self) -> None:
        self._elapsed += 1
        self.tick.emit(self._elapsed)
        cfg = self._cfg
        if cfg and cfg.timeout_s > 0 and self._elapsed >= cfg.timeout_s and self.is_running():
            self.line_out.emit(
                f"⏱ 超过设定超时 {cfg.timeout_s}s，已强制终止。可在参数区调整或设为 0（不限时）。",
                "error",
            )
            self.stop()

    def _on_error(self, err) -> None:  # QProcess.ProcessError
        if self._aborted:
            return
        text = {
            QProcess.ProcessError.FailedToStart: "进程启动失败",
            QProcess.ProcessError.Crashed: "进程崩溃",
            QProcess.ProcessError.Timedout: "进程超时",
            QProcess.ProcessError.WriteError: "写入错误",
            QProcess.ProcessError.ReadError: "读取错误",
        }.get(err, f"进程错误 {err}")
        self._fail(text)

    # -- 输出流 ---------------------------------------------------------------

    def _on_stdout(self) -> None:
        assert self._proc is not None
        self._stdout_buf += bytes(self._proc.readAllStandardOutput())
        self._stdout_buf = self._emit_lines(self._stdout_buf)

    def _on_stderr(self) -> None:
        assert self._proc is not None
        self._stderr_buf += bytes(self._proc.readAllStandardError())
        self._stderr_buf = self._emit_lines(self._stderr_buf, default_kind="err")

    def _emit_lines(self, buf: bytes, default_kind: str = "out") -> bytes:
        """把缓冲区里完整的行逐行发给界面，返回剩余的不完整行。"""
        while b"\n" in buf:
            line_bytes, buf = buf.split(b"\n", 1)
            text = line_bytes.decode("utf-8", errors="replace").rstrip("\r")
            if not text:
                continue
            kind = classify_line(text)
            self.line_out.emit(text, kind if kind != "out" else default_kind)
        return buf

    # -- 阶段切换 ---------------------------------------------------------------

    def _on_compile_finished(self, code: int, status) -> None:
        self._emit_lines(self._stdout_buf)
        self._stdout_buf = b""
        self._emit_lines(self._stderr_buf, default_kind="err")
        self._stderr_buf = b""

        if self._aborted:
            self._timer.stop()
            self._set_stage("idle")
            self.finished.emit(False, "已停止")
            return

        assert self._cfg is not None
        if code != 0 or status != QProcess.ExitStatus.NormalExit:
            self._timer.stop()
            self._set_stage("idle")
            self.line_out.emit(f"编译错误（verilator 退出码 {code}），详见上方日志。", "error")
            self.finished.emit(False, f"编译错误（退出码 {code}）")
            return

        binary = self._find_binary()
        if binary is None:
            self._timer.stop()
            self._set_stage("idle")
            self._fail("编译成功，但在输出目录里找不到可执行文件 V<top>。")
            return

        self.line_out.emit(f"$ {binary}   （在 {self._cfg.workdir} 下运行）", "status")
        self._set_stage("simulating")
        sim_proc = QProcess(self)
        self._proc = sim_proc
        sim_proc.setProgram(str(binary))
        sim_proc.setWorkingDirectory(self._cfg.workdir)
        sim_proc.readyReadStandardOutput.connect(self._on_stdout)
        sim_proc.readyReadStandardError.connect(self._on_stderr)
        sim_proc.finished.connect(self._on_sim_finished)
        sim_proc.errorOccurred.connect(self._on_error)
        self._stdout_buf = b""
        self._stderr_buf = b""
        sim_proc.start()

    def _find_binary(self) -> Path | None:
        """编译成功后定位可执行文件：优先 V<top>，否则取 Mdir 里最新的 V*。"""
        assert self._cfg is not None
        mdir = Path(self._cfg.workdir) / self._cfg.mdir
        exact = mdir / f"V{self._cfg.top_module}"
        if exact.is_file() and exact.stat().st_mode & 0o111:
            return exact
        candidates = sorted(mdir.glob("V*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for cand in candidates:
            if cand.is_file() and cand.stat().st_mode & 0o111:
                return cand
        return None

    def _on_sim_finished(self, code: int, status) -> None:
        self._emit_lines(self._stdout_buf)
        self._stdout_buf = b""
        self._emit_lines(self._stderr_buf, default_kind="err")
        self._stderr_buf = b""
        self._timer.stop()
        self._set_stage("idle")

        if self._aborted:
            self.finished.emit(False, "已停止")
            return
        if code == 0 and status == QProcess.ExitStatus.NormalExit:
            elapsed = self._elapsed
            self.line_out.emit("✅ 仿真完成，退出码 0。", "status")
            self.finished.emit(True, f"仿真完成（耗时 {elapsed}s）")
        else:
            self.line_out.emit(
                f"仿真运行失败（退出码 {code}）。若含断言失败/$fatal，上方日志已标红。", "error"
            )
            self.finished.emit(False, f"仿真失败（退出码 {code}）")
