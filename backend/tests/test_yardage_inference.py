"""M10-03 yardage inference unit tests."""

from __future__ import annotations

import pytest

from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.user import User
from app.services.yardage_inference import MIN_INFERENCE_SAMPLES, infer_yardage_for_club


@pytest.mark.asyncio
async def test_infer_yardage_requires_min_samples():
    from app.core.database import AsyncSessionLocal

    user_id = new_id("usr")
    async with AsyncSessionLocal() as db:
        db.add(
            User(
                id=user_id,
                wechat_openid=f"o_y_{user_id}",
                nickname="y",
                invite_code="YARD01",
            )
        )
        for i in range(MIN_INFERENCE_SAMPLES - 1):
            db.add(
                SwingAnalysis(
                    id=new_id("ana"),
                    user_id=user_id,
                    video_url="http://x/v.mp4",
                    camera_angle="face_on",
                    club_type="iron_7",
                    status="completed",
                    target_yardage=140 + i,
                )
            )
        await db.commit()

    async with AsyncSessionLocal() as db:
        assert await infer_yardage_for_club(db, user_id=user_id, club_type="iron_7") is None

    async with AsyncSessionLocal() as db:
        db.add(
            SwingAnalysis(
                id=new_id("ana"),
                user_id=user_id,
                video_url="http://x/v.mp4",
                camera_angle="face_on",
                club_type="iron_7",
                status="completed",
                target_yardage=150,
            )
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        result = await infer_yardage_for_club(db, user_id=user_id, club_type="iron_7")
        assert result is not None
        assert result.sample_count == MIN_INFERENCE_SAMPLES
        assert 140 <= result.avg <= 150
