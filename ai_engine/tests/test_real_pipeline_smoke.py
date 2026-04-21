"""W6-T5：真实 pipeline 顶层 smoke 测试。

目标：CI 护栏——保证 `run_real_analysis` 整个流水线（preprocess → pose → ...）
能从头跑到尾，输入 bouncing_box.mp4 → 返回 status=failed, error_code=50103。

为什么 smoke 要走失败路径而不是成功路径？
- 成功路径需要一段真正拍的挥杆视频（≥ 2s 完整 6 阶段），CI 里很难稳定持有
- 失败路径用合成 bouncing_box.mp4（3s，版权干净）即可复现；
  只要 preprocess / pose 能完整跑一趟而没崩 = pipeline 整体是活的

如果哪天这个测试红了，说明：
- preprocess 解码 / 质量检测 / ffmpeg 链路出了问题，或者
- MediaPipe 模型加载挂了（兜底抛 PoseModelError=50105，不是 50103），或者
- errors.PipelineError 的 except 链断了
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.main import analyze
from app.schemas import AnalyzeRequest
from tests.conftest import SYNTHETIC_DIR

# 真实 pipeline 依赖 mediapipe + cv2 + ffmpeg；任一缺失就 skip
_mediapipe = pytest.importorskip("mediapipe", reason="mediapipe 未安装，真实 pipeline smoke 跳过")
_cv2 = pytest.importorskip("cv2", reason="cv2 未安装，真实 pipeline smoke 跳过")

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg 未安装",
)


def _bouncing_box() -> Path | None:
    p = SYNTHETIC_DIR / "bouncing_box.mp4"
    return p if p.exists() else None


@needs_ffmpeg
@pytest.mark.asyncio
async def test_real_pipeline_smoke_bouncing_box_no_person(monkeypatch: pytest.MonkeyPatch):
    """顶层 smoke：/analyze 跑 bouncing_box → status=failed, error_code=50103。

    走 `app.main:analyze()` 入口（含 PipelineError → AnalyzeResult 的 except 包装），
    等价于一次完整的 POST /analyze，但不需要起 uvicorn。
    """
    video = _bouncing_box()
    if video is None:
        pytest.skip("bouncing_box.mp4 fixture 缺失，请先 make ai-engine-synth-fixtures")

    # 强制走真实管道（以防测试环境继承了 AI_ENGINE_MOCK_MODE=true）
    from app.config import settings

    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", False)

    result = await analyze(
        AnalyzeRequest(
            analysis_id="smoke-no-person",
            user_id="smoke-u",
            video_url=str(video),
            duration_ms=3000,
            membership_status="free",
            camera_angle="face_on",
            club_type="iron_7",
        )
    )

    assert result.status == "failed"
    # bouncing_box = 彩色弹跳方块，画质 OK 但无人；pose 阶段抛 NoPersonError=50103
    assert result.error_code == 50103
    assert result.error_message  # 有用户文案
    # 失败路径三类产物都不该落出
    assert result.skeleton_video_url is None or "placeholder" in (result.skeleton_video_url or "")
    assert result.overall_score is None
    assert result.issues == []
