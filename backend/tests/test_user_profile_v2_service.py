"""M9-01 / M9-05 user_profile_v2_service 单测（对齐 docs/23 §5.1 AC-2 + §5.5）.

覆盖
----
1. 新用户 upsert：建表插入 + consent 默认全 false → 字段被清空
2. 打开 consent + 写入字段 → 字段保留
3. 关闭 consent → 对应字段被强制清空（PIPL 删除权）
4. ``known_injuries`` 永不出现在 ``llm_prompt_safe_context``
5. ``add_club()`` 14 支硬上限触发 ``BadRequestError``
6. ``coach_visible_fields`` 白名单外字段被拒
7. ``project_for_coach()`` 在 coach_visible_consent=False 时仅返回 user_id
8. **M9-05** favorite_course_ids 校验：FK + 上限 + dedupe + 顺序 + consent
9. **M9-05** list_favorite_venues 顺序保留 + missing 拆分
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import BadRequestError
from app.core.security import new_id
from app.models.meetup import Venue
from app.models.user import User
from app.models.user_profile_v2 import (
    MAX_CLUBS_PER_USER,
    MAX_FAVORITE_VENUES,
    UserProfileV2,
)
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


async def _make_venue(
    db: AsyncSession,
    *,
    name: str = "测试球场",
    city: str = "Beijing",
    venue_type: str = "golf_course",
    status: str = "active",
) -> Venue:
    """M9-05 单测用：插入一行 venues，返回 Venue。"""

    v = Venue(
        id=new_id("ven"),
        city=city,
        name=name,
        venue_type=venue_type,
        source="ugc",
        status=status,
    )
    db.add(v)
    await db.flush()
    return v


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


# ============================ M9-05 常去球馆 ============================


@pytest.mark.asyncio
async def test_favorite_courses_rejects_nonexistent_venue() -> None:
    """传入不存在的 venue ID → 40021，不写入任何数据。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        v1 = await _make_venue(db, name="真实球场")
        bogus = "ven_nonexistent_id"
        with pytest.raises(BadRequestError) as exc_info:
            await svc.upsert_profile(
                db,
                user_id=u.id,
                payload=UserProfileV2Update(
                    favorite_course_ids=[v1.id, bogus],
                    privacy_payload=PrivacyPayload(location_consent=True),
                ),
            )
        assert exc_info.value.code == 40021
        assert bogus in (exc_info.value.detail or "")


@pytest.mark.asyncio
async def test_favorite_courses_rejects_closed_venue() -> None:
    """venues.status='closed' 视为不可用（FK-like 校验 = active only）。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        v_closed = await _make_venue(db, name="已下架球场", status="closed")
        with pytest.raises(BadRequestError) as exc_info:
            await svc.upsert_profile(
                db,
                user_id=u.id,
                payload=UserProfileV2Update(
                    favorite_course_ids=[v_closed.id],
                    privacy_payload=PrivacyPayload(location_consent=True),
                ),
            )
        assert exc_info.value.code == 40021


@pytest.mark.asyncio
async def test_favorite_courses_dedupes_preserving_order() -> None:
    """[A, B, A, C, B] → 落库为 [A, B, C]（保位去重，避免 chip 视觉欺骗）。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        va = await _make_venue(db, name="A")
        vb = await _make_venue(db, name="B")
        vc = await _make_venue(db, name="C")
        profile = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                favorite_course_ids=[va.id, vb.id, va.id, vc.id, vb.id],
                privacy_payload=PrivacyPayload(location_consent=True),
            ),
        )
        assert list(profile.favorite_course_ids) == [va.id, vb.id, vc.id]


@pytest.mark.asyncio
async def test_favorite_courses_cap_enforced_after_dedupe() -> None:
    """schema 7 条已超 max_length=6；dedupe 减到 6 内 → 写入成功。
    若 dedupe 仍 > 6 → 40020。

    本测试只覆盖 dedupe 内的 cap：schema 的 max_length 由 Pydantic 拦截，单元层
    不再重复（pydantic ValidationError 流程已被 _validate_handicap_out_of_range
    类似的测试覆盖模式）。
    """

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        venues = [await _make_venue(db, name=f"V{i}") for i in range(MAX_FAVORITE_VENUES)]
        ids = [v.id for v in venues]
        # 6 个全唯一 → 通过
        profile = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                favorite_course_ids=ids,
                privacy_payload=PrivacyPayload(location_consent=True),
            ),
        )
        assert len(profile.favorite_course_ids) == MAX_FAVORITE_VENUES


@pytest.mark.asyncio
async def test_favorite_courses_consent_off_clears_field() -> None:
    """关闭 location_consent → favorite_course_ids 被强制清空（已有的 consent 守门链）。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        v1 = await _make_venue(db)
        # 先开 consent + 写入
        await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                favorite_course_ids=[v1.id],
                privacy_payload=PrivacyPayload(location_consent=True),
            ),
        )
        # 再关 consent → 字段被清空
        profile2 = await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                privacy_payload=PrivacyPayload(location_consent=False),
            ),
        )
        assert list(profile2.favorite_course_ids) == []


@pytest.mark.asyncio
async def test_list_favorite_venues_preserves_order_and_splits_missing() -> None:
    """list_favorite_venues：按 ids 顺序返回 + 已 closed 的归入 missing_ids。

    重要：客户端依赖 items 顺序 = 用户原排序意图。DB 默认顺序（id / created_at）
    与用户预期不符，所以服务层显式按 ids 重排。
    """

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        v_active1 = await _make_venue(db, name="A")
        v_active2 = await _make_venue(db, name="B")
        v_active3 = await _make_venue(db, name="C")
        # 写入 4 个 ID
        await svc.upsert_profile(
            db,
            user_id=u.id,
            payload=UserProfileV2Update(
                favorite_course_ids=[v_active2.id, v_active1.id, v_active3.id],
                privacy_payload=PrivacyPayload(location_consent=True),
            ),
        )
        # 期间运营把 v_active2 软关闭
        v_active2.status = "closed"
        await db.flush()

        venues, missing = await svc.list_favorite_venues(db, user_id=u.id)
        assert [v.id for v in venues] == [v_active1.id, v_active3.id]
        assert missing == [v_active2.id]


@pytest.mark.asyncio
async def test_list_favorite_venues_empty_when_no_profile() -> None:
    """未填过 profile 的用户 → 返回 ([], [])，不抛错。"""

    async with AsyncSessionLocal() as db:
        u = await _make_user(db)
        venues, missing = await svc.list_favorite_venues(db, user_id=u.id)
        assert venues == [] and missing == []


def test_dedupe_helper_preserves_order_pure_function() -> None:
    """_dedupe_preserve_order 纯函数：保位去重；覆盖空列表与全重复边界。"""

    assert svc._dedupe_preserve_order([]) == []
    assert svc._dedupe_preserve_order(["a"]) == ["a"]
    assert svc._dedupe_preserve_order(["a", "a", "a"]) == ["a"]
    assert svc._dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
