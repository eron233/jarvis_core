"""Gera icone .ico a partir do SVG oficial, usando Qt e Pillow do runner."""
from pathlib import Path
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from PIL import Image

root = Path(__file__).resolve().parents[1]
renderer = QSvgRenderer(str(root / "interface/native_app/assets/genesis_zero.svg"))
if not renderer.isValid():
    raise SystemExit("Logo Genesis SVG invalida")
app = QApplication.instance() or QApplication(["genesis-icon"])
image = QImage(256, 256, QImage.Format_ARGB32)
image.fill(Qt.transparent)
painter = QPainter(image)
renderer.render(painter)
painter.end()
# PyInstaller --clean removes build/, so icon must live OUTSIDE that directory.
out = root / ".build-assets"
out.mkdir(parents=True, exist_ok=True)
png = out / "genesis_logo.png"
ico = out / "genesis.ico"
if not image.save(str(png)):
    raise SystemExit("Falha na renderizacao do SVG")
Image.open(png).save(ico, format="ICO", sizes=[
    (16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256),
])
print("Generated", ico, "bytes", ico.stat().st_size)
