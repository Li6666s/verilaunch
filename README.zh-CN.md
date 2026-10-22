<div align="center">

[English](README.md) | **简体中文**

</div>

# VeriLaunch

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)](#环境要求)

> VeriLaunch 是一个为 Verilator 打造的轻量图形界面启动器：选择 RTL/测试文件或文件夹，手动指定工作目录与顶层模块，一键编译并运行仿真，实时显示输出并将错误标红。自动归档带时间戳的运行日志，一键/自动弹出 GTKWave 查看波形，配置可保存与导入——*选好 RTL，一键运行，直接看波形*。

<p align="center"><img src="package/assets/icon_256.png" width="96" alt="VeriLaunch 图标"/></p>

---

## 功能特性

- 🗂 **文件/文件夹混选** — 支持 `.sv/.v/.svh/.vh` 文件与文件夹混合添加；文件夹递归收集，无目录排除
- 🎛 **参数手动可控** — 工作目录、`--Mdir`、顶层模块：可编辑下拉框自动列出所选文件里解析到的全部 module 名，也支持手填
- ▶ **一键仿真** — Verilator 编译 + 仿真异步执行，界面全程不卡顿
- 🌈 **实时着色日志** — 编译/仿真输出同屏显示；`%Error` 与断言失败红字、`%Warning` 橙字
- 📝 **自动归档运行日志** — 每次运行自动保存为 `工作目录/sim_<时间戳>_<OK|FAIL|STOP>.log`
- 🌊 **GTKWave 集成** — 手动一键打开最新 `.fst`，或在仿真成功后自动弹出
- 💾 **配置管理** — 设置自动记忆；配置可导出/导入 JSON，不同模块各存一份，切换随时恢复
- 📦 [AppImage](https://appimage.org) 免安装 — 单文件可执行，无需安装；系统没有 libfuse2 也能运行

## 环境要求

- Linux x86_64
- `PATH` 中装有 [Verilator](https://verilator.org) 5.x（流程基于 `--binary --timing --assert`）
- 可选：`gtkwave`（查看波形）、`libfuse2`（非必需——运行时会自动解压回退）

从源码运行需要：Python 3.9+（含 `venv` 模块）；PySide6 会自动装入本地 `.venv`，不触碰系统 Python 环境。

## 快速开始

**方式一 — AppImage**（推荐）：从 [Releases](../../releases) 下载 `verilaunch-x86_64.AppImage`：

```bash
chmod +x verilaunch-x86_64.AppImage
./verilaunch-x86_64.AppImage
```

**方式二 — 从源码运行：**

```bash
./run.sh        # 首次运行自动创建 .venv 并安装 PySide6（只写本目录）
```

**自行构建 AppImage：**

```bash
./package/build.sh   # 生成 package/verilaunch-x86_64.AppImage（附带 .tar.gz）
```

## 使用说明

1. **仿真文件**：添加 `.sv/.v` 文件或整个文件夹（可混选，递归收集）
2. **工作目录**：手动指定；`--Mdir`、波形相对路径和运行日志都以此为根
3. **顶层模块**：从下拉框选择（自动列出所选文件里的所有 module），也可手填
4. **运行**：点 `▶ 开始仿真` 后编译与仿真输出实时滚动，错误红字显示
5. 每次运行日志自动保存为 `工作目录/sim_<时间戳>_<OK|FAIL|STOP>.log`
6. 配置可**保存/导入**（JSON），不同模块各存一份，切换随时恢复

## AI 协作开发声明

> 本项目在 AI 编程助手（大语言模型结对编程）的协助下开发。维护者负责提出需求、设计决策、全部功能的实测验证与发布；主要代码与打包脚本由 AI 生成并经人工复核迭代。我们如实披露这一开发方式，供使用者在评估代码与参与贡献时参考。

## 项目状态

`v0.1.0` — 早期版本，细节仍在打磨；欢迎提交 issue 和 PR。

说明：VeriLaunch **与 Verilator 官方项目无关**（Verilator 由 Antmicro 及社区维护），名称中对 "Verilator" 的使用仅为描述性说明，指明本工具启动的是哪个仿真器。

## 许可

[MIT](LICENSE) © 2026 li yongxuan
