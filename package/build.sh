#!/bin/bash
# 打包 verilaunch：PyInstaller onedir + AppImage（附带 tar.gz 目录包作后备）。
#
# 产物（都在本目录）：
#   verilaunch-<arch>.AppImage   双击即可运行；无 libfuse2 时自动解压运行
#   verilaunch-<arch>.tar.gz     便携目录包，解压后跑 verilaunch/bin
#   build/ dist/ AppDir/ tools/         中间产物（已 gitignore）
#
# 前置条件：仓库根目录的 .venv 存在（没有则自动调 ../setup_venv.sh）。
# 注意：不安装任何系统包；appimagetool 用 --appimage-extract-and-run 运行。
set -euo pipefail
cd "$(dirname "$0")"

APP=verilaunch
ARCH=$(uname -m)
rm -rf dist build AppDir
mkdir -p assets

# ---- 1) 生成图标（如不存在） -------------------------------------------------
if [ ! -f assets/icon_256.png ]; then
  echo "== 生成图标 =="
  QT_QPA_PLATFORM=offscreen ../.venv/bin/python gen_icon.py
fi

# ---- 2) 虚拟环境 + PyInstaller（只写 .venv） ---------------------------------
if [ ! -x ../.venv/bin/python ]; then
  ../setup_venv.sh
fi
echo "== 安装 PyInstaller 到 .venv =="
../.venv/bin/pip install -q pyinstaller

echo "== PyInstaller 打包（onedir）=="
../.venv/bin/pyinstaller --noconfirm --clean \
  --name "$APP" \
  --distpath dist --workpath build --specpath . \
  --exclude-module tkinter \
  ../main.py

# ---- 3) 组装 AppDir ---------------------------------------------------------
echo "== 组装 AppDir =="
mkdir -p AppDir/usr/bin
cp -r "dist/$APP" "AppDir/usr/bin/"
chmod +x "AppDir/usr/bin/$APP/$APP"
cp "$APP.desktop" "AppDir/$APP.desktop"
cp assets/icon_256.png "AppDir/$APP.png"
cp assets/icon_256.png "AppDir/.DirIcon"
cp AppRun AppDir/AppRun
chmod +x AppDir/AppRun

# ---- 4) 便携目录包 ----------------------------------------------------------
tar -C dist -czf "$APP-$ARCH.tar.gz" "$APP"
echo "已生成: $(pwd)/$APP-$ARCH.tar.gz"

# ---- 5) AppImage ------------------------------------------------------------
TOOL="tools/appimagetool-$ARCH.AppImage"
if [ ! -x "$TOOL" ]; then
  echo "== 下载 appimagetool（仅放到 package/tools，不装系统）=="
  mkdir -p tools
  URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$ARCH.AppImage"
  curl -L --fail -o "$TOOL" "$URL"
  chmod +x "$TOOL"
fi

echo "== 制作 AppImage =="
"$TOOL" --appimage-extract-and-run --no-appstream \
  AppDir "$APP-$ARCH.AppImage"
chmod +x "$APP-$ARCH.AppImage"

echo
echo "== 打包完成 =="
ls -lh "$APP-$ARCH.AppImage" "$APP-$ARCH.tar.gz"
du -sh "AppDir"
