"""用富途牛牛 logo（nn_logo.png，来自 futunn.com 的 og:image）生成多尺寸的 futu.ico。
任务栏、标题栏、Alt+Tab、资源管理器在不同缩放比例下取不同尺寸，只有 32x32 时高分屏上会发糊。
<=48 用 BMP 格式（兼容所有 Windows 组件），更大的用 PNG 压缩。

    python launcher/make_icon.py
"""

import struct
import sys
from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter

HERE = Path(__file__).resolve().parent
SRC = HERE / "nn_logo.png"
OUT = HERE / "futu.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def square(img: QImage) -> QImage:
    side = max(img.width(), img.height())
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.drawImage((side - img.width()) // 2, (side - img.height()) // 2, img)
    p.end()
    return canvas


def png_bytes(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def bmp_bytes(img: QImage) -> bytes:
    """ICO 里的 BMP：BITMAPINFOHEADER（高度是两倍：颜色 + AND 掩码），BGRA 自下而上，再跟 1bpp AND 掩码"""
    n = img.width()
    img = img.convertToFormat(QImage.Format.Format_ARGB32)  # 内存里就是 BGRA
    header = struct.pack("<IiiHHIIiiII", 40, n, n * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    stride = n * 4
    bits = img.constBits().asstring(img.sizeInBytes())
    rows = b"".join(bits[y * img.bytesPerLine(): y * img.bytesPerLine() + stride] for y in range(n - 1, -1, -1))
    mask_stride = ((n + 31) // 32) * 4
    mask = bytearray()
    for y in range(n - 1, -1, -1):
        row = bytearray(mask_stride)
        for x in range(n):
            if (img.pixel(x, y) >> 24) == 0:
                row[x // 8] |= 0x80 >> (x % 8)
        mask += row
    return header + rows + bytes(mask)


def main():
    QGuiApplication(sys.argv)
    src = square(QImage(str(SRC)))
    if src.isNull():
        sys.exit(f"读不到 {SRC}")
    images = []
    for size in SIZES:
        img = src.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        images.append((size, png_bytes(img) if size > 48 else bmp_bytes(img)))
    offset = 6 + 16 * len(images)
    head = struct.pack("<HHH", 0, 1, len(images))
    entries, blobs = b"", b""
    for size, data in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    OUT.write_bytes(head + entries + blobs)
    print(f"写入 {OUT}：{', '.join(str(s) for s in SIZES)}，{OUT.stat().st_size} 字节")


if __name__ == "__main__":
    main()
