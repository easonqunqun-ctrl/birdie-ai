"""M12-07 pro_pgc_service 单测."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.exceptions import AIChatServiceError
from app.integrations.llm import FakeLLMClient
from app.models.analysis import SwingAnalysis
from app.models.pro_library import ProClipAnnotation, ProPlayer, ProSwingClip
from app.schemas.pro_library import ProPlayerCreate, ProSwingClipCreate
from app.services import pro_library_service as pro_svc
from app.services import pro_pgc_service as pgc_svc


def test_build_pgc_llm_messages_includes_annotation_and_analysis() -> None:
    clip = ProSwingClip(
        id="psc_x",
        pro_player_id="pp_x",
        club_type="iron_7",
        camera_angle="face_on",
        video_url="https://x/v.mp4",
        overall_score=92,
        engine_version="v1",
        features_snapshot={"tempo_ratio": 3.1},
        license_status="public_clip",
        source_credit="demo",
        source_url="https://example.com",
        is_published=True,
    )
    player = ProPlayer(
        id="pp_x",
        name="Demo",
        handedness="right",
        license_status="public_clip",
        is_active=True,
        sort_order=0,
    )
    ann = ProClipAnnotation(
        id="pca_x",
        clip_id="psc_x",
        annotation_type="text",
        content="击球稳定",
        time_marker_ms=1000,
        is_visible=True,
    )
    analysis = SwingAnalysis(
        id="ana_x",
        user_id="usr_x",
        status="completed",
        camera_angle="face_on",
        club_type="iron_7",
        video_url="https://x/u.mp4",
        overall_score=80,
        phase_scores={"setup": {"score": 78}},
    )
    messages = pgc_svc.build_pgc_llm_messages(
        clip=clip,
        player=player,
        annotations=[ann],
        analysis=analysis,
    )
    assert messages[0]["role"] == "system"
    user_content = messages[1]["content"]
    assert "Demo" in user_content
    assert "击球稳定" in user_content
    assert "用户报告摘要" in user_content


@pytest.mark.asyncio
async def test_generate_pgc_insight_uses_fake_llm() -> None:
    async with AsyncSessionLocal() as db:
        await pro_svc.seed_initial_pros(db)
        await pgc_svc.seed_initial_pgc_annotations(db)
        clip = (
            await db.execute(
                select(ProSwingClip).where(ProSwingClip.is_published.is_(True))
            )
        ).scalar_one()

        fake = FakeLLMClient()
        fake.set_reply("这是 AI 对比解读示例。")
        text = await pgc_svc.generate_pgc_insight(
            db,
            clip_id=clip.id,
            user_id="usr_test",
            analysis_id=None,
            llm_client=fake,
        )
        assert "AI 对比解读" in text
        assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_generate_pgc_insight_llm_error_raises() -> None:
    async with AsyncSessionLocal() as db:
        player = await pro_svc.create_player(
            db, ProPlayerCreate(name="P", handedness="right")
        )
        clip = await pro_svc.add_clip(
            db,
            ProSwingClipCreate(
                pro_player_id=player.id,
                club_type="driver",
                camera_angle="face_on",
                video_url="https://example.com/x.mp4",
                license_status="public_clip",
                source_credit="demo",
                source_url="https://example.com",
                is_published=True,
            ),
        )
        await db.commit()
        fake = FakeLLMClient()
        fake.set_mode("error")
        with pytest.raises(AIChatServiceError) as exc:
            await pgc_svc.generate_pgc_insight(
                db,
                clip_id=clip.id,
                user_id="usr_x",
                analysis_id=None,
                llm_client=fake,
            )
        assert exc.value.code == 50106
