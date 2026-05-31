"""P2-M7-R1 · AC-A1 真视频回归（manifest 驱动；无 fixture 时 skip）。

将 ``fixtures/real/*.mp4`` 跑完整 ``analyze`` V1 路径，断言旋转类 issue 不伤害信任。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.main import analyze
from app.pipeline.rotation_issue_copy import ROTATION_ISSUE_TYPES
from app.schemas import AnalyzeRequest
from tests.conftest import REAL_DIR, resolve_manifest_fixture_video

_mediapipe = pytest.importorskip("mediapipe", reason="mediapipe 未安装")
_cv2 = pytest.importorskip("cv2", reason="cv2 未安装")

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg 未安装",
)

_MEDIUM_OR_HIGH = frozenset({"medium", "high"})
_MANIFEST = Path(__file__).parent / "fixtures" / "rotation_regression_manifest.json"


def _fixture_cases(pack_key: str) -> list[dict]:
    if not _MANIFEST.is_file():
        return []
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    pack = manifest.get("packs", {}).get(pack_key, {})
    return [c for c in pack.get("cases", []) if c.get("source") == "fixture"]


def _rotation_issues(result) -> list:
    return [i for i in (result.issues or []) if i.type in ROTATION_ISSUE_TYPES]


@needs_ffmpeg
@pytest.mark.asyncio
@pytest.mark.parametrize("case", _fixture_cases("R2_dtl_broadcast"), ids=lambda c: c["id"])
async def test_r2_dtl_fixture_no_rotation_issues(
    case: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-A1 · DTL fixture：零 rotation 类 severity≥medium issue。"""
    video = resolve_manifest_fixture_video(case, real_dir=REAL_DIR)
    if video is None:
        pytest.skip(
            f"缺少 fixture：{case.get('fixture_file')}（见 fixtures/download_samples.sh）",
        )

    from app.config import settings

    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", False)

    declared = case.get("declared_camera_angle") or case.get("camera_angle")
    result = await analyze(
        AnalyzeRequest(
            analysis_id=f"r2-dtl-{case['id']}",
            user_id="regression-u",
            video_url=str(video),
            duration_ms=5000,
            membership_status="free",
            camera_angle=declared,
            club_type="iron_7",
        )
    )

    assert result.status == "completed", (
        f"expected completed, got {result.status} code={result.error_code} msg={result.error_message}"
    )
    rotation = _rotation_issues(result)
    severe = [i for i in rotation if i.severity in _MEDIUM_OR_HIGH]
    assert not severe, f"rotation issues: {[(i.type, i.severity) for i in rotation]}"


@needs_ffmpeg
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    _fixture_cases("R2_face_on_clear_turn"),
    ids=lambda c: c["id"],
)
async def test_r2_face_on_fixture_no_severe_under_rotation(
    case: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-A1 · face-on 明显转肩：不得 high severity under_rotation。"""
    video = resolve_manifest_fixture_video(case, real_dir=REAL_DIR)
    if video is None:
        pytest.skip(f"缺少 fixture：{case.get('fixture_file')}")

    from app.config import settings

    monkeypatch.setattr(settings, "AI_ENGINE_MOCK_MODE", False)

    declared = case.get("declared_camera_angle") or case.get("camera_angle")
    result = await analyze(
        AnalyzeRequest(
            analysis_id=f"r2-face-{case['id']}",
            user_id="regression-u",
            video_url=str(video),
            duration_ms=5000,
            membership_status="free",
            camera_angle=declared,
            club_type="iron_7",
        )
    )

    assert result.status == "completed"
    under = [i for i in (result.issues or []) if i.type == "under_rotation"]
    assert not any(i.severity == "high" for i in under), under
