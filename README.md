<div align="center">

**English** | [简体中文](README.zh-CN.md)

</div>

# VeriLaunch

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](#requirements)

> A lightweight, unofficial GUI launcher for Verilator: pick RTL and testbench files or folders, set the working dir and top module, and run compile + simulation with live, color-coded output. Timestamped run logs, one-click GTKWave waveforms, importable configs, and a ready-to-run Linux AppImage — *pick your RTL, hit run, see the waves*.

<p align="center"><img src="package/assets/icon_256.png" width="96" alt="VeriLaunch icon"/></p>

---

## Features

- 🗂 **File & folder picker** — mix `.sv/.v/.svh/.vh` files and folders; folders are collected recursively
- 🎛 **Manual control** — working directory, `--Mdir`, and the top module (an editable dropdown auto-populated with all module names found in your selection)
- ▶ **One-click run** — Verilator compile + simulation run as an asynchronous pipeline, never blocking the UI
- 🌈 **Live color-coded log** — all compiler/simulator output in one pane; `%Error` and assertion failures highlighted in red, `%Warning` in orange
- 📝 **Timestamped run logs** — every run is archived to the working directory as `sim_<datetime>_<OK|FAIL|STOP>.log`
- 🌊 **GTKWave integration** — open the newest `.fst` manually, or automatically on successful simulation
- 💾 **Profiles** — settings are remembered; configurations can be exported/imported as JSON to switch between modules instantly
- 📦 [AppImage](https://appimage.org) ready — a single executable file, no install, works even without libfuse2

## Requirements

- Linux x86_64
- [Verilator](https://verilator.org) 5.x in `PATH` (flow based on `--binary --timing --assert`)
- Optional: `gtkwave` for waveform viewing, `libfuse2` for mounting AppImages (not required — the runtime falls back to extraction automatically)

For running from source: Python 3.9+ with `venv`; PySide6 is installed automatically into a local `.venv` — never touching your system Python.

## Quick start

**Option A — AppImage** (recommended): download `verilaunch-x86_64.AppImage` from [Releases](../../releases), then:

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

## Usage

1. **Simulation files** — add `.sv/.v` files or whole folders (mixed selection is fine, collected recursively)
2. **Working directory** — choose it manually; `--Mdir`, relative waveform paths, and run logs are all resolved against it
3. **Top module** — pick from the dropdown (auto-populated with every module name found in your selection) or type your own
4. **Run** — click `▶ Start simulation`; compile and simulation output streams in live, errors highlighted in red
5. Each run is archived as `working_dir/sim_<datetime>_<OK|FAIL|STOP>.log`
6. Save and import configs (JSON) — one profile per module, switch back anytime

## AI-assisted development

> This project was developed with the help of an AI coding assistant (an LLM pair-programmer). Requirements, design decisions, testing, and release management were done by the maintainer; most of the code and packaging scripts were generated and iterated on with AI assistance under human review. We disclose this openly so users can factor it in when evaluating or contributing to the code.

## Project status

`v0.1.0` — still early. Expect rough edges; bug reports and PRs are welcome.

Note: VeriLaunch is **not affiliated with the Verilator project** (maintained by Antmicro and the community). "Verilator" is used descriptively to indicate which simulator this tool launches.

## License

[MIT](LICENSE) © 2026 li yongxuan
