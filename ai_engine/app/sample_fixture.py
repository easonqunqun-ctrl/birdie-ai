"""示例视频分析结果（MVP §3.6 / §4.1 "用示例视频先体验"）.

设计目标
--------
1. **固定**：每次返回完全相同的数据，方便运营拿"标杆样本"来跑演示 / 截图。
2. **真实感**：分数、弱项、诊断、训练建议要像真实用户的场景，不能太"完美"
   （MVP §4.1 产品语气："示例视频的分数 80 上下，有 1-2 个中高严重度问题"）。
3. **零副作用**：纯静态函数，不走 mock_pipeline 的 random / asyncio.sleep；
   调用方拿到就能立刻返回给用户，TTFB 控制在 ~100ms 内。

与 mock_pipeline 的区别
----------------------
| 项目          | mock_pipeline          | sample_fixture              |
|---------------|------------------------|-----------------------------|
| 随机性        | ✅（分数 / 问题）      | ❌（全固定）                |
| 延时          | 2~5 秒                 | 无                          |
| 幂等          | 否（每次不同）         | 是（可反复调用）            |
| 用于          | 真正的分析任务入口     | /analyses/sample 免登体验   |

示例视频本身（mp4）不在此处托管；MVP 里先复用"固定一条 MinIO 对象"或 CDN 的
已有公开 URL。`SAMPLE_VIDEO_URL` 留一个可覆盖的环境变量入口，发布时再替换成
真正运营上传的素材。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from app.schemas import (
    AnalyzeResult,
    IssueItem,
    PhaseScore,
    PhaseTimestamps,
    RecommendationItem,
)

# 固定的示例 id —— 前端会检测这个字符串，走免登接口
SAMPLE_ANALYSIS_ID = "sample"

# 运营可通过环境变量覆盖素材 URL（例如换成真正的 CDN 地址）
SAMPLE_VIDEO_URL = os.environ.get(
    "SAMPLE_VIDEO_URL",
    "https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo.mp4",
)
SAMPLE_THUMBNAIL_URL = os.environ.get(
    "SAMPLE_THUMBNAIL_URL",
    "https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo_thumb.jpg",
)

# 固定创建时间 —— 用"示例"场景不需要展示真实时间，选一个稳定的日期便于截图
SAMPLE_CREATED_AT = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


def build_sample_analyze_result() -> AnalyzeResult:
    """生成一份固定的"示例挥杆报告"（AnalyzeResult 同 mock_pipeline 返回类型）.

    分数设计：79 分（"good" 档），downswing 为最弱项（72），其余 75-85 区间。
    问题诊断：2 条，high + medium 各一；对应"抛杆" + "提前伸展"。
    训练建议：2 条，精准对应问题。
    """
    phase_scores_raw: dict[str, tuple[int, str]] = {
        "setup": (85, "站位准备"),
        "backswing": (78, "上杆轨迹"),
        "top": (80, "顶点位置"),
        "downswing": (72, "下杆转换"),  # 弱项
        "impact": (78, "击球触球"),
        "follow_through": (82, "收杆平衡"),
    }
    weakest = min(phase_scores_raw, key=lambda k: phase_scores_raw[k][0])
    phase_scores = {
        k: PhaseScore(score=score, label=label, is_weakest=(k == weakest))
        for k, (score, label) in phase_scores_raw.items()
    }

    # 加权综合分（与 mock_pipeline 权重一致）
    weights = {
        "setup": 0.15,
        "backswing": 0.20,
        "top": 0.15,
        "downswing": 0.25,
        "impact": 0.15,
        "follow_through": 0.10,
    }
    overall = round(sum(phase_scores_raw[k][0] * weights[k] for k in weights))

    phase_timestamps = PhaseTimestamps(
        setup={"start": 0.0, "end": 0.8},
        backswing={"start": 0.8, "end": 1.5},
        top={"start": 1.5, "end": 1.7},
        downswing={"start": 1.7, "end": 2.0},
        impact={"start": 2.0, "end": 2.1},
        follow_through={"start": 2.1, "end": 2.8},
    )

    issues = [
        IssueItem(
            type="casting",
            name="抛杆（Casting）",
            severity="high",
            description=(
                "你的手腕在下杆初期（约 1.8s）就开始释放，导致击球时杆面打开，"
                "容易产生右曲球。这是目前最需要改善的环节。"
            ),
            key_frame_timestamp=1.8,
        ),
        IssueItem(
            type="early_extension",
            name="提前伸展（Early Extension）",
            severity="medium",
            description=(
                "下杆时髋部过早向球方向移动（约 1.9s），破坏了脊柱角度，"
                "导致击球距离损失约 8-12 码。"
            ),
            key_frame_timestamp=1.9,
        ),
    ]

    recommendations = [
        RecommendationItem(
            drill_id="drill_towel_arm",
            name="毛巾夹臂练习",
            target_issue="casting",
            description="修复下杆时过早释放手腕",
            duration_minutes=15,
            sets=3,
            steps=[
                "取一条小毛巾，折叠后夹在双臂之间（肘关节内侧）",
                "做半挥杆练习，保持毛巾不掉落",
                "感受双臂与身体的连接感",
                "逐渐加大挥杆幅度到全挥",
                "每组 10 次挥杆，共 3 组，组间休息 30 秒",
            ],
        ),
        RecommendationItem(
            drill_id="drill_hip_rotation",
            name="髋部旋转练习",
            target_issue="early_extension",
            description="纠正侧移与提前伸展，建立旋转感",
            duration_minutes=15,
            sets=3,
            steps=[
                "双脚与肩同宽，将球杆横放在髋部前",
                "保持上身静止，缓慢左右旋转髋部",
                "感受髋部以脊柱为轴的旋转",
                "每次旋转幅度从小到大",
                "30 次为一组，共 3 组",
            ],
        ),
    ]

    return AnalyzeResult(
        analysis_id=SAMPLE_ANALYSIS_ID,
        status="completed",
        overall_score=overall,
        phase_scores=phase_scores,
        phase_timestamps=phase_timestamps,
        issues=issues,
        recommendations=recommendations,
        skeleton_video_url=SAMPLE_VIDEO_URL,  # mock 期和原视频同源
        thumbnail_url=SAMPLE_THUMBNAIL_URL,
        duration_ms=0,  # 示例结果是查表的，"分析耗时"对用户无意义
        quality_warnings=["low_light"],
    )


__all__ = [
    "SAMPLE_ANALYSIS_ID",
    "SAMPLE_CREATED_AT",
    "SAMPLE_THUMBNAIL_URL",
    "SAMPLE_VIDEO_URL",
    "build_sample_analyze_result",
]
