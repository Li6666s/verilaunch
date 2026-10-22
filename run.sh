#!/bin/bash
# 启动 Verilator 仿真 GUI。首次运行会自动调用 setup_venv.sh 建立虚拟环境。
# 也可以手动:  source .venv/bin/activate && python main.py
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "首次运行：创建虚拟环境 .venv 并安装 PySide6（只写入本目录）..."
  ./setup_venv.sh
fi
exec .venv/bin/python main.py "$@"
