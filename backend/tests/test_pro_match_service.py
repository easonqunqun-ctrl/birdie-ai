"""M12-04 pro_match_service 单测：匹配打分纯函数 + 集成写入."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.pro_library import ProSwingClip
from app.models.user import User
from app.services import pro_library_service as pro_svc
from app.services import pro_match_service as match_svc


def _clip_stub(
    *,
    overall_score: int = 90,
    camera_angle: str = "face_on",
    features_snapshot: dict | None = None,
) -> ProSwingClip:
    return ProSwingClip(
        id=new_id("psc"),
        pro_player_id="pp_stub",
        club_type="iron_7",
        camera_angle=camera_angle,
        video_url="https://minio.local/demo/x.mp4",
        overall_score=overall_score,
        engine_version="v1",
        features_snapshot=features_snapshot or {"shoulder_turn_deg": 88},
        license_status="public_clip",
        source_credit="test",
        source_url="https://example.com/meta",
        is_published=True,
    )


def test_score_clip_match_camera_angle_bonus() -> None:
    analysis = match_svc.AnalysisMatchInput(
        club_type="iron_7",
        camera_angle="face_on",
        overall_score=None,
        phase_scores=None,
    )
    matched_clip = _clip_stub(camera_angle="face_on", features_snapshot={})
    other_angle = _clip_stub(camera_angle="down_the_line", features_snapshot={})

    matched_score, matched_details = match_svc.score_clip_match(analysis, matched_clip)
    other_score, other_details = match_svc.score_clip_match(analysis, other_angle)

    assert matched_details["camera_angle_match"] is True
    assert other_details["camera_angle_match"] is False
    assert matched_details["components"] == {"fallback": 50.0}
    assert matched_score == pytest.approx(65.0, abs=0.01)
    assert other_score == pytest.approx(50.0, abs=0.01)


def test_phase_average_accepts_v2_dict_phase_scores() -> None:
    phase_scores = {
        "setup": {"label": "站位", "score": 80, "is_weakest": False},
        "impact": {"label": "击球", "score": 90, "is_weakest": False},
    }
    assert match_svc._phase_average(phase_scores) == pytest.approx(85.0)


def test_rank_clip_matches_orders_by_score_desc() -> None:
    analysis = match_svc.AnalysisMatchInput(
        club_type="iron_7",
        camera_angle="face_on",
        overall_score=85,
        phase_scores={"setup": 84},
    )
    from app.models.pro_library import ProPlayer

    player = ProPlayer(
        id="pp_a",
        name="A",
        handedness="right",
        license_status="public_clip",
        is_active=True,
        sort_order=0,
    )
    candidates = [
        (_clip_stub(overall_score=70), player),
        (_clip_stub(overall_score=92), player),
        (_clip_stub(overall_score=80), player),
    ]
    ranked = match_svc.rank_clip_matches(analysis, candidates, limit=2)
    assert len(ranked) == 2
    assert ranked[0].match_score >= ranked[1].match_score
    assert ranked[0].clip.overall_score == 92


async def _make_user(db: AsyncSession) -> User:
    user = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="match test",
        invite_code=new_id("inv")[-6:].upper(),
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_match_analysis_to_pro_clips_records_top1() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        await pro_svc.seed_initial_pros(db)
        analysis = SwingAnalysis(
            id=new_id("ana"),
            user_id=user.id,
            status="completed",
            stage="completed",
            stage_progress=100,
            camera_angle="face_on",
            club_type="iron_7",
            video_url="https://x/v.mp4",
            video_duration=8.0,
            overall_score=85,
            phase_scores={"setup": 84, "impact": 86},
            created_at=datetime.now(UTC),
            analyzed_at=datetime.now(UTC),
        )
        db.add(analysis)
        await db.commit()

        matches, history = await match_svc.match_analysis_to_pro_clips(
            db,
            user_id=user.id,
            analysis=analysis,
            limit=3,
            record=True,
        )
        await db.commit()

    assert matches
    assert history is not None
    assert history.analysis_id == analysis.id
    assert history.matched_clip_id == matches[0].clip.id


@pytest.mark.asyncio
async def test_match_analysis_rejects_sample() -> None:
    async with AsyncSessionLocal() as db:
        user = await _make_user(db)
        analysis = SwingAnalysis(
            id=new_id("ana"),
            user_id=user.id,
            status="completed",
            camera_angle="face_on",
            club_type="iron_7",
            video_url="https://x/v.mp4",
            overall_score=80,
            is_sample=True,
        )
        db.add(analysis)
        await db.commit()

        with pytest.raises(BadRequestError) as exc:
            await match_svc.match_analysis_to_pro_clips(
                db,
                user_id=user.id,
                analysis=analysis,
                record=False,
            )
        assert exc.value.code == 40093
