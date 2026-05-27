"""M9-01 user_profile_v2_service 单测（对齐 docs/23 §5.1 AC-2）.

覆盖
----
1. 新用户 upsert：建表插入 + consent 默认全 false → 字段被清空
2. 打开 consent + 写入字段 → 字段保留
3. 关闭 consent → 对应字段被强制清空（PIPL 删除权）
4. ``known_injuries`` 永不出现在 ``llm_prompt_safe_context``
5. ``add_club()`` 14 支硬上限触发 ``BadRequestError``
6. ``coach_visible_fields`` 白名单外字段被拒
7. ``project_for_coach()`` 在 coach_visible_consent=False 时仅返回 user_id
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.core.security import new_id
from app.models.user import User
from app.models.user_profile_v2 import MAX_CLUBS_PER_USER, UserProfileV2
from app.schemas.user_profile_v2 import (
    PrivacyPayload,
    UserClubCreate,
    UserProfileV2Update,
)
from app.services import user_profile_v2_service as svc


async def _make_user(db: AsyncSession) -> User:
    u = User(
        id=new_id("usr"),
        wechat_openid=f"o_{new_id('mock')}",
        nickname="t",
        invite_code=new_id("inv")[-6:].upper(),
    )
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_upsert_creates_profile_with_default_consent_off() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        profile = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                handicap_self=Decimal("12.3"),
                height_cm=176,
            ),
        )
        # 默认 consent 全 false → 字段被清空
        assert profile.handicap_self is None
        assert profile.height_cm is None
        assert profile.privacy_payload["handicap_consent"] is False


@pytest.mark.asyncio
async def test_upsert_with_consent_keeps_fields() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        profile = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                handicap_self=Decimal("8.5"),
                handicap_source="self",
                height_cm=180,
                weight_kg=75,
                handedness="right",
                privacy_payload=PrivacyPayload(
                    handicap_consent=True,
                    body_consent=True,
                ),
            ),
        )
        assert profile.handicap_self == Decimal("8.5")
        assert profile.height_cm == 180
        assert profile.weight_kg == 75
        assert profile.handedness == "right"


@pytest.mark.asyncio
async def test_revoking_consent_clears_fields() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                handicap_self=Decimal("7.0"),
                privacy_payload=PrivacyPayload(handicap_consent=True),
            ),
        )
        # 再次 patch：关闭 consent
        profile2 = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                privacy_payload=PrivacyPayload(handicap_consent=False),
            ),
        )
        assert profile2.handicap_self is None
        assert profile2.handicap_official is None
        assert profile2.handicap_source is None


@pytest.mark.asyncio
async def test_llm_context_never_leaks_injuries() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        profile = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                known_injuries=["lower_back"],
                handicap_self=Decimal("18.0"),
                privacy_payload=PrivacyPayload(
                    injury_consent=True,
                    handicap_consent=True,
                ),
            ),
        )
        ctx = svc.llm_prompt_safe_context(profile)
        # 即使 injury_consent=True，也禁止透传给 LLM
        assert "known_injuries" not in ctx
        assert "height_cm" not in ctx
        assert "weight_kg" not in ctx
        # 差点可以放行
        assert ctx["handicap_self"] == 18.0


@pytest.mark.asyncio
async def test_add_club_enforces_14_max() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        for i in range(MAX_CLUBS_PER_USER):
            await svc.add_club(
                db,
                user_id=u.id,
                payload=UserClubCreate(
                    club_type="iron",
                    nickname=f"club_{i}",
                    sort_order=i,
                ),
            )
        with pytest.raises(BadRequestError) as exc_info:
            await svc.add_club(
                db,
                user_id=u.id,
                payload=UserClubCreate(club_type="putter", nickname="overflow"),
            )
        assert "14" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_coach_visible_fields_whitelist() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        with pytest.raises(BadRequestError):
            await svc.upsert_profile(
                db,
                user_id=u.id,
                payload=UserProfileV2Update(
                    coach_visible_fields=["nickname", "phone_number"],  # 不在白名单
                ),
            )


@pytest.mark.asyncio
async def test_project_for_coach_requires_consent() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        profile = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                handicap_self=Decimal("10.0"),
                privacy_payload=PrivacyPayload(handicap_consent=True),
                coach_visible_fields=["handicap_self"],
            ),
        )
        # 没开教练总开关 → 教练视图除了 user_id 啥也看不到
        coach_view = svc.project_for_coach(profile)
        assert coach_view == {"user_id": u.id}

        # 开了教练总开关 → 按白名单字段曝光
        profile = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                privacy_payload=PrivacyPayload(
                    handicap_consent=True,
                    coach_visible_consent=True,
                ),
                coach_visible_fields=["handicap_self"],
            ),
        )
        coach_view = svc.project_for_coach(profile)
        assert coach_view["user_id"] == u.id
        assert coach_view["handicap_self"] == Decimal("10.0")
        # 未在 visible_fields 的字段不出现
        assert "height_cm" not in coach_view


@pytest.mark.asyncio
async def test_upsert_rejects_handicap_out_of_range() -> None:
    """Pydantic 层 ge=-10/le=54 拒绝异常差点（兜底 + DB CHECK 双层）。"""

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UserProfileV2Update(handicap_self=Decimal("99"))


@pytest.mark.asyncio
async def test_list_clubs_sorted_by_sort_order() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        await svc.add_club(
            db,
            user_id=u.id,
            payload=UserClubCreate(club_type="iron", nickname="A", sort_order=2),
        )
        await svc.add_club(
            db,
            user_id=u.id,
            payload=UserClubCreate(club_type="wedge", nickname="B", sort_order=0),
        )
        await svc.add_club(
            db,
            user_id=u.id,
            payload=UserClubCreate(club_type="putter", nickname="C", sort_order=1),
        )
        clubs = await svc.list_clubs(db, u.id)
        assert [c.nickname for c in clubs] == ["B", "C", "A"]


@pytest.mark.asyncio
async def test_update_coach_consent_open_with_fields() -> None:
    """M9-06：visible=True + fields → consent 打开 + 字段落库 + 白名单校验通过。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        profile = await svc.update_coach_consent(
            db,
            user_id=u.id,
            visible=True,
            fields=["handicap_self", "handedness", "handicap_self"],  # 故意含重复
        )
        assert profile.privacy_payload["coach_visible_consent"] is True
        # 保位去重生效
        assert list(profile.coach_visible_fields) == ["handicap_self", "handedness"]


@pytest.mark.asyncio
async def test_update_coach_consent_close_clears_fields() -> None:
    """M9-06：visible=False → 服务器无视客户端 fields，强制清空。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        # 先开
        await svc.update_coach_consent(
            db, user_id=u.id, visible=True, fields=["handicap_self"]
        )
        # 再关，故意传非空 fields → 服务器清空
        profile = await svc.update_coach_consent(
            db, user_id=u.id, visible=False, fields=["handicap_self", "handedness"]
        )
        assert profile.privacy_payload["coach_visible_consent"] is False
        assert list(profile.coach_visible_fields) == []


@pytest.mark.asyncio
async def test_update_coach_consent_open_without_fields_rejected() -> None:
    """M9-06：visible=True + 空 fields → 40022（中间态被拦截）。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        with pytest.raises(BadRequestError) as exc_info:
            await svc.update_coach_consent(
                db, user_id=u.id, visible=True, fields=[]
            )
        assert exc_info.value.code == 40022


@pytest.mark.asyncio
async def test_update_coach_consent_rejects_non_whitelisted_field() -> None:
    """M9-06：fields 中含白名单外字段 → 复用 _validate_coach_visible_fields → 40001。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        with pytest.raises(BadRequestError) as exc_info:
            await svc.update_coach_consent(
                db, user_id=u.id, visible=True, fields=["nickname", "phone_number"]
            )
        assert exc_info.value.code == 40001


@pytest.mark.asyncio
async def test_coach_consent_view_default_for_new_user() -> None:
    """M9-06：老用户没填过 profile → view 返回默认关闭 + 完整白名单。"""

    view = svc.coach_consent_view(None)
    assert view["visible"] is False
    assert view["fields"] == []
    # 白名单内容稳定（一旦变更必须同步 UI + 文档）
    assert "handicap_self" in view["allowed_fields"]
    assert "favorite_course_ids" in view["allowed_fields"]
    # 必须排序，避免每次请求顺序不稳定
    assert view["allowed_fields"] == sorted(view["allowed_fields"])


@pytest.mark.asyncio
async def test_update_coach_consent_preserves_other_consent_keys() -> None:
    """M9-06 回归：只动 coach_visible_consent，不应影响其他 4 个 consent 位。

    场景：先打开 handicap_consent + body_consent，再独立操作 coach 开关，
    其他 consent 必须保持原值（之前 #103 出过 PATCH 覆盖型 bug）。
    """

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        # 1) 通用 PATCH 打开 handicap + body
        await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                handicap_self=Decimal("12"),
                height_cm=180,
                privacy_payload=PrivacyPayload(
                    handicap_consent=True, body_consent=True
                ),
            ),
        )
        # 2) 独立打开 coach consent
        profile = await svc.update_coach_consent(
            db, user_id=u.id, visible=True, fields=["handedness"]
        )
        assert profile.privacy_payload["handicap_consent"] is True
        assert profile.privacy_payload["body_consent"] is True
        assert profile.privacy_payload["coach_visible_consent"] is True


@pytest.mark.asyncio
async def test_active_club_types_helper() -> None:
    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        c1 = await svc.add_club(
            db, user_id=u.id, payload=UserClubCreate(club_type="iron", is_active=True)
        )
        c2 = await svc.add_club(
            db, user_id=u.id, payload=UserClubCreate(club_type="wedge", is_active=False)
        )
        c3 = await svc.add_club(
            db, user_id=u.id, payload=UserClubCreate(club_type="driver", is_active=True)
        )
        assert svc.active_club_types([c1, c2, c3]) == ["driver", "iron"]
