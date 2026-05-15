"""Mock 分析流水线：返回符合 docs/02-API接口设计文档.md 报告结构的假数据.

W1-W5 阶段使用，让前后端链路先跑通；W6 替换为 real_pipeline.py。
"""

import asyncio
import random

from app.schemas import (
    AnalyzeRequest,
    AnalyzeResult,
    IssueItem,
    PhaseScore,
    PhaseTimestamps,
    RecommendationItem,
)

# Top5 常见错误模板
ISSUE_TEMPLATES: list[dict] = [
    {
        "type": "casting",
        "name": "抛杆（Casting）",
        "severity": "high",
        "description": "你的手腕在下杆初期就开始释放，导致击球时杆面打开，容易产生右曲球。这是目前最需要改善的环节。",
        "key_frame_timestamp": 1.8,
    },
    {
        "type": "over_the_top",
        "name": "由外到内下杆（Over-the-Top）",
        "severity": "high",
        "description": "下杆时杆头从身体外侧切入击球区，造成出杆路径偏左，容易拉左或切右。",
        "key_frame_timestamp": 1.7,
    },
    {
        "type": "early_extension",
        "name": "提前伸展（Early Extension）",
        "severity": "medium",
        "description": "下杆时髋部过早向球方向移动，破坏了脊柱角度，导致击球距离损失。",
        "key_frame_timestamp": 1.9,
    },
    {
        "type": "sway_slide",
        "name": "侧移/滑移（Sway/Slide）",
        "severity": "medium",
        "description": "上杆时身体重心明显向右侧偏移，下杆回正困难，影响一致性。",
        "key_frame_timestamp": 1.0,
    },
    {
        "type": "loss_of_posture",
        "name": "失去身体姿势（Loss of Posture）",
        "severity": "low",
        "description": "整个挥杆过程中头部高度变化超过 10cm，影响击球点的稳定。",
        "key_frame_timestamp": 1.5,
    },
]

# 13 个 drill：覆盖 docs/14 附录 A 映射表里全部 issue。drill_id 与
# `client/src/constants/drillLibrary.ts` 保持同步；增删时两边必须一起改。
DRILL_TEMPLATES: list[dict] = [
    {
        "drill_id": "drill_towel_arm",
        "name": "毛巾夹臂练习",
        "target_issue": "casting",
        "description": "修复下杆时过早释放手腕",
        "duration_minutes": 15,
        "sets": 3,
        "steps": [
            "取一条小毛巾，折叠后夹在双臂之间（肘关节内侧）",
            "做半挥杆练习，保持毛巾不掉落",
            "感受双臂与身体的连接感",
            "逐渐加大挥杆幅度",
            "每组做 10 次挥杆，共 3 组",
        ],
    },
    {
        "drill_id": "drill_impact_bag",
        "name": "击球包练习",
        "target_issue": "casting",
        "description": "强化击球位置的手腕前倾与身体连动",
        "duration_minutes": 10,
        "sets": 3,
        "steps": [
            "将击球包（或厚枕头）放在球位前方",
            "用半挥杆慢速击打，手腕保持前倾、杆头贴近身体",
            "记录手腕第一次『解锁』的感觉",
            "10 次为一组，共 3 组",
        ],
    },
    {
        "drill_id": "drill_half_swing",
        "name": "半挥杆节奏练习",
        "target_issue": "over_the_top",
        "description": "建立内侧下杆路径感",
        "duration_minutes": 20,
        "sets": 5,
        "steps": [
            "采用 7 号铁，站姿正常",
            "上杆只到水平位置（杆与地面平行）",
            "缓慢下杆，感受杆头从内侧进入击球区",
            "击球后跟进至同样高度",
            "每组 10 次，共 5 组",
        ],
    },
    {
        "drill_id": "drill_inside_path",
        "name": "内侧下杆路径练习",
        "target_issue": "over_the_top",
        "description": "用地上放杆引导下杆路径从内侧进入",
        "duration_minutes": 15,
        "sets": 3,
        "steps": [
            "在球位正后方 30cm 平行放一支练习杆",
            "上杆后刻意让下杆杆头沿练习杆内侧通过",
            "感受上半身被动、下半身主动的发力顺序",
            "每组 10 次，共 3 组",
        ],
    },
    {
        "drill_id": "drill_wall_butt",
        "name": "臀贴墙练习",
        "target_issue": "early_extension",
        "description": "保持臀部与墙接触，避免下杆髋部前移",
        "duration_minutes": 10,
        "sets": 3,
        "steps": [
            "背对墙站立，臀部轻贴墙面",
            "做上杆到下杆的镜像动作，臀部始终不离开墙",
            "感受脊柱角度在整个过程中保持不变",
            "10 次为一组，共 3 组",
        ],
    },
    {
        "drill_id": "drill_hip_rotation",
        "name": "髋部旋转练习",
        "target_issue": "sway_slide",
        "description": "纠正侧移，建立旋转感",
        "duration_minutes": 15,
        "sets": 3,
        "steps": [
            "双脚与肩同宽，将球杆横放在髋部前",
            "保持上身静止，缓慢左右旋转髋部",
            "感受髋部以脊柱为轴的旋转",
            "30 次为一组，共 3 组",
        ],
    },
    {
        "drill_id": "drill_mirror_spine",
        "name": "镜前脊柱角度练习",
        "target_issue": "loss_of_posture",
        "description": "借助镜子观察整挥中脊柱角是否恒定",
        "duration_minutes": 10,
        "sets": 2,
        "steps": [
            "面对落地镜做空挥",
            "观察从 setup 到 impact 脊柱前倾角的变化",
            "调整节奏直到差异 < 5°",
            "每组 10 次，共 2 组",
        ],
    },
    {
        "drill_id": "drill_weight_shift",
        "name": "重心转移节奏练习",
        "target_issue": "hanging_back",
        "description": "通过节奏口令建立『后-前-后』的重心流",
        "duration_minutes": 15,
        "sets": 3,
        "steps": [
            "站姿自然，口令『后、前、收』配合上杆/下杆/收杆",
            "收杆时感受 80% 重心在前脚",
            "对镜子检查完成姿势",
            "每组 10 次，共 3 组",
        ],
    },
    {
        "drill_id": "drill_backswing_stop",
        "name": "上杆截停练习",
        "target_issue": "over_rotation",
        "description": "防止过度转肩，控制上杆幅度",
        "duration_minutes": 10,
        "sets": 3,
        "steps": [
            "上杆到杆接近水平就停住，保持 2 秒",
            "确认肩转约 90°，再开始下杆",
            "体会『到位就停』的节奏",
            "每组 10 次，共 3 组",
        ],
    },
    {
        "drill_id": "drill_shoulder_turn",
        "name": "充分转肩练习",
        "target_issue": "under_rotation",
        "description": "强化上杆期充分转肩，提升力量传递",
        "duration_minutes": 10,
        "sets": 3,
        "steps": [
            "双手交叉抱肩",
            "做上半身旋转，直到左肩触到下巴",
            "保持髋部角度基本不变",
            "20 次为一组，共 3 组",
        ],
    },
    {
        "drill_id": "drill_plane_board",
        "name": "挥杆平面板练习",
        "target_issue": "flat_shoulder",
        "description": "借助倾斜板（或墙角）修正肩平面角",
        "duration_minutes": 15,
        "sets": 3,
        "steps": [
            "在挥杆轨迹一侧斜放练习板 / 枕头",
            "上杆 / 下杆沿板面移动，既不过高也不过低",
            "感受杆头始终在肩平面上",
            "每组 10 次，共 3 组",
        ],
    },
    {
        "drill_id": "drill_alignment_stick",
        "name": "瞄准杆站位练习",
        "target_issue": "open_stance",
        "description": "用瞄准杆纠正站位与目标线的夹角",
        "duration_minutes": 5,
        "sets": 2,
        "steps": [
            "在球位前方 2m 放置瞄准杆指向目标",
            "双脚、双膝、肩线都与瞄准杆平行",
            "检查自身影子 / 镜子里的角度",
            "每组 10 次 setup 练习，共 2 组",
        ],
    },
    {
        "drill_id": "drill_grip_checkpoint",
        "name": "握杆检查点练习",
        "target_issue": "grip_weak",
        "description": "按照标准握杆法复位左右手位置",
        "duration_minutes": 5,
        "sets": 1,
        "steps": [
            "左手握杆，确认看到 2-3 颗指关节",
            "右手叠握，V 字指向右肩",
            "保持握杆压力 4/10",
            "练习 5 次，每次保持 10 秒",
        ],
    },
]

# 运行时自检：drill_id 集合必须覆盖 pipeline.constants.ISSUE_DRILL_MAP 的全部目标
# （missing 则推荐环节 log warning 但不崩）
_DRILL_IDS = {d["drill_id"] for d in DRILL_TEMPLATES}
assert len(_DRILL_IDS) == len(DRILL_TEMPLATES), "DRILL_TEMPLATES 中 drill_id 有重复"

PHASE_LABELS = {
    "setup": "站位准备",
    "backswing": "上杆轨迹",
    "top": "顶点位置",
    "downswing": "下杆转换",
    "impact": "击球触球",
    "follow_through": "收杆平衡",
}


async def run_mock_analysis(req: AnalyzeRequest) -> AnalyzeResult:
    """模拟分析过程（短暂等待 + 返回随机但合理的结果）."""
    # 模拟分析耗时 2-5 秒
    await asyncio.sleep(random.uniform(1.2, 2.8))

    # 各阶段评分（中等水平用户）
    base_scores = {
        "setup": random.randint(75, 90),
        "backswing": random.randint(65, 85),
        "top": random.randint(70, 85),
        "downswing": random.randint(55, 75),  # 下杆通常是弱项
        "impact": random.randint(70, 85),
        "follow_through": random.randint(75, 90),
    }
    weakest = min(base_scores, key=base_scores.get)
    phase_scores = {
        k: PhaseScore(score=v, label=PHASE_LABELS[k], is_weakest=(k == weakest))
        for k, v in base_scores.items()
    }

    # 加权综合分
    weights = {
        "setup": 0.15, "backswing": 0.20, "top": 0.15,
        "downswing": 0.25, "impact": 0.15, "follow_through": 0.10,
    }
    overall = round(sum(base_scores[k] * weights[k] for k in base_scores))

    # 选 2 个问题（按弱项相关）
    issues_data = random.sample(ISSUE_TEMPLATES, k=2)
    issues = [IssueItem(**d) for d in issues_data]

    # 选 1-2 个建议
    recs_data = random.sample(DRILL_TEMPLATES, k=random.randint(1, 2))
    recommendations = [RecommendationItem(**d) for d in recs_data]

    # 模拟挥杆 6 阶段时间戳（总时长约 2.8s）
    phase_timestamps = PhaseTimestamps(
        setup={"start": 0.0, "end": 0.8},
        backswing={"start": 0.8, "end": 1.5},
        top={"start": 1.5, "end": 1.7},
        downswing={"start": 1.7, "end": 2.0},
        impact={"start": 2.0, "end": 2.1},
        follow_through={"start": 2.1, "end": 2.8},
    )

    return AnalyzeResult(
        analysis_id=req.analysis_id,
        status="completed",
        overall_score=overall,
        phase_scores=phase_scores,
        phase_timestamps=phase_timestamps,
        issues=issues,
        recommendations=recommendations,
        # 占位 URL，正式版替换为真实生成
        skeleton_video_url=req.video_url.replace(".mp4", "_skeleton.mp4"),
        thumbnail_url=req.video_url.replace(".mp4", "_thumb.jpg"),
        duration_ms=random.randint(2000, 5000),
    )
