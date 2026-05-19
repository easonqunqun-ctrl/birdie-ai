#!/usr/bin/env python3
"""
生成 W8-T2 tabBar 占位图标（8 张 81×81 PNG）。

背景：设计师尚未出图，W8 内部测试先用纯色几何图形占位；
W9 上线前由设计师替换同名文件即可，不需要改 app.config.ts。

图标形状约定（仅用于视觉区分 4 个 tab）：
  - home     : 实心圆
  - coach    : 实心正方形
  - training : 实心等腰三角
  - profile  : 实心菱形

颜色（**W8 占位**；W9 正式出图后会被设计师覆盖，本脚本只是临时工具）：
  - 默认态 : #9ca3af（灰）
  - 激活态 : #0f3d2e（**早期"深绿"占位；与当前品牌主色 #1a237e 靛蓝存在 drift**——
                      正式 token 见 `client/src/app.scss`，本占位不要被业务页面当 token 引用）

运行：
  python3 scripts/gen_tab_icons.py
输出：
  client/src/assets/tab/{home,coach,training,profile}{,_active}.png

实现无第三方依赖（纯 struct + zlib 手搓 PNG），CI 机也能跑。
"""

from __future__ import annotations

import os
import struct
import sys
import zlib
from typing import Callable, Tuple

SIZE = 81
CENTER = (SIZE - 1) / 2
FILL_DEFAULT: Tuple[int, int, int] = (0x9C, 0xA3, 0xAF)
FILL_ACTIVE: Tuple[int, int, int] = (0x0F, 0x3D, 0x2E)


def in_circle(x: int, y: int) -> bool:
    dx, dy = x - CENTER, y - CENTER
    return dx * dx + dy * dy <= 28 * 28


def in_square(x: int, y: int) -> bool:
    return 15 <= x <= SIZE - 16 and 15 <= y <= SIZE - 16


def in_triangle(x: int, y: int) -> bool:
    # 正三角向上：底边 y=65，顶点 y=15
    if y < 15 or y > 65:
        return False
    half_width = (y - 15) / (65 - 15) * 28
    return abs(x - CENTER) <= half_width


def in_diamond(x: int, y: int) -> bool:
    return abs(x - CENTER) + abs(y - CENTER) <= 28


SHAPES: dict[str, Callable[[int, int], bool]] = {
    "home": in_circle,
    "coach": in_square,
    "training": in_triangle,
    "profile": in_diamond,
}


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def render_png(shape: Callable[[int, int], bool], rgb: Tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)  # PNG filter type None
        for x in range(SIZE):
            if shape(x, y):
                raw.extend((r, g, b, 255))
            else:
                raw.extend((0, 0, 0, 0))

    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), level=9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "client", "src", "assets", "tab")
    os.makedirs(out_dir, exist_ok=True)

    for name, shape in SHAPES.items():
        for suffix, rgb in ((".png", FILL_DEFAULT), ("_active.png", FILL_ACTIVE)):
            data = render_png(shape, rgb)
            out = os.path.join(out_dir, f"{name}{suffix}")
            with open(out, "wb") as f:
                f.write(data)
            print(f"wrote {out} ({len(data)} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
