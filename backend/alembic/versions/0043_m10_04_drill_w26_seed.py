"""W26 · drill 文案 tips 补齐 + 4 条短杆 seed（推杆/切杆 → ~30 条）.

revision: 0043_m10_04_drill_w26_seed
down_revision: 0042_m7_13_selected_swing_index
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043_m10_04_drill_w26_seed"
down_revision: Union[str, None] = "0042_m7_13_selected_swing_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# W26-A · 推杆/切杆 drill 补 tips（0041 插入时 tips 为空）
TIPS_BY_ID: dict[str, list[str]] = {
    "drill_one_hand_putt": [
        "握压约 3/10，避免手指单独发力",
        "推完停留 1 秒再抬头看球线",
    ],
    "drill_gate_putt": [
        "门宽先宽后窄，杆头通过时勿抬离地面",
        "杆面方正时球更易从门中滚出",
    ],
    "drill_distance_ladder": [
        "同一节奏比同一力度更重要",
        "记录每档落点分散度，分散大则放慢节奏",
    ],
    "drill_eyes_closed_putt": [
        "从 1 米短推建立钟摆感再加长",
        "闭眼时更依赖肩臂一体，勿用手腕补距离",
    ],
    "drill_clock_putt": [
        "每点位推 3 球再换点，避免只练顺坡位",
        "读线以落点圈为首要目标",
    ],
    "drill_chip_land_spot": [
        "先选落点再选杆，落点比洞更重要",
        "打厚/打薄都回到「落点是否命中」复盘",
    ],
    "drill_low_runner": [
        "杆身前倾、球位略后，减少挑球倾向",
        "送杆短收，让球低滚通过果岭",
    ],
    "drill_hinge_chip": [
        "上杆小铰链、下杆加速，勿长扫",
        "触球后杆头仍向目标方向延伸",
    ],
}

NEW_DRILLS: list[dict] = [
    {
        "id": "drill_wrist_lock_putt",
        "name": "锁腕推杆",
        "category": "putting",
        "target_issues": ["putting_wrist_hinge"],
        "description": "固定手腕角度，让肩部钟摆主导推击。",
        "steps": [
            "短推 1 米，手腕角度保持不变",
            "推击时只动肩臂，观察杆头路径",
            "每组 10 球，记录偏离方向",
        ],
        "tips": [
            "可在推杆握把处贴胶带作手腕角度参照",
            "若球左右乱飞，先缩短距离再恢复",
        ],
        "duration_minutes": 12,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 115,
    },
    {
        "id": "drill_backstroke_pause",
        "name": "回摆停顿推杆",
        "category": "putting",
        "target_issues": ["putting_short_backstroke", "putting_decel_stroke"],
        "description": "回摆到位后短暂停顿，再加速通过球。",
        "steps": [
            "上杆到舒适幅度后停 0.5 秒",
            "下杆加速通过球，送杆对称",
            "同距离推 10 球记录进洞率",
        ],
        "tips": [
            "停顿是为了确认回摆长度，不是刻意减速击球",
            "送杆长度应与回摆大致对称",
        ],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 116,
    },
    {
        "id": "drill_alignment_chip",
        "name": "对准线切杆",
        "category": "chipping",
        "target_issues": ["chipping_alignment_off"],
        "description": "用地面参照线校正脚线、球位与目标线。",
        "steps": [
            "地面贴杆或绳作目标线",
            "脚线与目标线平行，球位居中偏后",
            "切 10 球观察初始方向",
        ],
        "tips": [
            "先练方向再练距离",
            "杆面与目标线垂直时初始方向更稳",
        ],
        "duration_minutes": 12,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 123,
    },
    {
        "id": "drill_accelerate_through",
        "name": "加速通过切杆",
        "category": "chipping",
        "target_issues": ["chipping_decel", "chipping_scoop"],
        "description": "强调触球后杆头仍向目标加速，避免减速或挑球。",
        "steps": [
            "上杆至腰高以内",
            "触球瞬间杆头仍向目标加速",
            "送杆时胸朝向目标",
        ],
        "tips": [
            "减速击球常伴随挑球，先练低弹道滚进",
            "可想象杆头要「穿过」球而非「舀」球",
        ],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 124,
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    for drill_id, tips in TIPS_BY_ID.items():
        conn.execute(
            sa.text(
                """
                UPDATE drills
                SET tips = CAST(:tips AS jsonb), updated_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": drill_id, "tips": json.dumps(tips, ensure_ascii=False)},
        )

    for raw in NEW_DRILLS:
        tips = raw.get("tips", [])
        d = {k: v for k, v in raw.items() if k != "tips"}
        conn.execute(
            sa.text(
                """
                INSERT INTO drills (
                    id, name, name_en, target_issues, description, steps, tips,
                    duration_minutes, sets, difficulty, illustration_url, video_url,
                    sort_order, is_active, category, created_at, updated_at
                ) VALUES (
                    :id, :name, NULL, CAST(:target_issues AS jsonb), :description,
                    CAST(:steps AS jsonb), CAST(:tips AS jsonb),
                    :duration_minutes, :sets, :difficulty, NULL, NULL,
                    :sort_order, true, :category, NOW(), NOW()
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                **d,
                "tips": json.dumps(tips, ensure_ascii=False),
                "target_issues": json.dumps(d["target_issues"]),
                "steps": json.dumps(d["steps"], ensure_ascii=False),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for d in NEW_DRILLS:
        conn.execute(sa.text("DELETE FROM drills WHERE id = :id"), {"id": d["id"]})
    for drill_id in TIPS_BY_ID:
        conn.execute(
            sa.text(
                """
                UPDATE drills
                SET tips = '[]'::jsonb, updated_at = NOW()
                WHERE id = :id
                """
            ),
            {"id": drill_id},
        )
