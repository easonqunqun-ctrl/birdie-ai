"""P2-M7-14 · V2 分析管线骨架（灰度可独立切换）。

设计要点
--------
- **复用 V1 大部分链路**（preprocess / pose / phases / features / scoring /
  recommend / 衍生产物）；本 PR 仅完成 **V2 路由打通** + 暴露 ``diagnose_v2``
  公共 API，方便 W34 接 P2-M7-02 / P2-M7-06 后无缝替换诊断与置信度填充。
- **降级安全**：YAML 加载失败 / V2 入口抛错 → fallback 到 V1 ``run_real_analysis``；
  线上日志打 ``v2_resources_unavailable_falling_back_to_v1`` 便于复盘。
- 报告 ``engine_version`` 字段由 ``main.py`` 在路由层最终覆盖；本模块内部不显式
  写值，避免与路由层重复。

P2-W5 收口
----------
- ✅ ``run_real_analysis_v2`` 通过 ``diagnose_fn=diagnose_v2`` 真正重诊 issues
- ✅ ``diagnose_v2`` 接受 ``PhaseSegmentResult`` 并填 ``key_frame_timestamp``
- ✅ YAML 全集 14 条规则覆盖 V1 全部 issue（``grip_weak`` 占位除外）

P2-W7 收口（V2 灌溉续）
----------------------
- ✅ ``_enrich_v2`` 注入 ``run_real_analysis(enrichment_fn=...)``，在 result 组装完
  后填三层 confidence + tier（M7-06）+ engine_warnings 占位（M7-02）
- ✅ V1 路径默认不调 enrichment_fn → ``analysis_confidence=1.0`` /
  ``IssueItem.confidence=None``（schema 默认值，向后兼容）
- ⏸ V2 pipeline 切到 ``phases_v2`` / ``preprocess_v2``：留 W8+（让 engine_warnings
  真有内容；当前 MVP 只在 fallback 时塞一条 ``fallback_to_v1`` 占位）
"""

from __future__ import annotations

import logging

from app import metrics
from app.pipeline.confidence import (
    analysis_tier,
    compute_analysis_confidence,
    issue_confidence,
    issue_tier,
)
from app.pipeline.constants import issue_meta
from app.pipeline.diagnose import (
    DiagnosedIssue,
    MAX_ISSUES,
    MIN_DISPLAY_CONFIDENCE,
)
from app.pipeline.engine_warnings import EngineWarning, serialize_engine_warnings
from app.pipeline.phases import PhaseSegmentResult
from app.pipeline.preprocess_v2 import (
    TARGET_FPS_V2,
    _ffprobe_extended,
)
from app.pipeline.rule_engine import (
    LOCALES_DIR,
    RULES_DIR,
    Rule,
    RuleEngine,
    RuleResult,
    load_locale,
    load_rules_from_yaml,
    render_i18n_key,
)
from app.schemas import AnalyzeRequest, AnalyzeResult

log = logging.getLogger("ai_engine.real_pipeline_v2")


# 进程级缓存：避免每次请求都 IO 读 YAML / JSON
_RULES_CACHE: list[Rule] | None = None
_LOCALE_CACHE: dict[str, str] | None = None


def _get_rules() -> list[Rule]:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        _RULES_CACHE = load_rules_from_yaml(RULES_DIR / "v2_starter.yaml")
    return _RULES_CACHE


def _get_locale() -> dict[str, str]:
    global _LOCALE_CACHE
    if _LOCALE_CACHE is None:
        _LOCALE_CACHE = load_locale(LOCALES_DIR / "zh_CN.json")
    return _LOCALE_CACHE


def reset_caches() -> None:
    """单测 / 热更新 / 配置回滚时清缓存。"""
    global _RULES_CACHE, _LOCALE_CACHE
    _RULES_CACHE = None
    _LOCALE_CACHE = None


def _severity_label(ratio: float) -> str:
    """将 0-1 severity ratio 折算成 V1 风格的 high/medium/low 标签。"""
    if ratio >= 0.7:
        return "high"
    if ratio >= 0.3:
        return "medium"
    return "low"


def _keyframe_timestamp(
    res: RuleResult, phases: PhaseSegmentResult | None
) -> float | None:
    """根据 ``phase_anchor`` 从 ``PhaseSegmentResult`` 计算关键帧秒数。

    优先级：top/impact → 用 ``top_frame`` / ``impact_frame``（与 V1 一致）；
    其余阶段 → 用对应 ``PhaseInfo.key_frame``。
    """
    if phases is None or phases.fps <= 0:
        return None
    anchor = res.phase_anchor
    if anchor == "top":
        frame = phases.top_frame
    elif anchor == "impact":
        frame = phases.impact_frame
    else:
        info = phases.phases.get(anchor)
        if info is None:
            return None
        frame = info.key_frame
    return round(frame / phases.fps, 2)


def _build_issue_from_rule_result(
    res: RuleResult,
    locale: dict[str, str],
    *,
    fallback_name: str | None = None,
    phases: PhaseSegmentResult | None = None,
) -> DiagnosedIssue:
    """RuleResult → DiagnosedIssue（沿用 V1 schema，便于 main.py 直接组装）。"""
    name = fallback_name or render_i18n_key(
        res.display_name_key, res.payload, locale_dict=locale
    )
    summary_key = res.display_name_key.replace(".title", ".summary")
    description = render_i18n_key(summary_key, res.payload, locale_dict=locale)
    return DiagnosedIssue(
        type=res.type,
        name=name,
        severity=_severity_label(res.severity),
        description=description,
        confidence=res.confidence,
        key_frame_timestamp=_keyframe_timestamp(res, phases),
        metrics=dict(res.payload),
    )


def diagnose_v2(
    features: dict[str, float],
    phases: PhaseSegmentResult | None = None,
    *,
    min_confidence: float = MIN_DISPLAY_CONFIDENCE,
    max_issues: int = MAX_ISSUES,
    engine: RuleEngine | None = None,
    locale: dict[str, str] | None = None,
    confidences: dict[str, float] | None = None,
) -> list[DiagnosedIssue]:
    """V2 诊断主入口：YAML 规则 + i18n locale → DiagnosedIssue。

    与 V1 ``diagnose`` 签名一致；report assembly 不需要分支。

    - ``confidences`` 缺省时所有规则置 1.0；W34 接 P2-M7-06 后由 issue_confidence 填充
    - ``phases`` 用于按 ``phase_anchor`` 填 ``key_frame_timestamp``；缺省时该字段为 None
    """
    rules_engine = engine or RuleEngine(rules=_get_rules())
    loc = locale if locale is not None else _get_locale()

    rule_confs = confidences or {r.name: 1.0 for r in rules_engine.rules}
    results = rules_engine.diagnose(features, confidences=rule_confs)

    issues: list[DiagnosedIssue] = []
    for res in results:
        try:
            fallback = issue_meta(res.type)["name"]
        except KeyError:
            fallback = None
        issue = _build_issue_from_rule_result(
            res, loc, fallback_name=fallback, phases=phases
        )
        if issue.confidence < min_confidence:
            continue
        issues.append(issue)

    return issues[:max_issues]


def _enrich_v2(result: AnalyzeResult, ctx) -> None:
    """P2-W7 ENG-B · V2 enrichment hook：填三层 confidence + engine_warnings 占位.

    在 ``real_pipeline.run_real_analysis`` 组装完 ``AnalyzeResult`` 后被调用一次。
    所有写操作都对 result 原地修改（IssueItem / AnalyzeResult 都是 Pydantic
    BaseModel，frozen=False 可改字段）。

    三层填法
    --------
    Layer 1 — feature_confidences（dict[feature_name, 0-1]）:
        MVP 简化：所有特征复用 ``pose_result.mean_confidence``。
        理由：精确实现需要建 FEATURE_LANDMARKS_MAP 把每个特征关联到 N 个
        landmarks，工作量大。W8+ 可换成 ``feature_confidence(visibility[:, landmarks])``
        逐特征精算。当前简化保证「不浮报」（mean 是上界）+ 提供端到端通路。

    Layer 2 — IssueItem.confidence / confidence_tier:
        对每个 issue 找对应的 YAML rule，取 rule.conditions[].feature 的
        feature_confidences 求平均 → 调 ``issue_confidence(...)`` →
        ``issue_tier(...)`` 折算 confirmed / leaning / hidden。
        阈值距离暂固定 0.5（W8+ 可基于 feature value 与 condition.threshold
        归一化距离精算）。

    Layer 3 — analysis_confidence:
        直接喂 ``compute_analysis_confidence(...)``；
        ``camera_angle_offset_deg=None`` 待 M7-04 接入后补。

    engine_warnings:
        MVP 阶段 V2 仍走 V1 pipeline，**正常路径不产生 warning**；
        ``run_real_analysis_v2`` fallback 时由 caller 注入一条 ``fallback_to_v1``。
    """
    pose = ctx.pose_result
    mean_vis = float(pose.mean_confidence) if pose.num_frames > 0 else 0.0

    # Layer 1 — feature_confidences（MVP：全部用 mean_vis）
    feature_names = list(ctx.features.keys())
    feature_confs = {name: round(mean_vis, 3) for name in feature_names}

    # Layer 2 — 每 issue confidence + tier
    rules = _get_rules()
    rules_by_name = {r.name: r for r in rules}
    for issue in result.issues:
        rule = rules_by_name.get(issue.type)
        if rule is None or not rule.conditions:
            # 不在 YAML 表里的 issue（V1 兼容路径），用全局 mean 作为兜底
            conf = mean_vis
        else:
            feats_for_issue = [
                feature_confs.get(c.feature, mean_vis) for c in rule.conditions
            ]
            # threshold_distance 暂固定 0.5（中等距离）；W8+ 可按 feature value 实算
            conf = issue_confidence(feats_for_issue, threshold_distance=0.5)
        issue.confidence = round(conf, 3)
        issue.confidence_tier = issue_tier(conf)

    # Layer 3 — analysis_confidence
    ac = compute_analysis_confidence(
        mean_visibility=mean_vis,
        quality_warnings=ctx.quality_warnings,
        camera_angle_offset_deg=None,  # M7-04 接入后补
        feature_confidences=feature_confs,
    )
    result.analysis_confidence = round(ac, 3)
    result.feature_confidences = feature_confs

    log.info(
        "v2_enrichment_done",
        extra={
            "analysis_id": result.analysis_id,
            "mean_visibility": round(mean_vis, 3),
            "analysis_confidence": result.analysis_confidence,
            "analysis_tier": analysis_tier(ac),
            "num_issues_confirmed": sum(
                1 for i in result.issues if i.confidence_tier == "confirmed"
            ),
            "num_issues_leaning": sum(
                1 for i in result.issues if i.confidence_tier == "leaning"
            ),
            "num_issues_hidden": sum(
                1 for i in result.issues if i.confidence_tier == "hidden"
            ),
        },
    )


def _probe_video_warnings(video_url: str) -> list[EngineWarning]:
    """P2-W8 ENG-C2 · 对原始 ``video_url`` 跑 ffprobe 探测，生成 engine_warnings.

    ffprobe 直接支持 HTTP / HTTPS URL（只读 header / 几 KB metadata，无需完整下载）。
    探测项：
    - ``decoded_hevc`` / ``decoded_vp9``：codec_name
    - ``hdr_tonemapped``：color_transfer ∈ {smpte2084, arib-std-b67}
    - ``slowmo_detected`` + ``nominal_fps_used``：mov/mp4 tags 检出真实帧率
    - ``fps_upsampled`` / ``fps_downsampled``：raw fps ≠ TARGET_FPS_V2
    - ``audio_kept`` / ``audio_dropped``：原视频是否含音轨

    出错（网络不通 / ffprobe 不识别 / 私有 URL 鉴权失败）静默返回空列表，
    **绝不阻塞主分析流程**——pipeline 主体仍走 V1，engine_warnings 仅为辅助信息。
    """
    if not video_url:
        return []
    try:
        probe = _ffprobe_extended(video_url)
    except Exception as exc:  # noqa: BLE001
        log.info(
            "v2_probe_failed_silently",
            extra={"video_url": video_url, "err": repr(exc)},
        )
        return []

    warnings: list[EngineWarning] = []

    if probe.codec_name in {"hevc", "h265"}:
        warnings.append(
            EngineWarning(
                code="decoded_hevc",
                level="info",
                detail=f"codec={probe.codec_name}",
            )
        )
    elif probe.codec_name == "vp9":
        warnings.append(
            EngineWarning(code="decoded_vp9", level="info", detail="codec=vp9")
        )
    elif probe.codec_name == "h264":
        warnings.append(
            EngineWarning(code="decoded_h264", level="info", detail="codec=h264")
        )

    if probe.is_hdr:
        warnings.append(
            EngineWarning(
                code="hdr_tonemapped",
                level="info",
                detail=(
                    f"color_transfer={probe.color_transfer} → bt709 "
                    f"(pix_fmt={probe.pix_fmt})"
                ),
            )
        )

    if probe.is_slowmo and probe.nominal_fps > 0:
        warnings.append(
            EngineWarning(
                code="slowmo_detected",
                level="info",
                detail=(
                    f"nominal_fps={probe.nominal_fps:.1f} vs "
                    f"fps_raw={probe.fps_raw:.1f}"
                ),
            )
        )
        warnings.append(
            EngineWarning(
                code="nominal_fps_used",
                level="info",
                detail=f"using nominal_fps={probe.nominal_fps:.1f} for timeline",
            )
        )

    if probe.fps_raw > 0 and abs(probe.fps_raw - TARGET_FPS_V2) > 0.5:
        code = "fps_upsampled" if probe.fps_raw < TARGET_FPS_V2 else "fps_downsampled"
        warnings.append(
            EngineWarning(
                code=code,
                level="info",
                detail=f"raw {probe.fps_raw:.1f}fps vs V2 target {TARGET_FPS_V2}fps",
            )
        )

    warnings.append(
        EngineWarning(
            code="audio_kept" if probe.has_audio else "audio_dropped",
            level="info",
            detail=("audio stream present" if probe.has_audio else "no audio stream"),
        )
    )

    return warnings


async def run_real_analysis_v2(req: AnalyzeRequest) -> AnalyzeResult:
    """V2 真实分析入口。

    P2-W5：通过 ``real_pipeline.run_real_analysis(diagnose_fn=diagnose_v2)`` 真正用
    YAML RuleEngine 重诊 issues；features 与 phases 由 V1 pipeline 计算后透传给
    ``diagnose_v2``。

    P2-W7：``enrichment_fn=_enrich_v2`` 在 result 组装完后注入三层 confidence + tier。

    出错降级：V2 资源（YAML / locale）加载失败 → 记日志后退回 V1 ``diagnose``，
    确保灰度期不影响报告交付；engine_warnings 注入一条 ``fallback_to_v1`` 占位
    让客户端看到本次走的是 V1。V1 入口抛 PipelineError 时直接透传，由 main.py
    统一捕获转 ``status=failed``。
    """
    from app.pipeline.real_pipeline import run_real_analysis

    diagnose_impl = None
    enrichment_impl = _enrich_v2
    fallback_warning: EngineWarning | None = None
    try:
        _get_rules()
        _get_locale()
        diagnose_impl = diagnose_v2
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "v2_resources_unavailable_falling_back_to_v1",
            extra={"analysis_id": req.analysis_id, "err": repr(exc)},
        )
        metrics.incr("v2_fallback_count")
        # YAML/locale 加载不上时不能跑 _enrich_v2（rules_by_name 为空），跳过；
        # 客户端能从 engine_warnings 看到走了 V1。
        enrichment_impl = None
        fallback_warning = EngineWarning(
            code="fallback_to_v1",
            level="warn",
            detail=f"V2 资源加载失败: {type(exc).__name__}",
        )

    # P2-W8 ENG-C：对原始视频跑一次 ffprobe，拿 codec/hdr/slowmo/fps/audio 信息
    # 做成 engine_warnings。在 V1 pipeline 跑之前（甚至并行）做，避免阻塞主流程。
    # 探测失败静默返回 []，绝不影响主分析。
    probe_warnings = _probe_video_warnings(req.video_url)

    result = await run_real_analysis(
        req, diagnose_fn=diagnose_impl, enrichment_fn=enrichment_impl
    )

    # 合并所有 engine_warnings：probe 探测 + fallback 占位（若有）
    all_warnings: list[EngineWarning] = list(probe_warnings)
    if fallback_warning is not None:
        all_warnings.append(fallback_warning)
    if all_warnings:
        result.engine_warnings = serialize_engine_warnings(all_warnings)

    return result


__all__ = [
    "_enrich_v2",
    "diagnose_v2",
    "reset_caches",
    "run_real_analysis_v2",
]
