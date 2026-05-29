"""P2-M12-07 · 职业镜头 PGC 解说 + LLM 对比解读."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AIChatServiceError, BadRequestError, NotFoundError
from app.core.logging import get_logger
from app.integrations.llm import AbstractLLMClient, Message
from app.models.analysis import SwingAnalysis
from app.models.pro_library import ProClipAnnotation, ProPlayer, ProSwingClip
from app.services import pro_library_service
from app.services.analysis_service import _load_owned

logger = get_logger("pro_pgc")

PGC_SYSTEM_PROMPT = """你是领翼 golf 的职业挥杆解说助手（PGC 风格）。
根据提供的职业镜头元数据、已有文字解说要点，以及（若有）用户本人分析报告摘要，
用中文写 2-4 段简短解读（每段 1-3 句）：
- 不要假装逐帧看过视频；只基于给出的分数、特征、阶段分与解说要点
- 语气专业、鼓励，适合小程序阅读
- 禁止伤病诊断、医疗建议、保证疗效类表述
- 若提供了用户报告，点出 1-2 个与职业参考的可对标差异即可，勿堆砌术语"""


async def list_clip_annotations(
    db: AsyncSession, clip_id: str
) -> list[ProClipAnnotation]:
    clip = await pro_library_service.get_clip(db, clip_id)
    if clip is None or not clip.is_published:
        raise NotFoundError(code=40406, message="镜头不存在或未发布")
    rows = await db.execute(
        select(ProClipAnnotation)
        .where(
            ProClipAnnotation.clip_id == clip_id,
            ProClipAnnotation.is_visible.is_(True),
        )
        .order_by(
            ProClipAnnotation.time_marker_ms.asc().nulls_last(),
            ProClipAnnotation.created_at.asc(),
        )
    )
    return list(rows.scalars().all())


def _format_ms(ms: int | None) -> str:
    if ms is None:
        return "全程"
    sec = max(0, ms // 1000)
    m, s = divmod(sec, 60)
    return f"{m:01d}:{s:02d}"


def build_pgc_llm_messages(
    *,
    clip: ProSwingClip,
    player: ProPlayer,
    annotations: list[ProClipAnnotation],
    analysis: SwingAnalysis | None,
) -> list[Message]:
    ann_lines = [
        f"- [{_format_ms(a.time_marker_ms)}] { (a.content or '').strip() }"
        for a in annotations
        if a.annotation_type == "text" and (a.content or "").strip()
    ]
    feat = clip.features_snapshot or {}
    feat_line = ", ".join(
        f"{k}={v}" for k, v in list(feat.items())[:8] if isinstance(v, (int, float))
    )
    user_block = ""
    if analysis is not None:
        phase_bits = []
        if analysis.phase_scores:
            for key, val in list(analysis.phase_scores.items())[:6]:
                if isinstance(val, dict) and val.get("score") is not None:
                    phase_bits.append(f"{key}={val['score']}")
        user_block = (
            f"\n用户报告摘要：综合分 {analysis.overall_score}；"
            f"球杆 {analysis.club_type}；机位 {analysis.camera_angle}；"
            f"阶段分 {', '.join(phase_bits) or '无'}"
        )

    user_prompt = (
        f"职业球手：{player.name}（{player.handedness}）\n"
        f"镜头：{clip.club_type} · {clip.camera_angle} · 综合分 {clip.overall_score}\n"
        f"特征快照：{feat_line or '无'}\n"
        f"已有 PGC 解说要点：\n"
        + ("\n".join(ann_lines) if ann_lines else "- 无")
        + user_block
        + "\n\n请输出 PGC 风格解读正文（不要标题编号以外的 markdown）。"
    )
    return [
        {"role": "system", "content": PGC_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


async def _complete_llm_text(
    client: AbstractLLMClient, messages: list[Message]
) -> str:
    chunks: list[str] = []
    error_msg: str | None = None
    async for chunk in client.stream_chat(
        messages, temperature=0.5, max_tokens=800
    ):
        if chunk.type == "content":
            chunks.append(chunk.delta)
        elif chunk.type == "error":
            error_msg = chunk.error or "LLM 调用失败"
            break
    text = "".join(chunks).strip()
    if error_msg is not None or not text:
        raise AIChatServiceError(
            code=50106,
            message="AI 解读暂时不可用，请稍后再试",
            detail=error_msg or "empty_response",
        )
    return text


async def generate_pgc_insight(
    db: AsyncSession,
    *,
    clip_id: str,
    user_id: str,
    analysis_id: str | None,
    llm_client: AbstractLLMClient,
) -> str:
    clip = await pro_library_service.get_clip(db, clip_id)
    if clip is None or not clip.is_published:
        raise NotFoundError(code=40406, message="镜头不存在或未发布")

    player = await pro_library_service.get_player(db, clip.pro_player_id)
    if player is None or not player.is_active:
        raise NotFoundError(code=40406, message="球手不存在或已下架")

    analysis: SwingAnalysis | None = None
    if analysis_id:
        analysis = await _load_owned(db, analysis_id, _FakeUser(user_id))
        if analysis.status != "completed":
            raise BadRequestError(code=40001, message="仅已完成分析可用于对比解读")
        if analysis.is_sample:
            raise BadRequestError(code=40093, message="示例分析报告不可用于 AI 解读")

    annotations = await list_clip_annotations(db, clip_id)
    messages = build_pgc_llm_messages(
        clip=clip, player=player, annotations=annotations, analysis=analysis
    )
    insight = await _complete_llm_text(llm_client, messages)
    logger.info(
        "pro_pgc_insight_generated",
        clip_id=clip_id,
        user_id=user_id,
        analysis_id=analysis_id,
        length=len(insight),
    )
    return insight


class _FakeUser:
    """供 ``_load_owned`` 使用的最小 user 对象."""

    def __init__(self, user_id: str) -> None:
        self.id = user_id


async def seed_initial_pgc_annotations(db: AsyncSession) -> list[ProClipAnnotation]:
    """幂等：为 demo clip 写入 3 条 text 解说."""

    from app.schemas.pro_library import ProClipAnnotationCreate

    await pro_library_service.seed_initial_pros(db)
    clip_row = await db.execute(
        select(ProSwingClip)
        .join(ProPlayer, ProPlayer.id == ProSwingClip.pro_player_id)
        .where(
            ProPlayer.name == "Demo Pro · 内置示例",
            ProSwingClip.is_published.is_(True),
        )
        .limit(1)
    )
    clip = clip_row.scalar_one_or_none()
    if clip is None:
        return []

    existing = await db.execute(
        select(ProClipAnnotation).where(ProClipAnnotation.clip_id == clip.id)
    )
    if existing.scalars().first() is not None:
        return list(existing.scalars().all())

    payloads = [
        ProClipAnnotationCreate(
            clip_id=clip.id,
            annotation_type="text",
            content="准备阶段：脊柱前倾角稳定，重心分布均匀。",
            time_marker_ms=0,
        ),
        ProClipAnnotationCreate(
            clip_id=clip.id,
            annotation_type="text",
            content="上杆顶点：肩转充分，左臂保持延展。",
            time_marker_ms=1200,
        ),
        ProClipAnnotationCreate(
            clip_id=clip.id,
            annotation_type="text",
            content="击球：髋部领先启动，杆面回正时机良好。",
            time_marker_ms=2200,
        ),
    ]
    created: list[ProClipAnnotation] = []
    for payload in payloads:
        created.append(await pro_library_service.add_annotation(db, payload))
    return created


__all__ = [
    "build_pgc_llm_messages",
    "generate_pgc_insight",
    "list_clip_annotations",
    "seed_initial_pgc_annotations",
]
