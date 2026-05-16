"""W7-T3：训练计划 / 打卡测试.

覆盖：
- 分析成功 → 自动生成当周训练计划（去重 / 任务数 <= MAX_TASKS_PER_ANALYSIS）
- 分析无 issue → 不生成 plan
- 打卡：任务 completed + practice_log 写入 + streak +1
- 同一天重复打卡另一任务 → streak 不再 +1
- 跨天打卡 → streak +1
- 断签后打卡 → streak 重置为 1
- 同一周第二次分析 → 增量追加新 drill（不重建）
- 他人 task 打卡 → 40301；已完成任务打卡 → 40014
- `/v1/drills` 返回 13 条 seed；`/me/practice-logs?month=...` 过滤正确
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import new_id
from app.models.analysis import SwingAnalysis
from app.models.training import PracticeLog
from app.models.user import User
from app.services import training_service


# ==================== 辅助：拿到当前登录用户 id ====================
async def _get_user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    me = (await client.get("/v1/users/me", headers=headers)).json()["data"]
    return me["id"]


# ==================== drills seed ====================
@pytest.mark.asyncio
async def test_drills_endpoint_returns_seeded_rows(
    client: AsyncClient, auth_headers: dict[str, str]
):
    resp = await client.get("/v1/drills", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    drills = resp.json()["data"]
    assert len(drills) == 13
    ids = {d["id"] for d in drills}
    assert "drill_towel_arm" in ids
    assert "drill_grip_checkpoint" in ids
    # 静态业务字段完整
    towel = next(d for d in drills if d["id"] == "drill_towel_arm")
    assert "casting" in towel["target_issues"]
    assert towel["duration_minutes"] == 15
    assert towel["difficulty"] == "easy"
    assert len(towel["steps"]) >= 3


# ==================== 当周无 plan 时 /current 返回 null ====================
@pytest.mark.asyncio
async def test_current_plan_none_when_no_analysis(
    client: AsyncClient, auth_headers: dict[str, str]
):
    resp = await client.get("/v1/users/me/training-plan/current", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] is None


# ==================== 分析完成 → 生成训练计划 ====================
@pytest.mark.asyncio
async def test_generate_plan_from_analysis_issues(
    client: AsyncClient, auth_headers: dict[str, str]
):
    user_id = await _get_user_id(client, auth_headers)

    async with AsyncSessionLocal() as db:
        # 先造一条 swing_analysis（仅为了 FK 合法；W7-T3 service 接收的是 issues list）
        analysis_id = new_id("swa")
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                video_url="s3://fake/video.mp4",
                video_file_size=1024,
                camera_angle="face_on",
                club_type="driver",
                status="completed",
            )
        )
        await db.commit()

        plan = await training_service.generate_or_update_weekly(
            db,
            user_id=user_id,
            analysis_id=analysis_id,
            issues=[
                {"type": "casting", "severity": "high"},
                {"type": "over_the_top", "severity": "medium"},
                {"type": "early_extension", "severity": "low"},
            ],
        )
        await db.commit()

    assert plan is not None
    assert plan.total_tasks == 3
    assert plan.completed_tasks == 0

    # API 查
    resp = await client.get("/v1/users/me/training-plan/current", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data is not None
    assert len(data["tasks"]) == 3
    drill_ids = {t["drill_id"] for t in data["tasks"]}
    assert len(drill_ids) == 3  # 去重成功


# ==================== 没有 issue → 不建 plan ====================
@pytest.mark.asyncio
async def test_no_plan_when_no_issues(
    client: AsyncClient, auth_headers: dict[str, str]
):
    user_id = await _get_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        analysis_id = new_id("swa")
        db.add(
            SwingAnalysis(
                id=analysis_id,
                user_id=user_id,
                video_url="s3://fake/v.mp4",
                video_file_size=1024,
                camera_angle="face_on",
                club_type="driver",
                status="completed",
            )
        )
        await db.commit()

        plan = await training_service.generate_or_update_weekly(
            db, user_id=user_id, analysis_id=analysis_id, issues=[]
        )
    assert plan is None


# ==================== 同一周第二次分析 → 增量追加 ====================
@pytest.mark.asyncio
async def test_second_analysis_in_same_week_appends_tasks(
    client: AsyncClient, auth_headers: dict[str, str]
):
    user_id = await _get_user_id(client, auth_headers)

    async with AsyncSessionLocal() as db:
        a1 = new_id("swa")
        a2 = new_id("swa")
        for aid in (a1, a2):
            db.add(
                SwingAnalysis(
                    id=aid, user_id=user_id, video_url="s3://x", video_file_size=1,
                    camera_angle="face_on", club_type="driver", status="completed",
                )
            )
        await db.commit()

        await training_service.generate_or_update_weekly(
            db, user_id=user_id, analysis_id=a1,
            issues=[{"type": "casting", "severity": "high"}],
        )
        await db.commit()
        plan2 = await training_service.generate_or_update_weekly(
            db, user_id=user_id, analysis_id=a2,
            issues=[
                {"type": "casting", "severity": "high"},  # 已存在，应去重
                {"type": "over_the_top", "severity": "medium"},  # 新增
            ],
        )
        await db.commit()

    assert plan2.total_tasks == 2
    # source_analysis_id 更新为最新 a2
    assert plan2.source_analysis_id == a2


# ==================== 打卡：streak 管理 ====================
@pytest.mark.asyncio
async def test_complete_task_writes_log_and_bumps_streak(
    client: AsyncClient, auth_headers: dict[str, str]
):
    user_id = await _get_user_id(client, auth_headers)

    async with AsyncSessionLocal() as db:
        a1 = new_id("swa")
        db.add(
            SwingAnalysis(
                id=a1, user_id=user_id, video_url="s3://x", video_file_size=1,
                camera_angle="face_on", club_type="driver", status="completed",
            )
        )
        await db.commit()
        await training_service.generate_or_update_weekly(
            db, user_id=user_id, analysis_id=a1,
            issues=[
                {"type": "casting", "severity": "high"},
                {"type": "over_the_top", "severity": "medium"},
            ],
        )
        await db.commit()

    # 拿到一个 task id
    plan_data = (
        await client.get("/v1/users/me/training-plan/current", headers=auth_headers)
    ).json()["data"]
    assert plan_data["completed_tasks"] == 0
    task_id_1 = plan_data["tasks"][0]["id"]
    task_id_2 = plan_data["tasks"][1]["id"]

    # 第一次打卡
    r1 = await client.post(
        f"/v1/training-plan/tasks/{task_id_1}/complete",
        headers=auth_headers,
        json={"duration_minutes": 15, "notes": "感觉不错"},
    )
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert d1["task"]["status"] == "completed"
    assert d1["current_streak_days"] == 1
    assert d1["plan_completed_tasks"] == 1

    # 同日再打另一个 task → streak 不涨
    r2 = await client.post(
        f"/v1/training-plan/tasks/{task_id_2}/complete",
        headers=auth_headers,
        json={},
    )
    assert r2.status_code == 200
    d2 = r2.json()["data"]
    assert d2["current_streak_days"] == 1  # 同日不叠
    assert d2["plan_completed_tasks"] == 2

    # 已完成任务不可重复打卡
    r3 = await client.post(
        f"/v1/training-plan/tasks/{task_id_1}/complete",
        headers=auth_headers,
        json={},
    )
    assert r3.status_code == 400
    assert r3.json()["code"] == 40014


# ==================== 跨天 / 断签 streak 逻辑 ====================
@pytest.mark.asyncio
async def test_streak_rolls_over_and_resets(
    client: AsyncClient, auth_headers: dict[str, str]
):
    user_id = await _get_user_id(client, auth_headers)
    today = training_service._china_today()

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        assert user is not None

        # 昨天打过 → 今天再打应 +1
        user.current_streak_days = 3
        user.last_practice_date = today - timedelta(days=1)
        user.max_streak_days = 3
        await db.commit()

        training_service._update_streak(user, today)
        assert user.current_streak_days == 4
        assert user.max_streak_days == 4

        # 再在同一天打一次 → 不变
        training_service._update_streak(user, today)
        assert user.current_streak_days == 4

        # 前天之前打过（断签） → 重置为 1
        user.current_streak_days = 10
        user.last_practice_date = today - timedelta(days=3)
        user.max_streak_days = 10
        training_service._update_streak(user, today)
        assert user.current_streak_days == 1
        assert user.max_streak_days == 10  # max 保留历史


# ==================== 他人 task 打卡 ====================
@pytest.mark.asyncio
async def test_cannot_complete_another_users_task(
    client: AsyncClient, auth_headers: dict[str, str], fresh_code: str
):
    # 用户 A 建计划
    user_a_id = await _get_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        aid = new_id("swa")
        db.add(
            SwingAnalysis(
                id=aid, user_id=user_a_id, video_url="s3://x", video_file_size=1,
                camera_angle="face_on", club_type="driver", status="completed",
            )
        )
        await db.commit()
        await training_service.generate_or_update_weekly(
            db, user_id=user_a_id, analysis_id=aid,
            issues=[{"type": "casting", "severity": "high"}],
        )
        await db.commit()

    plan_data = (
        await client.get("/v1/users/me/training-plan/current", headers=auth_headers)
    ).json()["data"]
    a_task_id = plan_data["tasks"][0]["id"]

    # 用户 B 登录
    from uuid import uuid4

    login_b = await client.post(
        "/v1/auth/wechat-login", json={"code": f"pytest_{uuid4().hex}"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['data']['token']}"}

    resp = await client.post(
        f"/v1/training-plan/tasks/{a_task_id}/complete",
        headers=headers_b,
        json={},
    )
    assert resp.status_code in (403, 409)  # ConflictError 返 409，或按业务 40301


# ==================== 月度练习日志查询 ====================
@pytest.mark.asyncio
async def test_practice_logs_by_month(
    client: AsyncClient, auth_headers: dict[str, str]
):
    user_id = await _get_user_id(client, auth_headers)
    today = training_service._china_today()

    async with AsyncSessionLocal() as db:
        # 直接写一条 practice_log（不走 task，模拟离线补录）
        db.add(
            PracticeLog(
                id=new_id("plog"),
                user_id=user_id,
                task_id=None,
                drill_id="drill_towel_arm",
                practice_date=today,
                duration_minutes=20,
                notes="独立练习",
            )
        )
        await db.commit()

    month = f"{today.year:04d}-{today.month:02d}"
    resp = await client.get(
        f"/v1/users/me/practice-logs?month={month}", headers=auth_headers
    )
    assert resp.status_code == 200
    logs = resp.json()["data"]
    assert any(
        lg["drill_id"] == "drill_towel_arm" and lg["duration_minutes"] == 20
        for lg in logs
    )

    # 不同月 → 空
    other = "2020-01"
    resp2 = await client.get(
        f"/v1/users/me/practice-logs?month={other}", headers=auth_headers
    )
    assert resp2.json()["data"] == []

    # 格式错误
    bad = await client.get(
        "/v1/users/me/practice-logs?month=2020/01", headers=auth_headers
    )
    assert bad.status_code == 400


# ====================================================================
# P0-2 覆盖：报告页「加入训练计划」幂等接口
# POST /v1/training-plan/from-analysis/{analysis_id}
# ====================================================================
@pytest.mark.asyncio
async def test_add_to_plan_from_analysis_creates_plan(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """主路径：分析存在且有 issues → 当周计划被创建/追加，返回完整 plan."""
    from app.models.analysis import AnalysisIssue

    user_id = await _get_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        analysis_id = new_id("swa")
        db.add(
            SwingAnalysis(
                id=analysis_id, user_id=user_id, video_url="s3://x",
                video_file_size=1, camera_angle="face_on", club_type="driver",
                status="completed",
            )
        )
        # 注意：此接口从 AnalysisIssue 表里读 issues，而不是接受参数
        for it_type, sev in [("casting", "high"), ("over_the_top", "medium")]:
            db.add(
                AnalysisIssue(
                    id=new_id("ai"), analysis_id=analysis_id, issue_type=it_type,
                    name=it_type, severity=sev, description="...",
                )
            )
        await db.commit()

    resp = await client.post(
        f"/v1/training-plan/from-analysis/{analysis_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    plan = resp.json()["data"]
    assert plan["total_tasks"] == 2
    assert plan["completed_tasks"] == 0
    assert len(plan["tasks"]) == 2
    assert plan["source_analysis_id"] == analysis_id


@pytest.mark.asyncio
async def test_add_to_plan_from_analysis_idempotent(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """对同一 analysis 重复调用应是幂等的（不重复加任务）."""
    from app.models.analysis import AnalysisIssue

    user_id = await _get_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        aid = new_id("swa")
        db.add(
            SwingAnalysis(
                id=aid, user_id=user_id, video_url="s3://x", video_file_size=1,
                camera_angle="face_on", club_type="driver", status="completed",
            )
        )
        db.add(
            AnalysisIssue(
                id=new_id("ai"), analysis_id=aid, issue_type="casting",
                name="抛杆", severity="high", description="...",
            )
        )
        await db.commit()

    r1 = await client.post(
        f"/v1/training-plan/from-analysis/{aid}", headers=auth_headers
    )
    r2 = await client.post(
        f"/v1/training-plan/from-analysis/{aid}", headers=auth_headers
    )
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["data"]["total_tasks"] == r2.json()["data"]["total_tasks"] == 1


@pytest.mark.asyncio
async def test_add_to_plan_from_analysis_rejects_sample(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """sample 报告应被拒（40015）."""
    resp = await client.post(
        "/v1/training-plan/from-analysis/sample", headers=auth_headers
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40015


@pytest.mark.asyncio
async def test_add_to_plan_from_analysis_404(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """分析不存在 → 40402."""
    resp = await client.post(
        "/v1/training-plan/from-analysis/swa_doesnotexist", headers=auth_headers
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 40402


@pytest.mark.asyncio
async def test_add_to_plan_from_analysis_no_issues(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """分析没有 issue → 40015 不创建空 plan."""
    user_id = await _get_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        aid = new_id("swa")
        db.add(
            SwingAnalysis(
                id=aid, user_id=user_id, video_url="s3://x", video_file_size=1,
                camera_angle="face_on", club_type="driver", status="completed",
            )
        )
        await db.commit()

    resp = await client.post(
        f"/v1/training-plan/from-analysis/{aid}", headers=auth_headers
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40015


@pytest.mark.asyncio
async def test_add_to_plan_from_analysis_forbidden(
    client: AsyncClient, auth_headers: dict[str, str]
):
    """别人的分析 → 40302."""
    from uuid import uuid4

    from app.models.analysis import AnalysisIssue

    user_a_id = await _get_user_id(client, auth_headers)
    async with AsyncSessionLocal() as db:
        aid = new_id("swa")
        db.add(
            SwingAnalysis(
                id=aid, user_id=user_a_id, video_url="s3://x", video_file_size=1,
                camera_angle="face_on", club_type="driver", status="completed",
            )
        )
        db.add(
            AnalysisIssue(
                id=new_id("ai"), analysis_id=aid, issue_type="casting",
                name="抛杆", severity="high", description="...",
            )
        )
        await db.commit()

    login_b = await client.post(
        "/v1/auth/wechat-login", json={"code": f"pytest_{uuid4().hex}"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['data']['token']}"}
    resp = await client.post(
        f"/v1/training-plan/from-analysis/{aid}", headers=headers_b
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == 40302


def test_training_task_to_item_coerces_bad_status():
    """非法 status 降级，避免序列化链路抛 ValidationError."""
    from datetime import date as date_cls

    from app.models.training import TrainingTask

    t = TrainingTask(
        id="task_badstat",
        plan_id="plan_x",
        user_id="usr_x",
        drill_id="drill_towel_arm",
        scheduled_date=date_cls(2026, 5, 1),
        sort_order=1,
        status="oops",
    )
    item = training_service.training_task_to_item(t)
    assert item.status == "pending"


def test_normalize_list_camera_and_club_coerce_unknown():
    from app.services import analysis_service

    assert analysis_service.normalize_list_camera_angle("side_view", analysis_id="a1") == "face_on"
    assert analysis_service.normalize_list_club_type("seven_iron_legacy", analysis_id="a2") == "unknown"
