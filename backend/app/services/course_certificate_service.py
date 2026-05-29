"""P2-M11-05 · 课程通关证书 / 阶段勋章（对齐 kickoff §3.4）.

证书图像由客户端 Canvas 合成（复用 M5 海报能力）；服务端落库 + 渲染元数据，
``cert_url`` 预留对象存储 key，待用户「保存到相册」后可异步回填（非 MVP 阻塞项）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.course import Course, CourseCertificate
from app.models.user import User

STAGE_BADGE_LABELS: dict[int, str] = {
    1: "入门过关",
    2: "基础夯实",
    3: "进阶突破",
    4: "整合自如",
    5: "精修有成",
    6: "高阶认证",
    7: "大师之阶",
}

STAGE_TITLES: dict[int, str] = {
    1: "第 1 阶 · 入门",
    2: "第 2 阶 · 基础",
    3: "第 3 阶 · 进阶",
    4: "第 4 阶 · 整合",
    5: "第 5 阶 · 精修",
    6: "第 6 阶 · 高阶",
    7: "第 7 阶 · 大师",
}


def badge_label_for_stage(stage: int) -> str:
    return STAGE_BADGE_LABELS.get(stage, f"第 {stage} 阶通关")


def stage_title_for(stage: int) -> str:
    return STAGE_TITLES.get(stage, f"第 {stage} 阶")


def holder_display_name(user: User | None, *, fallback: str = "球友") -> str:
    if user is None:
        return fallback
    return (user.nickname or "").strip() or fallback


def populate_certificate_metadata(
    cert: CourseCertificate,
    *,
    course: Course,
    holder_name: str,
) -> None:
    """写入 ``extra_metadata`` 供客户端 Canvas 渲染；幂等合并已有键."""

    meta = dict(cert.extra_metadata or {})
    meta.update(
        {
            "course_title": course.title,
            "course_code": course.code,
            "badge_label": badge_label_for_stage(course.stage),
            "holder_name": holder_name,
            "stage_title": stage_title_for(course.stage),
        }
    )
    cert.extra_metadata = meta
    if not cert.cert_url:
        cert.cert_url = f"certs/{cert.user_id}/{cert.id}.png"


def certificate_to_read_dict(
    cert: CourseCertificate,
    *,
    course_title: str,
    holder_name: str | None = None,
) -> dict:
    meta = cert.extra_metadata or {}
    return {
        "id": cert.id,
        "user_id": cert.user_id,
        "course_id": cert.course_id,
        "stage": cert.stage,
        "cert_url": cert.cert_url,
        "issued_at": cert.issued_at,
        "revoked_at": cert.revoked_at,
        "course_title": course_title,
        "badge_label": meta.get("badge_label") or badge_label_for_stage(cert.stage),
        "holder_name": holder_name or meta.get("holder_name") or "球友",
        "stage_title": meta.get("stage_title") or stage_title_for(cert.stage),
    }


async def list_user_certificates(
    db: AsyncSession, user_id: str
) -> list[dict]:
    rows = await db.execute(
        select(CourseCertificate, Course.title, User.nickname)
        .join(Course, Course.id == CourseCertificate.course_id)
        .join(User, User.id == CourseCertificate.user_id)
        .where(
            CourseCertificate.user_id == user_id,
            CourseCertificate.revoked_at.is_(None),
        )
        .order_by(CourseCertificate.issued_at.desc())
    )
    out: list[dict] = []
    for cert, course_title, nickname in rows.all():
        holder = (nickname or "").strip() or "球友"
        out.append(
            certificate_to_read_dict(
                cert,
                course_title=course_title,
                holder_name=holder,
            )
        )
    return out


async def get_user_certificate(
    db: AsyncSession, *, user_id: str, cert_id: str
) -> dict:
    row = await db.execute(
        select(CourseCertificate, Course.title, User.nickname)
        .join(Course, Course.id == CourseCertificate.course_id)
        .join(User, User.id == CourseCertificate.user_id)
        .where(
            CourseCertificate.id == cert_id,
            CourseCertificate.revoked_at.is_(None),
        )
    )
    item = row.one_or_none()
    if item is None:
        raise NotFoundError(code=40406, message="证书不存在")
    cert, course_title, nickname = item
    if cert.user_id != user_id:
        raise ForbiddenError(code=40301, message="无权查看该证书")
    holder = (nickname or "").strip() or "球友"
    return certificate_to_read_dict(
        cert,
        course_title=course_title,
        holder_name=holder,
    )


__all__ = [
    "STAGE_BADGE_LABELS",
    "STAGE_TITLES",
    "badge_label_for_stage",
    "certificate_to_read_dict",
    "get_user_certificate",
    "holder_display_name",
    "list_user_certificates",
    "populate_certificate_metadata",
    "stage_title_for",
]
