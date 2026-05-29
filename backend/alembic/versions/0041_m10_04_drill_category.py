"""M10-04 · drills.category 列 + 推杆/切杆扩库 seed.

revision: 0041_m10_04_drill_category
down_revision: 0040_m10_03_target_yardage
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041_m10_04_drill_category"
down_revision: Union[str, None] = "0040_m10_03_target_yardage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_DRILLS: list[dict] = [
    {
        "id": "drill_one_hand_putt",
        "name": "单手推杆练习",
        "category": "putting",
        "target_issues": ["putting_unstable_pendulum"],
        "description": "强化肩部钟摆主导，减少手腕独立发力。",
        "steps": ["非主导手背后或口袋", "主导手推 10 球", "关注肩臂一体"],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 110,
    },
    {
        "id": "drill_gate_putt",
        "name": "门型推杆练习",
        "category": "putting",
        "target_issues": ["putting_face_open"],
        "description": "用 tees 做门型，约束杆头路径与杆面方正。",
        "steps": ["球两侧各插 tee 做门", "推杆通过门型", "逐渐缩短门宽"],
        "duration_minutes": 12,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 111,
    },
    {
        "id": "drill_distance_ladder",
        "name": "推杆距离梯",
        "category": "putting",
        "target_issues": ["putting_rushed_tempo", "putting_slow_tempo"],
        "description": "3/6/9 米递进，训练节奏与距离感。",
        "steps": ["标记 3 个距离", "同一节奏推各 5 球", "记录落点分散度"],
        "duration_minutes": 20,
        "sets": 1,
        "difficulty": "medium",
        "sort_order": 112,
    },
    {
        "id": "drill_eyes_closed_putt",
        "name": "闭眼推杆",
        "category": "putting",
        "target_issues": ["putting_head_moved"],
        "description": "减少视觉依赖，稳定头部与钟摆感。",
        "steps": ["短距离 1 米起", "闭眼完成推杆", "逐步加长"],
        "duration_minutes": 10,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 113,
    },
    {
        "id": "drill_clock_putt",
        "name": "钟面推杆",
        "category": "putting",
        "target_issues": ["putting_unstable_pendulum", "putting_face_open"],
        "description": "围绕洞周 12 点位推杆，练稳定度与读线。",
        "steps": ["洞周标 4-6 点", "每点 3 球", "换点继续"],
        "duration_minutes": 18,
        "sets": 1,
        "difficulty": "medium",
        "sort_order": 114,
    },
    {
        "id": "drill_chip_land_spot",
        "name": "切杆落点练习",
        "category": "chipping",
        "target_issues": ["chipping_chunked", "chipping_thin"],
        "description": "先控落点再滚，建立触球前规划。",
        "steps": ["选落点毛巾/圈", "切到落点停", "记录过/短"],
        "duration_minutes": 15,
        "sets": 4,
        "difficulty": "easy",
        "sort_order": 120,
    },
    {
        "id": "drill_low_runner",
        "name": "低滚切杆",
        "category": "chipping",
        "target_issues": ["chipping_scoop", "chipping_over_swing"],
        "description": "杆身前倾、短幅度，练低弹道滚进。",
        "steps": ["球位偏后", "杆身前倾", "短切低滚 10 球"],
        "duration_minutes": 12,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 121,
    },
    {
        "id": "drill_hinge_chip",
        "name": "铰链切杆",
        "category": "chipping",
        "target_issues": ["chipping_decel", "chipping_over_swing"],
        "description": "上杆小铰链、下杆加速通过球。",
        "steps": ["上杆腕铰链", "下杆加速", "送杆短收"],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 122,
    },
    {
        "id": "drill_mirror_setup",
        "name": "镜子站位练习",
        "category": "full_swing",
        "target_issues": ["setup_posture", "spine_angle_loss"],
        "description": "对照镜子校正站姿与脊柱角。",
        "steps": ["侧对镜子", "检查脊柱角", "半挥保持角度"],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 130,
    },
    {
        "id": "drill_feet_together",
        "name": "并脚平衡挥杆",
        "category": "full_swing",
        "target_issues": ["sway", "loss_of_balance"],
        "description": "缩小支撑面，强化挥杆平衡。",
        "steps": ["双脚并拢", "7 号铁半挥", "保持稳定"],
        "duration_minutes": 12,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 131,
    },
    {
        "id": "drill_pause_top",
        "name": "顶点停顿练习",
        "category": "full_swing",
        "target_issues": ["overswing", "reverse_pivot"],
        "description": "上杆顶点多停 1 秒，改善转换顺序。",
        "steps": ["上杆到顶停 1 秒", "再下杆", "半速重复"],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 132,
    },
    {
        "id": "drill_step_through",
        "name": "迈步送杆练习",
        "category": "full_swing",
        "target_issues": ["early_extension", "weight_shift_poor"],
        "description": "送杆时迈步，强化重心转移。",
        "steps": ["正常上杆", "击球后迈步向前", "10 球一组"],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 133,
    },
]


def upgrade() -> None:
    op.add_column(
        "drills",
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'full_swing'"),
        ),
    )
    op.create_check_constraint(
        "chk_drill_category",
        "drills",
        "category IN ('full_swing', 'putting', 'chipping', 'short_game', 'general')",
    )
    conn = op.get_bind()
    for d in NEW_DRILLS:
        conn.execute(
            sa.text(
                """
                INSERT INTO drills (
                    id, name, name_en, target_issues, description, steps, tips,
                    duration_minutes, sets, difficulty, illustration_url, video_url,
                    sort_order, is_active, category, created_at, updated_at
                ) VALUES (
                    :id, :name, NULL, CAST(:target_issues AS jsonb), :description,
                    CAST(:steps AS jsonb), '[]'::jsonb,
                    :duration_minutes, :sets, :difficulty, NULL, NULL,
                    :sort_order, true, :category, NOW(), NOW()
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                **d,
                "target_issues": json.dumps(d["target_issues"]),
                "steps": json.dumps(d["steps"]),
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for d in NEW_DRILLS:
        conn.execute(sa.text("DELETE FROM drills WHERE id = :id"), {"id": d["id"]})
    op.drop_constraint("chk_drill_category", "drills", type_="check")
    op.drop_column("drills", "category")
