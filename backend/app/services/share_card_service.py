"""分享物料：小程序码 PNG 落对象存储（O-11/O-12 最小闭环）."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.integrations.minio import MinioStorageClient
from app.integrations.wechat_wxacode import fetch_wxacode_unlimited_png
from app.models.user import User
from app.services.analysis_service import _load_owned


async def ensure_share_wxa_code_url(
    *,
    db: AsyncSession,
    user: User,
    analysis_id: str,
    storage: MinioStorageClient,
) -> str:
    if analysis_id == "sample":
        raise BadRequestError(code=40001, message="示例报告不支持生成小程序码")

    await _load_owned(db, analysis_id, user, load_children=False)
    key = f"share/wxa/{analysis_id}.png"
    if storage.head_object(key):
        return storage.get_object_url(key)

    scene = f"i={analysis_id}"
    if len(scene) > 32:
        raise BadRequestError(code=40001, message="分析 ID 过长，无法生成小程序码 scene")

    png = await fetch_wxacode_unlimited_png(
        scene=scene,
        page="pages/analysis/report",
        width=430,
    )
    storage.put_object_bytes(key=key, data=png, content_type="image/png")
    return storage.get_object_url(key)
