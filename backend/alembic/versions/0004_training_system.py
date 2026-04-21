"""W7-T3: training_plans + training_tasks + practice_logs + drills + seed

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-21

W7 训练闭环：分析完成 → 自动生成当周训练计划 → 用户打卡 → 写练习日志 → 更新 streak。
对齐 docs/03 §3.7-3.10。

seed 数据：13 条 drill，与 `client/src/constants/drillLibrary.ts` + `ai_engine/app/mock_pipeline.py::DRILL_TEMPLATES` 完全一致；
downgrade 会整表删除（drills 是静态业务数据，不在用户侧手写）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ============================================================
# 13 条 drill seed（与 client/src/constants/drillLibrary.ts 同步）
# ============================================================
# 映射：client 'difficulty' ('入门'/'进阶'/'高级') → db ('easy'/'medium'/'hard')
DRILLS_SEED: list[dict] = [
    {
        "id": "drill_towel_arm",
        "name": "毛巾夹臂练习",
        "target_issues": ["casting", "chicken_wing"],
        "description": "修复下杆时过早释放手腕，找到双臂和身体一起走的感觉。",
        "steps": [
            "取一条小毛巾，折叠后夹在双臂之间（肘关节内侧）",
            "做半挥杆练习，保持毛巾不掉落",
            "感受双臂与身体的连接感",
            "逐渐加大挥杆幅度到全挥",
            "每组 10 次挥杆，共 3 组，组间休息 30 秒",
        ],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 10,
    },
    {
        "id": "drill_impact_bag",
        "name": "击球包练习",
        "target_issues": ["casting"],
        "description": "强化击球位置的手腕前倾与身体连动，修正抛杆。",
        "steps": [
            "将击球包（或厚枕头）放在球位前方",
            "用半挥杆慢速击打，手腕保持前倾、杆头贴近身体",
            "记录手腕第一次『解锁』的感觉",
            "10 次为一组，共 3 组",
        ],
        "duration_minutes": 10,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 20,
    },
    {
        "id": "drill_half_swing",
        "name": "半挥杆节奏练习",
        "target_issues": ["over_the_top"],
        "description": "建立从内侧下杆的路径感，缓解由外到内的击球问题。",
        "steps": [
            "采用 7 号铁，站姿正常",
            "上杆只到水平位置（杆与地面平行）",
            "缓慢下杆，感受杆头从内侧进入击球区",
            "击球后跟进至同样高度",
            "每组 10 次，共 5 组，全程节奏 3:1",
        ],
        "duration_minutes": 20,
        "sets": 5,
        "difficulty": "easy",
        "sort_order": 30,
    },
    {
        "id": "drill_inside_path",
        "name": "内侧下杆路径练习",
        "target_issues": ["over_the_top"],
        "description": "用地上放杆引导下杆路径从内侧进入，消除外上内下。",
        "steps": [
            "在球位正后方 30cm 平行放一支练习杆",
            "上杆后刻意让下杆杆头沿练习杆内侧通过",
            "感受上半身被动、下半身主动的发力顺序",
            "每组 10 次，共 3 组",
        ],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 40,
    },
    {
        "id": "drill_wall_butt",
        "name": "臀贴墙练习",
        "target_issues": ["early_extension", "reverse_spine"],
        "description": "保持臀部与墙接触，避免下杆髋部前移（提前伸展 / 反向脊柱通用）。",
        "steps": [
            "背对墙站立，臀部轻贴墙面",
            "做上杆到下杆的镜像动作，臀部始终不离开墙",
            "感受脊柱角度在整个过程中保持不变",
            "10 次为一组，共 3 组",
        ],
        "duration_minutes": 10,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 50,
    },
    {
        "id": "drill_hip_rotation",
        "name": "髋部旋转练习",
        "target_issues": ["sway_slide", "sway_lead"],
        "description": "纠正侧移，建立髋部以脊柱为轴的旋转（而非平移）感。",
        "steps": [
            "双脚与肩同宽，将球杆横放在髋部前",
            "保持上身静止，缓慢左右旋转髋部",
            "感受髋部以脊柱为轴的旋转",
            "每次旋转幅度从小到大",
            "30 次为一组，共 3 组",
        ],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 60,
    },
    {
        "id": "drill_mirror_spine",
        "name": "镜前脊柱角度练习",
        "target_issues": ["loss_of_posture"],
        "description": "借助镜子观察整挥中脊柱角是否恒定。",
        "steps": [
            "面对落地镜做空挥",
            "观察从 setup 到 impact 脊柱前倾角的变化",
            "调整节奏直到差异 < 5°",
            "每组 10 次，共 2 组",
        ],
        "duration_minutes": 10,
        "sets": 2,
        "difficulty": "easy",
        "sort_order": 70,
    },
    {
        "id": "drill_weight_shift",
        "name": "重心转移节奏练习",
        "target_issues": ["hanging_back"],
        "description": "通过节奏口令建立『后-前-后』的重心流，修正留身。",
        "steps": [
            "站姿自然，口令『后、前、收』配合上杆 / 下杆 / 收杆",
            "收杆时感受 80% 重心在前脚",
            "对镜子检查完成姿势",
            "每组 10 次，共 3 组",
        ],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 80,
    },
    {
        "id": "drill_backswing_stop",
        "name": "上杆截停练习",
        "target_issues": ["over_rotation"],
        "description": "防止过度转肩，控制上杆幅度。",
        "steps": [
            "上杆到杆接近水平就停住，保持 2 秒",
            "确认肩转约 90°，再开始下杆",
            "体会『到位就停』的节奏",
            "每组 10 次，共 3 组",
        ],
        "duration_minutes": 10,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 90,
    },
    {
        "id": "drill_shoulder_turn",
        "name": "充分转肩练习",
        "target_issues": ["under_rotation"],
        "description": "强化上杆期充分转肩，提升力量传递。",
        "steps": [
            "双手交叉抱肩",
            "做上半身旋转，直到左肩触到下巴",
            "保持髋部角度基本不变",
            "20 次为一组，共 3 组",
        ],
        "duration_minutes": 10,
        "sets": 3,
        "difficulty": "easy",
        "sort_order": 100,
    },
    {
        "id": "drill_plane_board",
        "name": "挥杆平面板练习",
        "target_issues": ["flat_shoulder", "steep_shoulder"],
        "description": "借助倾斜板（或墙角）修正肩平面角。",
        "steps": [
            "在挥杆轨迹一侧斜放练习板 / 枕头",
            "上杆 / 下杆沿板面移动，既不过高也不过低",
            "感受杆头始终在肩平面上",
            "每组 10 次，共 3 组",
        ],
        "duration_minutes": 15,
        "sets": 3,
        "difficulty": "medium",
        "sort_order": 110,
    },
    {
        "id": "drill_alignment_stick",
        "name": "瞄准杆站位练习",
        "target_issues": ["open_stance"],
        "description": "用瞄准杆纠正站位与目标线的夹角。",
        "steps": [
            "在球位前方 2m 放置瞄准杆指向目标",
            "双脚、双膝、肩线都与瞄准杆平行",
            "检查自身影子 / 镜子里的角度",
            "每组 10 次 setup 练习，共 2 组",
        ],
        "duration_minutes": 5,
        "sets": 2,
        "difficulty": "easy",
        "sort_order": 120,
    },
    {
        "id": "drill_grip_checkpoint",
        "name": "握杆检查点练习",
        "target_issues": ["grip_weak"],
        "description": "按照标准握杆法复位左右手位置。",
        "steps": [
            "左手握杆，确认看到 2-3 颗指关节",
            "右手叠握，V 字指向右肩",
            "保持握杆压力 4/10",
            "练习 5 次，每次保持 10 秒",
        ],
        "duration_minutes": 5,
        "sets": 1,
        "difficulty": "easy",
        "sort_order": 130,
    },
]


def upgrade() -> None:
    # ==================== drills ====================
    drills = op.create_table(
        "drills",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=True),
        sa.Column("target_issues", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("steps", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("tips", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("sets", sa.Integer, nullable=True),
        sa.Column("difficulty", sa.String(10), nullable=False),
        sa.Column("illustration_url", sa.String(512), nullable=True),
        sa.Column("video_url", sa.String(512), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="chk_drill_difficulty",
        ),
    )
    op.create_index(
        "idx_drills_active",
        "drills",
        ["is_active"],
        postgresql_where=sa.text("is_active = TRUE"),
    )

    # seed 13 条 drill。JSONB 列直接传 Python list / dict，
    # SQLAlchemy 在 bind 阶段会走 asyncpg/psycopg 的 JSON codec 自动序列化。
    rows = [
        {
            "id": d["id"],
            "name": d["name"],
            "name_en": None,
            "target_issues": d["target_issues"],
            "description": d["description"],
            "steps": d["steps"],
            "tips": [],
            "duration_minutes": d["duration_minutes"],
            "sets": d["sets"],
            "difficulty": d["difficulty"],
            "illustration_url": None,
            "video_url": None,
            "sort_order": d["sort_order"],
            "is_active": True,
        }
        for d in DRILLS_SEED
    ]
    op.bulk_insert(drills, rows)

    # ==================== training_plans ====================
    op.create_table(
        "training_plans",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("week_end", sa.Date, nullable=False),
        sa.Column(
            "source_analysis_id",
            sa.String(32),
            sa.ForeignKey("swing_analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("total_tasks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_tasks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id", "week_start", name="uq_user_week"),
    )
    op.create_index("idx_plans_user_week", "training_plans", ["user_id", "week_start"])

    # ==================== training_tasks ====================
    op.create_table(
        "training_tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(32),
            sa.ForeignKey("training_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "drill_id",
            sa.String(32),
            sa.ForeignKey("drills.id"),
            nullable=False,
        ),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verification_analysis_id",
            sa.String(32),
            sa.ForeignKey("swing_analyses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')",
            name="chk_task_status",
        ),
    )
    op.create_index("idx_tasks_plan", "training_tasks", ["plan_id"])
    op.create_index("idx_tasks_user_date", "training_tasks", ["user_id", "scheduled_date"])
    op.create_index(
        "idx_tasks_user_status",
        "training_tasks",
        ["user_id", "status", "scheduled_date"],
    )

    # ==================== practice_logs ====================
    op.create_table(
        "practice_logs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            sa.String(32),
            sa.ForeignKey("training_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "drill_id",
            sa.String(32),
            sa.ForeignKey("drills.id"),
            nullable=False,
        ),
        sa.Column("practice_date", sa.Date, nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_practice_user_date", "practice_logs", ["user_id", "practice_date"])


def downgrade() -> None:
    op.drop_index("idx_practice_user_date", table_name="practice_logs")
    op.drop_table("practice_logs")

    op.drop_index("idx_tasks_user_status", table_name="training_tasks")
    op.drop_index("idx_tasks_user_date", table_name="training_tasks")
    op.drop_index("idx_tasks_plan", table_name="training_tasks")
    op.drop_table("training_tasks")

    op.drop_index("idx_plans_user_week", table_name="training_plans")
    op.drop_table("training_plans")

    op.drop_index("idx_drills_active", table_name="drills")
    op.drop_table("drills")
