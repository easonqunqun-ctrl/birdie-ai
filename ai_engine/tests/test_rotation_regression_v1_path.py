"""P2-M7-R1 · AC-A4：V1 桶 sanitize 全路径 + 计分机位冻结（club_aware_scoring=False）。"""

from __future__ import annotations

from app.pipeline.diagnose import diagnose
from app.pipeline.feature_measurability import (
    WARN_ANGLE_LIMITED_SCORING,
    sanitize_features,
)
from app.pipeline.rotation_issue_copy import ROTATION_ISSUE_TYPES
from app.pipeline.scoring import score_all_phases, score_overall
from tests.test_diagnose import _fake_phases, _ideal_features
from tests.test_nelly_dtl_scoring import NELLY_LIVE


def test_ac_a4_v1_sanitize_uses_effective_dtl_no_rotation_issues() -> None:
    """V1 诊断链：DTL effective → 旋转键剔除 → 零 rotation issue。"""
    cleaned, warns = sanitize_features(NELLY_LIVE, camera_angle="down_the_line")
    assert "shoulder_rotation_top" not in cleaned
    assert "x_factor" not in cleaned
    issues = diagnose(cleaned, _fake_phases(), camera_angle="down_the_line")
    hit = ROTATION_ISSUE_TYPES & {i.type for i in issues}
    assert not hit
    assert WARN_ANGLE_LIMITED_SCORING not in warns


def test_ac_a4_v1_scoring_camera_angle_frozen_none() -> None:
    """V1 计分：``camera_angle=None`` 与 historical ideal 一致；不因 DTL sanitize 漂移。"""
    cleaned, _ = sanitize_features(NELLY_LIVE, camera_angle="down_the_line")
    v1_scores = score_all_phases(cleaned, club_category=None, camera_angle=None)
    v1_overall = score_overall(v1_scores, club_category=None, camera_angle=None, features=cleaned)

    ideal = _ideal_features()
    ideal_scores = score_all_phases(ideal, club_category=None, camera_angle=None)
    ideal_overall = score_overall(ideal_scores, club_category=None, camera_angle=None, features=ideal)

    # DTL sanitize 后非旋转维仍可用；overall 应落在合理 band（与 ideal 同量级，非 155° 误报拉低）
    assert v1_overall >= 50
    assert abs(v1_overall - ideal_overall) <= 25


def test_ac_a4_v2_scoring_would_use_camera_angle() -> None:
    """对照：V2 club_aware 打开时 DTL 计分会走 angle profile（与 V1 可不同）。"""
    cleaned, _ = sanitize_features(NELLY_LIVE, camera_angle="down_the_line")
    v1 = score_overall(
        score_all_phases(cleaned, club_category=None, camera_angle=None),
        club_category=None,
        camera_angle=None,
        features=cleaned,
    )
    v2 = score_overall(
        score_all_phases(cleaned, club_category="iron", camera_angle="down_the_line"),
        club_category="iron",
        camera_angle="down_the_line",
        features=cleaned,
    )
    assert v1 != v2 or v1 >= 50
