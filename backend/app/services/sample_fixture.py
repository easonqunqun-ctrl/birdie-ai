"""示例分析报告数据（/v1/analyses/sample 的数据源）.

设计背景
--------
`ai_engine/app/sample_fixture.py` 定义了 AI 侧的"标杆样本"生成器。但 `ai_engine` 是
独立服务（独立 Dockerfile + 独立 uv 环境），backend 无法直接 import 它的 Python 模块。

走 HTTP 调 ai_engine 只是为了拿一份静态数据，带来两个坏处：
  1. 多一个可能超时 / 503 的依赖点（和"示例体验要极快给出结果"矛盾）
  2. CI / 本地开发时需要先启 ai_engine，心智负担大

所以这里在 backend 端也维护一份示例数据。**两边内容必须保持一致**：
数值（分数 / 弱项 / 问题 / 建议）和 ai_engine 侧 sample_fixture 同源，改动时要双改。

不入库、不计配额
----------------
`/v1/analyses/sample` 直接返回 `AnalysisReportResponse`，不创建 `SwingAnalysis` 记录，
也不扣配额。`id` 固定为字符串 "sample"，前端 `report` 页识别此 id 就知道在看示例。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from app.schemas.analysis import (
    AnalysisReportResponse,
    IssueItem,
    PhaseScore,
    PhaseWindow,
    RecommendationItem,
    score_level,
)

SAMPLE_ANALYSIS_ID = "sample"

# 允许通过环境变量替换素材 URL（发布时换成真实运营上传的素材）
SAMPLE_VIDEO_URL = os.environ.get(
    "SAMPLE_VIDEO_URL",
    "https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo.mp4",
)
SAMPLE_THUMBNAIL_URL = os.environ.get(
    "SAMPLE_THUMBNAIL_URL",
    "https://xiaoniao-assets.oss-cn-hangzhou.aliyuncs.com/samples/swing_demo_thumb.jpg",
)

# 固定创建时间：截图稳定性 > 真实性
SAMPLE_CREATED_AT = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
SAMPLE_ANALYZED_AT = datetime(2026, 4, 1, 10, 0, 3, tzinfo=UTC)  # +3s

# 与 `ai_engine/app/sample_fixture.py::build_sample_analyze_result` 同源的分数矩阵
_PHASE_DATA: dict[str, tuple[int, str]] = {
    "setup": (85, "站位准备"),
    "backswing": (78, "上杆轨迹"),
    "top": (80, "顶点位置"),
    "downswing": (72, "下杆转换"),  # 最弱项
    "impact": (78, "击球触球"),
    "follow_through": (82, "收杆平衡"),
}

_PHASE_WEIGHTS = {
    "setup": 0.15,
    "backswing": 0.20,
    "top": 0.15,
    "downswing": 0.25,
    "impact": 0.15,
    "follow_through": 0.10,
}

_PHASE_WINDOWS = {
    "setup": PhaseWindow(start=0.0, end=0.8),
    "backswing": PhaseWindow(start=0.8, end=1.5),
    "top": PhaseWindow(start=1.5, end=1.7),
    "downswing": PhaseWindow(start=1.7, end=2.0),
    "impact": PhaseWindow(start=2.0, end=2.1),
    "follow_through": PhaseWindow(start=2.1, end=2.8),
}


def build_sample_report() -> AnalysisReportResponse:
    """构造固定的示例分析报告（纯静态，无副作用）."""
    weakest = min(_PHASE_DATA, key=lambda k: _PHASE_DATA[k][0])
    phase_scores = {
        k: PhaseScore(score=s, label=label, is_weakest=(k == weakest))
        for k, (s, label) in _PHASE_DATA.items()
    }
    overall = round(
        sum(_PHASE_DATA[k][0] * _PHASE_WEIGHTS[k] for k in _PHASE_DATA)
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
            key_frame_url=None,
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
            key_frame_url=None,
            key_frame_timestamp=1.9,
        ),
    ]

    recommendations = [
        RecommendationItem(drill_id="drill_towel_arm", target_issue="casting", sort_order=0),
        RecommendationItem(
            drill_id="drill_hip_rotation",
            target_issue="early_extension",
            sort_order=1,
        ),
    ]

    return AnalysisReportResponse(
        id=SAMPLE_ANALYSIS_ID,
        # 示例报告没有真正的 owner；用固定标识让日志/埋点能区分
        user_id="sample",
        status="completed",
        camera_angle="face_on",
        club_type="iron_7",
        video_url=SAMPLE_VIDEO_URL,
        video_duration=2.8,
        skeleton_video_url=SAMPLE_VIDEO_URL,  # mock 期两者同源
        skeleton_data_url=None,
        thumbnail_url=SAMPLE_THUMBNAIL_URL,
        overall_score=overall,
        score_change=None,  # 示例不展示"相对上次变化"
        score_level=score_level(overall),
        phase_scores=phase_scores,
        phase_timestamps=_PHASE_WINDOWS,
        issues=issues,
        recommendations=recommendations,
        share_card_url=None,
        analyzed_at=SAMPLE_ANALYZED_AT,
        created_at=SAMPLE_CREATED_AT,
    )


__all__ = [
    "SAMPLE_ANALYSIS_ID",
    "SAMPLE_CREATED_AT",
    "SAMPLE_THUMBNAIL_URL",
    "SAMPLE_VIDEO_URL",
    "build_sample_report",
]
