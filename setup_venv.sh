#!/bin/bash
# 在本目录创建 .venv 并安装 requirements.txt（PySide6）。
# 只写入本目录下的 .venv/，不安装、不修改任何系统级 Python 包。
# 依赖：系统 python3 需带 venv 模块（Debian: sudo apt install python3-venv）。
set -e
cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

.venv/bin/python -c "import PySide6; print('PySide6', PySide6.__version__, '就绪')"
echo "虚拟环境已建好: $(pwd)/.venv"
