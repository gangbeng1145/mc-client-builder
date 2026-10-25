import sys
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)
n = 256
img = QImage(n, n, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)

bg = QPainterPath()
bg.addRoundedRect(QRectF(6, 6, n - 12, n - 12), 58, 58)
grad = QLinearGradient(0, 0, n, n)
grad.setColorAt(0, QColor("#4c8dff"))
grad.setColorAt(1, QColor("#6a5cff"))
p.fillPath(bg, grad)

# 像素草方块
x, y, w = 58, 58, 140
p.setPen(Qt.NoPen)
p.setBrush(QColor("#6fbf4a"))
p.drawRect(QRectF(x, y, w, 44))
p.setBrush(QColor("#57a63c"))
p.drawRect(QRectF(x, y, w, 10))
p.setBrush(QColor("#8b5a3c"))
p.drawRect(QRectF(x, y + 44, w, w - 44))

# 像素点缀
p.setBrush(QColor("#4f9436"))
for px, py, ps in [(x + 18, y + 16, 12), (x + 74, y + 8, 10), (x + 108, y + 22, 12)]:
    p.drawRect(QRectF(px, py, ps, ps))
p.setBrush(QColor("#a06a48"))
for px, py, ps in [(x + 22, y + 70, 16), (x + 92, y + 96, 18), (x + 46, y + 112, 12), (x + 110, y + 60, 12)]:
    p.drawRect(QRectF(px, py, ps, ps))
p.setBrush(QColor("#744a30"))
for px, py, ps in [(x + 70, y + 70, 10), (x + 30, y + 98, 10), (x + 96, y + 118, 12)]:
    p.drawRect(QRectF(px, py, ps, ps))

p.end()
out = Path(__file__).resolve().parent / "assets"
out.mkdir(parents=True, exist_ok=True)
img.save(str(out / "icon.png"))
print("saved", out / "icon.png")
