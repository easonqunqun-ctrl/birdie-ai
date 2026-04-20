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
]

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
    await asyncio.sleep(random.uniform(2, 5))

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
