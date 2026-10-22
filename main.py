"""VeriLaunch —— 轻量 Verilator 图形界面启动器。

启动方式：
    ./run.sh                    # 自动创建/复用本目录 .venv
    或 .venv/bin/python main.py

设计要点：
- 所有输出（编译、仿真、错误、状态）都显示在主界面日志区，不用弹窗打扰。
- 文件列表支持混合添加 .sv/.v 文件和文件夹（文件夹递归展开，不做目录排除）。
- 工作目录、顶层模块均手动指定；顶层模块必填。
- 每次运行以分割线区分历史；运行结束把本次日志按时间戳写到工作目录根目录。
- 设置自动记忆（QSettings），并可导出/导入 JSON 配置文件。
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from verilator_runner import (
    SimConfig,
    VerilatorRunner,
    collect_source_files,
    parse_module_names,
)

ORG = "verilaunch"
APP = "verilaunch"

KIND_COLOR = {
    "out": None,            # 默认前景色
    "err": "#d0d0d0",       # 进程 stderr（verilator 大多走 stderr）
    "info": "#8a8a8a",      # 编译进度信息
    "warn": "#e5a50a",      # %Warning
    "error": "#ff5f5f",     # %Error / 断言失败
    "status": "#5fb8ff",    # 工具自身状态行
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VeriLaunch — Verilator 仿真启动器")
        self.resize(1050, 720)

        self.runner = VerilatorRunner(self)
        self.runner.line_out.connect(self._on_line)
        self.runner.stage_changed.connect(self._on_stage)
        self.runner.tick.connect(self._on_tick)
        self.runner.finished.connect(self._on_finished)

        self._settings = QSettings(ORG, APP)
        self._run_no = 0        # 运行计数（分割线用）
        self._run_lines: list[str] | None = None  # 本次运行日志捕获（None=不在运行中）
        self._last_workdir = ""
        self._build_ui()
        self._restore_settings()
        self._check_verilator()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        # ---- 仿真文件区 -------------------------------------------------
        files_box = QGroupBox("仿真文件（可混合添加 .sv/.v 文件和文件夹，文件夹递归展开）")
        fv = QVBoxLayout(files_box)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        fv.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.btn_add_files = QPushButton("添加文件…")
        self.btn_add_dir = QPushButton("添加文件夹…")
        self.btn_remove = QPushButton("移除选中")
        self.btn_clear = QPushButton("清空")
        for b in (self.btn_add_files, self.btn_add_dir, self.btn_remove, self.btn_clear):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        fv.addLayout(btn_row)
        root.addWidget(files_box)

        # ---- 参数区 ------------------------------------------------------
        param_box = QGroupBox("仿真参数")
        grid = QGridLayout(param_box)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("工作目录"), 0, 0)
        self.workdir_edit = QLineEdit()
        self.workdir_edit.setPlaceholderText(
            "必填：仿真在此目录下运行；Mdir、波形和运行日志都相对它"
        )
        btn_wd = QPushButton("浏览…")
        btn_wd.setFixedWidth(70)
        wd_row = QHBoxLayout()
        wd_row.addWidget(self.workdir_edit, 1)
        wd_row.addWidget(btn_wd)
        grid.addLayout(wd_row, 0, 1, 1, 3)

        grid.addWidget(QLabel("顶层模块"), 1, 0)
        self.top_combo = QComboBox()
        self.top_combo.setEditable(True)
        self.top_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.top_combo.setMinimumContentsLength(24)
        self.top_combo.lineEdit().setPlaceholderText(
            "直接选或手填顶层模块名（必填）；下拉列表来自下方「扫描模块」/自动解析"
        )
        self.top_combo.setToolTip("下拉列出所选文件/文件夹中解析到的所有 module 名")
        grid.addWidget(self.top_combo, 1, 1)
        btn_scan = QPushButton("扫描模块")
        btn_scan.setFixedWidth(70)
        btn_scan.setToolTip("重新从所选文件/文件夹解析 module 名，刷新下拉列表")
        grid.addWidget(btn_scan, 1, 2)
        self.btn_scan_top = btn_scan

        grid.addWidget(QLabel("输出目录 --Mdir"), 2, 0)
        self.mdir_edit = QLineEdit("tb/obj_dir")
        grid.addWidget(self.mdir_edit, 2, 1)

        grid.addWidget(QLabel("超时(秒)"), 2, 2, Qt.AlignmentFlag.AlignRight)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0, 999999)
        self.timeout_spin.setValue(0)
        self.timeout_spin.setToolTip("0 = 不限时；超过后强制终止进程")
        grid.addWidget(self.timeout_spin, 2, 3)

        grid.addWidget(QLabel("附加参数"), 3, 0)
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("原样追加给 verilator，如 -Wno-UNUSEDSIGNAL")
        grid.addWidget(self.extra_edit, 3, 1, 1, 3)

        flag_row = QHBoxLayout()
        self.cb_timing = QCheckBox("--timing")
        self.cb_assert = QCheckBox("--assert")
        self.cb_trace = QCheckBox("--trace-fst")
        self.cb_wall = QCheckBox("-Wall")
        self.cb_wno_fatal = QCheckBox("--Wno-fatal")
        self.cb_wno_fatal.setToolTip("快速测试用：把 %Warning 不再升级为错误（不推荐常态化使用）")
        for cb, checked in (
            (self.cb_timing, True),
            (self.cb_assert, True),
            (self.cb_trace, True),
            (self.cb_wall, False),
            (self.cb_wno_fatal, False),
        ):
            cb.setChecked(checked)
            flag_row.addWidget(cb)
        flag_row.addStretch(1)
        flag_row.addWidget(QLabel("--binary 固定启用"))
        grid.addLayout(flag_row, 4, 1, 1, 3)
        root.addWidget(param_box)

        # ---- 操作区 ------------------------------------------------------
        action_row = QHBoxLayout()
        self.btn_run = QPushButton("▶ 开始仿真")
        self.btn_run.setMinimumHeight(34)
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_wave = QPushButton("用 GTKWave 打开最新波形")
        self.btn_outdir = QPushButton("打开输出目录")
        self.btn_clean_log = QPushButton("清空日志")
        for b in (self.btn_run, self.btn_stop, self.btn_wave, self.btn_outdir, self.btn_clean_log):
            action_row.addWidget(b)
        action_row.addStretch(1)
        root.addLayout(action_row)

        cfg_row = QHBoxLayout()
        self.cb_auto_wave = QCheckBox("仿真完成后自动打开 GTKWave")
        self.cb_auto_wave.setToolTip("仅仿真成功（退出码 0）时弹出")
        self.btn_save_cfg = QPushButton("💾 保存配置…")
        self.btn_load_cfg = QPushButton("📂 导入配置…")
        cfg_row.addWidget(self.cb_auto_wave)
        cfg_row.addStretch(1)
        cfg_row.addWidget(self.btn_save_cfg)
        cfg_row.addWidget(self.btn_load_cfg)
        root.addLayout(cfg_row)

        # ---- 状态行 ------------------------------------------------------
        status_row = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.elapsed_label = QLabel("")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.elapsed_label)
        root.addLayout(status_row)

        # ---- 日志区 ------------------------------------------------------
        log_box = QGroupBox("输出（编译/仿真/错误全部显示在这里，保留历史，分割线区分每次运行）")
        lv = QVBoxLayout(log_box)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(10)
        self.log.setFont(mono)
        self.log.document().setMaximumBlockCount(20000)
        lv.addWidget(self.log)
        root.addWidget(log_box, 1)

        central.setLayout(root)
        self.setCentralWidget(central)

        # ---- 信号 --------------------------------------------------------
        self.btn_add_files.clicked.connect(self._add_files)
        self.btn_add_dir.clicked.connect(self._add_dir)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_files)
        self.btn_scan_top.clicked.connect(self._refresh_top_modules)
        self.file_list.itemSelectionChanged.connect(
            lambda: self.btn_remove.setEnabled(bool(self.file_list.selectedItems()))
        )
        self.btn_remove.setEnabled(False)
        btn_wd.clicked.connect(self._browse_workdir)
        self.btn_run.clicked.connect(self._run)
        self.btn_stop.clicked.connect(self.runner.stop)
        self.btn_wave.clicked.connect(self._open_wave)
        self.btn_outdir.clicked.connect(self._open_outdir)
        self.btn_clean_log.clicked.connect(self.log.clear)
        self.btn_save_cfg.clicked.connect(self._save_config_json)
        self.btn_load_cfg.clicked.connect(self._load_config_json)

    # ---------------------------------------------------------------- 选择文件

    def _entries(self) -> list[str]:
        return [self.file_list.item(i).text() for i in range(self.file_list.count())]

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要编译的源文件",
            self._dialog_dir(),
            "Verilog/SystemVerilog (*.sv *.v *.svh *.vh);;所有文件 (*)",
        )
        self._add_entries(paths)

    def _add_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "选择文件夹（递归收集 .sv/.v）", self._dialog_dir()
        )
        self._add_entries([path] if path else [])

    def _dialog_dir(self) -> str:
        for cand in (self.workdir_edit.text(), str(Path.home())):
            if cand and Path(cand).is_dir():
                return cand
        return ""

    def _add_entries(self, paths: list[str]) -> None:
        existing = set(self._entries())
        for p in paths:
            if p and p not in existing:
                self.file_list.addItem(QListWidgetItem(p))
                existing.add(p)
        if paths:
            self._refresh_top_modules()

    # ---------------------------------------------------------------- 顶层模块下拉

    def _clear_files(self) -> None:
        self.file_list.clear()
        self._refresh_top_modules()

    def _refresh_top_modules(self) -> None:
        """解析所选文件/文件夹的全部 module 名，刷新顶层模块下拉列表。

        tb_ 前缀文件里的模块排前面；下拉可编辑，手填的模块名在刷新后保留。
        """
        files = collect_source_files(self._entries())
        tb_names: list[str] = []
        other: list[str] = []
        for f in files:
            for name in parse_module_names(f):
                bucket = tb_names if Path(f).name.startswith("tb_") else other
                if name not in bucket:
                    bucket.append(name)
        current = self.top_combo.currentText()
        self.top_combo.clear()
        ordered = tb_names + other
        if ordered:
            self.top_combo.addItems(ordered)
        self.top_combo.setCurrentText(current)
        if ordered and not current:
            self.top_combo.lineEdit().setPlaceholderText(
                f"下拉列表已就绪（{len(ordered)} 个模块），选择或手填；必填"
            )

    def _remove_selected(self) -> None:
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._refresh_top_modules()

    def _browse_workdir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "选择工作目录（Mdir/波形/运行日志都相对它）", self._dialog_dir()
        )
        if path:
            self.workdir_edit.setText(path)

    # ---------------------------------------------------------------- 配置

    def _build_config(self) -> SimConfig | None:
        files = collect_source_files(self._entries())
        if not files:
            self._log_error_and_status("没有可编译的源文件：请先添加 .sv/.v 文件或包含它们的文件夹。",
                                       "未选择源文件")
            return None
        workdir = self.workdir_edit.text().strip()
        if not workdir or not Path(workdir).expanduser().is_dir():
            self._log_error_and_status(f"工作目录无效: {workdir or '(空)'}，请用「浏览…」手动选择。",
                                       "工作目录无效")
            return None
        top = self.top_combo.currentText().strip()
        if not top:
            self._log_error_and_status("未指定顶层模块：请从「顶层模块」下拉列表选择，或手动填写。",
                                       "未指定顶层模块")
            return None

        extra = []
        if self.cb_wall.isChecked():
            extra.append("-Wall")
        if self.cb_wno_fatal.isChecked():
            extra.append("--Wno-fatal")
        if self.extra_edit.text().strip():
            extra.append(self.extra_edit.text().strip())
        return SimConfig(
            files=files,
            workdir=str(Path(workdir).expanduser()),
            mdir=self.mdir_edit.text().strip() or "tb/obj_dir",
            top_module=top,
            timing=self.cb_timing.isChecked(),
            assert_=self.cb_assert.isChecked(),
            trace_fst=self.cb_trace.isChecked(),
            extra_args=" ".join(extra),
            timeout_s=self.timeout_spin.value(),
        )

    def _log_error_and_status(self, line: str, status: str) -> None:
        self._append_log(f"❌ {line}", "error")
        self._set_status(f"❌ {status}", "#ff5f5f")

    # ---------------------------------------------------------------- 运行

    def _run(self) -> None:
        self._save_settings()
        cfg = self._build_config()
        if cfg is None:
            return
        # 保留历史，分割线区分每次运行；从分割线开始捕获本次日志
        self._run_no += 1
        self._run_lines = []
        self._append_log(
            f"═════════ 第 {self._run_no} 次运行 · {time.strftime('%Y-%m-%d %H:%M:%S')} ═════════",
            "status",
        )
        self._append_log(f"共 {len(cfg.files)} 个源文件，顶层模块: {cfg.top_module}", "status")
        self._last_workdir = cfg.workdir
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.runner.start(cfg)

    # ---------------------------------------------------------------- 信号槽

    def _on_line(self, text: str, kind: str) -> None:
        self._append_log(text, kind)

    def _on_stage(self, stage: str) -> None:
        if stage == "compiling":
            self._set_status("编译中…", "#e5a50a")
        elif stage == "simulating":
            self._set_status("仿真运行中…", "#5fb8ff")
        else:
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)

    def _on_tick(self, elapsed: int) -> None:
        self.elapsed_label.setText(f"已运行 {elapsed // 60}:{elapsed % 60:02d}")

    def _on_finished(self, ok: bool, summary: str) -> None:
        if ok:
            self._set_status(f"✅ {summary}", "#4caf50")
            state = "OK"
        elif summary == "已停止":
            self._set_status("⏹ 已停止", "#8a8a8a")
            state = "STOP"
        else:
            self._set_status(f"❌ {summary}", "#ff5f5f")
            state = "FAIL"
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._write_run_log(state)
        if ok and self.cb_auto_wave.isChecked():
            self._open_wave()

    # ---------------------------------------------------------------- 日志

    def _append_log(self, text: str, kind: str = "out") -> None:
        if self._run_lines is not None:
            self._run_lines.append(text)
        color = KIND_COLOR.get(kind)
        esc = html.escape(text)
        if color:
            self.log.append(f'<span style="color:{color};white-space:pre-wrap">{esc}</span>')
        else:
            self.log.append(f"<span style='white-space:pre-wrap'>{esc}</span>")
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _write_run_log(self, state: str) -> None:
        """把本次运行的日志写到工作目录根目录：sim_<时间戳>_<OK|FAIL|STOP>.log"""
        lines, self._run_lines = self._run_lines, None
        if lines is None:
            return
        try:
            workdir = Path(self._last_workdir).expanduser()
            if not workdir.is_dir():
                raise OSError(f"工作目录不存在: {workdir}")
            fname = workdir / f"sim_{time.strftime('%Y%m%d-%H%M%S')}_{state}.log"
            fname.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self._append_log(f"已保存本次运行日志: {fname}", "status")
        except OSError as e:
            self._append_log(f"❌ 保存运行日志失败: {e}", "error")

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        if "就绪" in text or "完成" in text or "错误" in text or "停止" in text:
            self.elapsed_label.setText("")

    def _check_verilator(self) -> None:
        verilator = shutil.which("verilator")
        if verilator is None:
            self._append_log("❌ 未找到 verilator（PATH 中不存在）。请检查环境。", "error")
            self._set_status("❌ 未找到 verilator", "#ff5f5f")
            return
        try:
            ver = subprocess.run(
                [verilator, "--version"], capture_output=True, text=True, timeout=10
            ).stdout.strip()
        except OSError as e:
            ver = f"（无法获取版本: {e}）"
        self._append_log(f"使用 {ver}", "status")

    # ---------------------------------------------------------------- 波形/目录

    def _find_newest_fst(self) -> Path | None:
        workdir = Path(self.workdir_edit.text()).expanduser()
        if not workdir.is_dir():
            return None
        fsts = list(workdir.rglob("*.fst"))
        if not fsts:
            return None
        return max(fsts, key=lambda p: p.stat().st_mtime)

    def _open_wave(self) -> None:
        if shutil.which("gtkwave") is None:
            self._append_log("❌ 未找到 gtkwave，无法打开波形。", "error")
            return
        fst = self._find_newest_fst()
        if fst is None:
            self._append_log("❌ 工作目录下未找到 .fst 波形文件（先成功跑一次仿真）。", "error")
            return
        ok, msg = _spawn_detached("gtkwave", [str(fst)])
        if ok:
            self._append_log(f"已启动 GTKWave: {fst}", "status")
        else:
            self._append_log(f"❌ 启动 gtkwave 失败: {msg} ({fst})", "error")

    def _open_outdir(self) -> None:
        mdir = Path(self.workdir_edit.text()).expanduser() / self.mdir_edit.text()
        if not mdir.is_dir():
            self._append_log(f"❌ 输出目录不存在: {mdir}", "error")
            return
        ok, msg = _spawn_detached("xdg-open", [str(mdir)])
        if not ok:
            self._append_log(f"❌ 打开目录失败: {msg} ({mdir})", "error")

    # ---------------------------------------------------------------- 配置保存/导入

    def _collect_config(self) -> dict:
        return {
            "tool": "verilaunch",
            "version": 1,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "entries": self._entries(),
            "workdir": self.workdir_edit.text(),
            "mdir": self.mdir_edit.text(),
            "top": self.top_combo.currentText(),
            "extra": self.extra_edit.text(),
            "timeout": self.timeout_spin.value(),
            "timing": self.cb_timing.isChecked(),
            "assert": self.cb_assert.isChecked(),
            "trace_fst": self.cb_trace.isChecked(),
            "wall": self.cb_wall.isChecked(),
            "wno_fatal": self.cb_wno_fatal.isChecked(),
            "auto_open_wave": self.cb_auto_wave.isChecked(),
        }

    def _apply_config(self, d: dict) -> None:
        entries = d.get("entries") or []
        if isinstance(entries, str):  # QSettings 单条列表可能回读成 str
            entries = [entries]
        self.file_list.clear()
        for e in entries:
            self.file_list.addItem(QListWidgetItem(str(e)))
        self.workdir_edit.setText(str(d.get("workdir") or ""))
        self.mdir_edit.setText(str(d.get("mdir") or "tb/obj_dir"))
        self.extra_edit.setText(str(d.get("extra") or ""))
        self._refresh_top_modules()
        self.top_combo.setCurrentText(str(d.get("top") or ""))
        self.timeout_spin.setValue(int(d.get("timeout") or 0))
        self.cb_timing.setChecked(bool(d.get("timing", True)))
        self.cb_assert.setChecked(bool(d.get("assert", True)))
        self.cb_trace.setChecked(bool(d.get("trace_fst", True)))
        self.cb_wall.setChecked(bool(d.get("wall", False)))
        self.cb_wno_fatal.setChecked(bool(d.get("wno_fatal", False)))
        self.cb_auto_wave.setChecked(bool(d.get("auto_open_wave", False)))

    def _save_config_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存仿真配置",
            self._default_cfg_filename(),
            "仿真配置 (*.json);;所有文件 (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(self._collect_config(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self._append_log(f"已保存配置: {path}", "status")
        except OSError as e:
            self._append_log(f"❌ 保存配置失败: {e}", "error")

    def _default_cfg_filename(self) -> str:
        base = self.workdir_edit.text().strip()
        if not base or not Path(base).expanduser().is_dir():
            base = str(Path.home())
        top = self.top_combo.currentText().strip() or "sim"
        return str(Path(base) / f"simcfg_{top}.json")

    def _load_config_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "导入仿真配置", self._dialog_dir(),
            "仿真配置 (*.json);;所有文件 (*)",
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            self._append_log(f"❌ 读取配置失败: {e} ({path})", "error")
            return
        if not isinstance(data, dict):
            self._append_log(f"❌ 配置文件格式不对（应为 JSON 对象）: {path}", "error")
            return
        self._apply_config(data)
        self._save_settings()
        top = data.get("top") or "(未指定)"
        n = len(data.get("entries", []) or [])
        self._append_log(f"已导入配置: {path}（{n} 个文件，顶层 {top}）", "status")

    # ---------------------------------------------------------------- 设置持久化

    def _save_settings(self) -> None:
        s = self._settings
        cfg = self._collect_config()
        cfg.pop("saved_at", None)
        for k, v in cfg.items():
            s.setValue(k, v if not isinstance(v, list) else list(v))

    def _restore_settings(self) -> None:
        s = self._settings
        cfg = {}
        for k in self._collect_config():
            v = s.value(k)
            cfg[k] = v
        self._apply_config(cfg)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.runner.is_running():
            self.runner.stop()
        self._save_settings()
        super().closeEvent(event)


def _spawn_detached(program: str, args: list[str]) -> tuple[bool, str]:
    """脱离本进程启动外部程序（GUI 不被阻塞，父进程退出也不影响）。"""
    if shutil.which(program) is None:
        return False, f"未找到 {program}"
    try:
        subprocess.Popen(
            [program, *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True, ""
    except OSError as e:
        return False, str(e)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setOrganizationName(ORG)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
