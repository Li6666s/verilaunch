#!/usr/bin/env python3
"""离线生成 AppImage 图标（192-256px png）。需要 QT_QPA_PLATFORM=offscreen 环境。"""

from __future__ import annotations
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QApplication

SIZE = 256


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    out = Path(__file__).resolve().parent / "assets"
    out.mkdir(exist_ok=True)
    img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # 深色圆角底
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#16324a"))
    p.drawRoundedRect(8, 8, SIZE - 16, SIZE - 16, 48, 48)
    # 示波器式方波轨迹（绿色）
    path = QPainterPath(QPointF(34, 168))
    pts = [
        (72, 168), (72, 100), (112, 100), (112, 190),
        (152, 190), (152, 66), (196, 66), (196, 168), (224, 168),
    ]
    for x, y in pts:
        path.lineTo(QPointF(x, y))
    pen = QPen(QColor("#7de07a"))
    pen.setWidthF(9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPath(path)
    # 蓝色状态点缀
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#5fb8ff"))
    p.drawEllipse(QPointF(SIZE / 2, 224), 7, 7)
    p.end()

    target = out / "icon_256.png"
    img.save(str(target), "PNG")
    print(f"图标已生成: {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
