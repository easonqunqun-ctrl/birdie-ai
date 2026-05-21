#!/usr/bin/env python3
"""
生成 tabBar 图标（8 张 81×81 PNG）。

设计目标（**正式版**，2026-05-20 代设计师出图）：
- 与品牌主色靛蓝 `#1a237e` 完全对齐（与 `client/src/app.config.ts::tabBar.selectedColor`、
  `client/src/app.scss::--color-primary` 三处同源）；默认态 `#888888` 与
  `tabBar.color` 一致。
- 4 个 metaphor 直观、与产品语义一致的形状：
    home     - 屋顶 + 屋身（首页 / 家）
    coach    - 对话气泡（AI 教练 = 对话）
    training - 球场旗杆 + 三角旗（高尔夫训练标志物）
    profile  - 人形头像（圆头 + 半圆肩膀）
- **4× 超采样抗锯齿**：每像素取 4×4 = 16 个子样本平均，让斜边/圆弧不显锯齿。
  在 81×81 输出尺寸下 PNG 边缘灰度过渡平滑，比原 W8 占位的硬边显著精致。

颜色：
  - 默认态  `#888888`（与 `app.config.ts::tabBar.color` 完全一致）
  - 激活态  `#1a237e`（与 `app.config.ts::tabBar.selectedColor` 完全一致；
                    与 `app.scss::--color-primary` 同源）

运行：
  python3 scripts/gen_tab_icons.py

输出：
  client/src/assets/tab/{home,coach,training,profile}{,_active}.png

实现仍**无第三方依赖**（纯 struct + zlib 手搓 PNG），CI 机也能跑；超采样会让生成
耗时从原来的 ~30ms 升到 ~500ms（仍秒级）。

历史：
  - W8（2026-04）：占位版 8 张几何图形（圆 / 方 / 三角 / 菱形），激活态深绿 #0f3d2e
  - 2026-05-20：本次出"正式版"，删除占位 drift（详见
    `docs/release-notes/W8-tab-icons.md`）
"""

from __future__ import annotations

import os
import struct
import sys
import zlib
from typing import Callable, Tuple

SIZE = 81
# 4× 超采样：每个像素拆 4×4 子像素做覆盖率估算，得到平滑边缘的 alpha
SUPERSAMPLE = 4
SUB_PER_PIXEL = SUPERSAMPLE * SUPERSAMPLE

FILL_DEFAULT: Tuple[int, int, int] = (0x88, 0x88, 0x88)  # 与 app.config.ts::tabBar.color 一致
FILL_ACTIVE: Tuple[int, int, int] = (0x1A, 0x23, 0x7E)  # 与 selectedColor / --color-primary 一致


# ============================================================
# 形状定义：参数都按 81×81 标尺，几何中心 (40, 40)
# 每个 shape(x, y) 返回 bool（True = 该子样本在前景内）
# ============================================================


def in_house(x: float, y: float) -> bool:
    """房屋：屋顶等腰三角 + 屋身矩形。

    顶点 (40, 13)，屋檐底 y=38（屋檐宽度 12..68 → 屋顶比屋身略宽，更具房屋感）；
    屋身 (18, 38) - (62, 68)；
    门洞挖空：(34, 50) - (46, 68)（让"家"的语义一眼可读）。
    """
    # 屋顶（含屋檐凸出）
    if 13 <= y <= 38:
        half_w = (y - 13) / (38 - 13) * 28  # 顶宽 0、底宽 56
        if abs(x - 40) <= half_w:
            return True
    # 屋身
    if 38 <= y <= 68 and 18 <= x <= 62:
        # 门洞挖空
        if 34 <= x <= 46 and 50 <= y <= 68:
            return False
        return True
    return False


def in_bubble(x: float, y: float) -> bool:
    """AI 教练 = 对话气泡：圆角矩形 + 左下尾巴小三角。

    主体矩形 (12, 16) - (68, 52)，圆角半径 9；尾巴朝左下 (24, 52) - (36, 52) → (28, 64)。
    """
    # 圆角矩形主体
    if 12 <= x <= 68 and 16 <= y <= 52:
        r = 9
        # 四个圆角区：在角象限内时检查距离圆心 ≤ r
        for cx, cy, sx, sy in [
            (12 + r, 16 + r, -1, -1),  # 左上
            (68 - r, 16 + r, 1, -1),  # 右上
            (12 + r, 52 - r, -1, 1),  # 左下
            (68 - r, 52 - r, 1, 1),  # 右下
        ]:
            if (x - cx) * sx > 0 and (y - cy) * sy > 0:
                if (x - cx) ** 2 + (y - cy) ** 2 > r * r:
                    return False
        return True
    # 尾巴（左下三角；尖端朝左下，给气泡"指向用户"的方向感）
    if 52 <= y <= 64:
        # 三角顶点 (28, 64)，上边连 (24, 52)–(36, 52)
        # 在该梯形内：随 y 增加，左右边界向尖端收敛
        t = (y - 52) / (64 - 52)  # 0..1
        left = 24 + t * (28 - 24)  # 24 → 28
        right = 36 - t * (36 - 28)  # 36 → 28
        if left <= x <= right:
            return True
    return False


def in_flag(x: float, y: float) -> bool:
    """高尔夫训练 = 球场旗杆 + 三角旗。

    旗杆细长矩形 (39, 14) - (42, 68)，3px 宽，54px 高；
    三角旗在杆顶右侧：顶点 (42, 14) → (66, 22) → (42, 30)，朝右指向运动方向；
    底座："洞" — 在杆脚 y=68 周围画窄椭圆形短线 (32, 66) - (50, 68)。
    """
    # 旗杆
    if 39 <= x <= 42 and 14 <= y <= 68:
        return True
    # 旗子三角（右翼）：在 (42,14)-(66,22)-(42,30) 三角形内
    if 42 <= x <= 66 and 14 <= y <= 30:
        # 旗子上沿：y = 14 + (x-42)/(66-42) * (22-14) = 14 + (x-42)/3
        # 旗子下沿：y = 30 - (x-42)/(66-42) * (30-22) = 30 - (x-42)/3
        if 14 + (x - 42) / 3 <= y <= 30 - (x - 42) / 3:
            return True
    # 底座（短横线："洞"的暗示，让"训练场"语义更明确）
    if 32 <= x <= 50 and 66 <= y <= 68:
        return True
    return False


def in_person(x: float, y: float) -> bool:
    """个人 = 头 + 半圆肩膀。

    头：圆心 (40, 26)，半径 11 → 占 y∈[15, 37]；
    肩膀：椭圆上半，圆心 (40, 70)，长短轴 22 → 仅 y≤70 部分有效，最高点 y=48；
    自然空隙：头底 y=37 与肩膀顶 y=48 之间 y∈[38, 47] 椭圆方程自然为空（不在椭圆内），
    无需额外"挖缝隙"，视觉上头与肩自然分离。
    """
    # 头
    if (x - 40) ** 2 + (y - 26) ** 2 <= 11 * 11:
        return True
    # 肩膀（椭圆上半；y > 70 的部分由 if 过滤）
    if y <= 70 and (x - 40) ** 2 / (22 * 22) + (y - 70) ** 2 / (22 * 22) <= 1:
        return True
    return False


SHAPES: dict[str, Callable[[float, float], bool]] = {
    "home": in_house,
    "coach": in_bubble,
    "training": in_flag,
    "profile": in_person,
}


# ============================================================
# 渲染：4× 超采样抗锯齿 + PNG 编码
# ============================================================


def _coverage(shape: Callable[[float, float], bool], px: int, py: int) -> int:
    """返回该像素的前景覆盖度 0..255（4×4 子样本平均）。"""
    hit = 0
    for sy in range(SUPERSAMPLE):
        # 子样本中心：px + (0.5 + sy) / SUPERSAMPLE → 在像素方格内均匀分布
        y = py + (sy + 0.5) / SUPERSAMPLE
        for sx in range(SUPERSAMPLE):
            x = px + (sx + 0.5) / SUPERSAMPLE
            if shape(x, y):
                hit += 1
    return (hit * 255) // SUB_PER_PIXEL


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def render_png(shape: Callable[[float, float], bool], rgb: Tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)  # PNG filter type None
        for x in range(SIZE):
            a = _coverage(shape, x, y)
            if a == 0:
                raw.extend((0, 0, 0, 0))
            else:
                raw.extend((r, g, b, a))

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
