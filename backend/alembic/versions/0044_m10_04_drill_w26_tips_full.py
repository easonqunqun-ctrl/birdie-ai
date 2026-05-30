"""W26 收尾 · 全库 drill tips + 第 30 条推杆 seed.

revision: 0044_m10_04_drill_w26_tips_full
down_revision: 0043_m10_04_drill_w26_seed
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044_m10_04_drill_w26_tips_full"
down_revision: Union[str, None] = "0043_m10_04_drill_w26_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# W26-A · 全挥杆 13 条原始 + 0041 四条 full_swing 补 tips
FULL_SWING_TIPS: dict[str, list[str]] = {
    "drill_towel_arm": [
        "毛巾夹在肘下而非腋下，更容易感知双臂连接",
        "半挥稳定后再加长，避免为了不掉毛巾而僵肩",
    ],
    "drill_impact_bag": [
        "慢速击打时杆身前倾角保持不变",
        "感受延迟释放，而非用手腕「甩」向包",
    ],
    "drill_half_swing": [
        "节奏 3:1：上杆 3 拍、下杆 1 拍",
        "下杆时髋部先启动，上身跟随",
    ],
    "drill_inside_path": [
        "练习杆仅作引导，勿碰杆头",
        "下杆时胸口仍朝向球位，避免过早转开",
    ],
    "drill_wall_butt": [
        "臀部轻贴墙即可，勿顶死失去旋转",
        "下杆时若臀离墙，说明提前伸展",
    ],
    "drill_hip_rotation": [
        "旋转时脚踵不离地，避免用侧移代替转髋",
        "杆横放髋前，只看髋部转动幅度",
    ],
    "drill_mirror_spine": [
        "setup 与 impact 脊柱角差异目标 < 5°",
        "空挥先看镜子，再上球验证",
    ],
    "drill_weight_shift": [
        "口令「后-前-收」与挥杆同步，勿抢节奏",
        "收杆时前脚承重约 80%",
    ],
    "drill_backswing_stop": [
        "停 2 秒是为了确认转肩幅度，不是憋气",
        "肩转约 90° 即可，勿追杆头高度",
    ],
    "drill_shoulder_turn": [
        "抱肩旋转时髋部尽量稳定",
        "左肩触下巴为参考，勿过度抬肩",
    ],
    "drill_plane_board": [
        "板面角度与目标肩平面一致",
        "杆头沿板面移动，避免「掏」或「挑」",
    ],
    "drill_alignment_stick": [
        "脚线、膝线、肩线三线平行",
        "setup 练 10 次再击球，养成一致站位",
    ],
    "drill_grip_checkpoint": [
        "握压 4/10：能控杆又不捏死",
        "每次改握后先空挥 3 次再打球",
    ],
    "drill_mirror_setup": [
        "侧对镜看脊柱角与球位关系",
        "半挥时镜中脊柱角应基本不变",
    ],
    "drill_feet_together": [
        "并脚半挥先稳，再尝试全挥",
        "失衡说明重心或节奏需放慢",
    ],
    "drill_pause_top": [
        "顶点停 1 秒感受加载，不是刻意减速下杆",
        "转换时下半身先动",
    ],
    "drill_step_through": [
        "迈步在击球后自然发生，勿提前跳步",
        "送杆完成后重心应在前脚",
    ],
}

NEW_DRILL: dict = {
    "id": "drill_string_line_putt",
    "name": "绳线瞄准推杆",
    "category": "putting",
    "target_issues": ["putting_aim_off"],
    "description": "用地面绳线校准推杆线与目标线，减少瞄准偏差。",
    "steps": [
        "洞与球位之间拉一条绳/杆作目标线",
        "推杆头沿目标线通过，球从线中滚出",
        "同距离推 10 球记录左右偏离",
    ],
    "tips": [
        "先练 1 米直推再加长",
        "杆头路径比杆面更重要时，先对齐脚线与目标线",
    ],
    "duration_minutes": 12,
    "sets": 3,
    "difficulty": "easy",
    "sort_order": 117,
}


def upgrade() -> None:
    conn = op.get_bind()
    for drill_id, tips in FULL_SWING_TIPS.items():
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

    tips = NEW_DRILL.get("tips", [])
    payload = {k: v for k, v in NEW_DRILL.items() if k != "tips"}
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
            **payload,
            "tips": json.dumps(tips, ensure_ascii=False),
            "target_issues": json.dumps(payload["target_issues"]),
            "steps": json.dumps(payload["steps"], ensure_ascii=False),
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM drills WHERE id = :id"),
        {"id": NEW_DRILL["id"]},
    )
    for drill_id in FULL_SWING_TIPS:
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
