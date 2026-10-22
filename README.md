# VeriLaunch

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](#requirements)

> A lightweight, unofficial GUI launcher for Verilator: pick RTL and testbench files or folders, set the working dir and top module, and run compile + simulation with live, color-coded output. Timestamped run logs, one-click GTKWave waveforms, importable configs, and a ready-to-run Linux AppImage.
>
> **VeriLaunch 是一个为 Verilator 打造的轻量图形界面启动器：选择 RTL/测试文件，一键编译并运行仿真，实时显示输出并将错误标红，自动归档运行日志，一键/自动打开 GTKWave 查看波形。**

<p align="center"><img src="package/assets/icon_256.png" width="96" alt="VeriLaunch icon"/></p>

---

## Features / 功能特性

- 🗂 **File & folder picker** — mix `.sv/.v/.svh/.vh` files and folders; folders are scanned recursively
- 🎛 **Manual control** — working directory, `--Mdir`, and the top module (editable dropdown auto-populated with all module names found in your selection)
- ▶ **One-click run** — Verilator compile + simulation as an asynchronous pipeline, never blocking the UI
- 🌈 **Live log** — all compiler/simulator output in one pane; `%Error` and assertion failures highlighted in red, `%Warning` in orange
- 📝 **Timestamped run logs** — every run is archived to the working directory as `sim_<datetime>_<OK|FAIL|STOP>.log`
- 🌊 **GTKWave integration** — open the newest `.fst` manually, or automatically on successful simulation
- 💾 **Profiles** — settings are remembered; configs can be exported/imported as JSON to switch between modules quickly
- 🍎 [AppImage](https://appimage.org) ready — a single executable file, no install, works even without libfuse2

## Requirements / 环境要求

- Linux x86_64
- [Verilator](https://verilator.org) in `PATH` (5.x recommended, `--binary`/`--timing` required)
- Optional: `gtkwave` for waveform viewing, `libfuse2` for mounting AppImages (not required — the runtime falls back to extraction automatically)

For running from source: Python 3.9+ with `venv`, and PySide6 (installed automatically into a local `.venv` — never touches your system Python).

## Quick start / 快速开始

**Option A — AppImage** (recommended): download `verilaunch-x86_64.AppImage` from [Releases](../../releases), make it executable, and run:

```bash
chmod +x verilaunch-x86_64.AppImage
./verilaunch-x86_64.AppImage
```

**Option B — from source:**

```bash
./run.sh        # first run creates .venv and installs PySide6 (local only)
```

**Build the AppImage yourself:**

```bash
./package/build.sh   # produces package/verilaunch-x86_64.AppImage (+ .tar.gz)
```

## Usage tips / 使用说明

1. **仿真文件**：添加 `.sv/.v` 文件或整个文件夹（可混选，递归收集）
2. **工作目录**：手动指定；`--Mdir`、波形相对路径和运行日志都以此为根
3. **顶层模块**：从下拉框选择（自动列出所选文件里的所有 module），也可手填
4. **运行**：`▶ 开始仿真` 后编译与仿真输出实时滚动；错误红字显示
5. 每次运行日志自动存为 `工作目录/sim_<时间戳>_<OK|FAIL|STOP>.log`
6. 配置可 **保存/导入**（JSON），不同模块各存一份，切换随时恢复

## AI-assisted development / AI 协作开发声明

> **English**: This project was developed with the help of an AI coding assistant (an LLM pair-programmer). Requirements, design decisions, testing, and release management were done by the maintainer; most of the code and packaging scripts were generated and iterated on with AI assistance under human review.
>
> **中文**：本项目在 AI 编程助手（大语言模型结对编程）的协助下开发。维护者负责提出需求、设计决策、全部功能的实测验证与发布；主要代码与打包脚本由 AI 生成并经人工复核迭代。我们如实披露这一开发方式，供使用者在评估代码与贡献时参考。

## Project status / 状态

`v0.1.0` — still early. Expect rough edges; bug reports and PRs are welcome.

Note: VeriLaunch is **not affiliated with the Verilator project** (maintained by Antmicro and the community). "Verilator" is used descriptively to indicate which simulator this tool launches.

## License / 许可

[MIT](LICENSE) © 2026 li yongxuan
