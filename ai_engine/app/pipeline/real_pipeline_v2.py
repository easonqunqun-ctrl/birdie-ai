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
from app.pipeline.camera_angle import (
    CameraAngleResult,
    angle_engine_warnings,
    attach_declared,
    detect_camera_angle,
    summarize_pose_for_angle,
)
from app.pipeline.confidence import (
    analysis_tier,
    compute_analysis_confidence,
    feature_confidence,
    issue_confidence,
    issue_tier,
)
from app.pipeline.constants import feature_meta, issue_meta
from app.pipeline.diagnose import (
    DiagnosedIssue,
    MAX_ISSUES,
    MIN_DISPLAY_CONFIDENCE,
)
from app.pipeline.engine_warnings import EngineWarning, serialize_engine_warnings
from app.pipeline.phases import PhaseSegmentResult
from app.pipeline.pose import (
    LANDMARK_LEFT_ANKLE,
    LANDMARK_LEFT_ELBOW,
    LANDMARK_LEFT_HIP,
    LANDMARK_LEFT_KNEE,
    LANDMARK_LEFT_SHOULDER,
    LANDMARK_LEFT_WRIST,
    LANDMARK_NOSE,
    LANDMARK_RIGHT_ANKLE,
    LANDMARK_RIGHT_ELBOW,
    LANDMARK_RIGHT_HIP,
    LANDMARK_RIGHT_KNEE,
    LANDMARK_RIGHT_SHOULDER,
    LANDMARK_RIGHT_WRIST,
)
from app.pipeline.preprocess_v2 import (
    TARGET_FPS_V2,
    _ffprobe_extended,
)
from app.pipeline.rule_engine import (
    LOCALES_DIR,
    RULES_DIR,
    Rule,
    RuleCondition,
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


# ============================================================
# P2-W9 ENG-D · enrichment 精算用：feature → landmark 依赖表 + phase 抽取
# ============================================================
#
# 设计：W7 MVP 全部 feature_confidence 用 pose.mean_confidence 一锅端，
# 不能反映「不同特征对不同身体部位的依赖差异」（比如 finish_balance 只看脚踝，
# 与肩腕 visibility 无关）。W9 把 docs/05 §2.5 15 个特征逐一映射到所用 landmark
# 子集，并按特征所在 phase 取相应帧 window，从 pose.visibility 子矩阵实算
# feature_confidence。
#
# 不依赖 lead/trail 手别的特征用静态 indices；依赖 lead 手别的（如 top_wrist_position
# / wrist_release_* / tempo_ratio / finish_height）在运行时按 ``phases.lead_wrist_idx``
# / ``phases.lead_shoulder_idx`` 动态取 idx。
#
# 与 `confidence.FEATURE_LANDMARK_DEPENDENCY` 的关系
# ------------------------------------------------
# confidence.py 里那张 dict 是 docs/05 kickoff §3.2.1 提供的「教学版样例」（只列了 3
# 个特征 + W18 注释），不构成生产单一真源。我们在 V2 enrichment 内部保留一份
# 完整 15 项依赖表，避免把 lead/trail 动态判定推进通用 confidence.py。

# 静态依赖（不依赖手别）：feature_name → 涉及的 MediaPipe landmark idx 列表
_STATIC_FEATURE_LANDMARKS: dict[str, list[int]] = {
    "spine_angle_setup": [
        LANDMARK_LEFT_SHOULDER, LANDMARK_RIGHT_SHOULDER,
        LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP,
    ],
    "knee_flexion_setup": [
        LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP,
        LANDMARK_LEFT_KNEE, LANDMARK_RIGHT_KNEE,
        LANDMARK_LEFT_ANKLE, LANDMARK_RIGHT_ANKLE,
    ],
    "shoulder_rotation_top": [LANDMARK_LEFT_SHOULDER, LANDMARK_RIGHT_SHOULDER],
    "hip_rotation_top": [LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP],
    "x_factor": [
        LANDMARK_LEFT_SHOULDER, LANDMARK_RIGHT_SHOULDER,
        LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP,
    ],
    "left_arm_straightness": [
        LANDMARK_LEFT_SHOULDER, LANDMARK_LEFT_ELBOW, LANDMARK_LEFT_WRIST,
    ],
    "downswing_sequence": [
        LANDMARK_LEFT_SHOULDER, LANDMARK_RIGHT_SHOULDER,
        LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP,
    ],
    "spine_angle_impact_delta": [
        LANDMARK_LEFT_SHOULDER, LANDMARK_RIGHT_SHOULDER,
        LANDMARK_LEFT_HIP, LANDMARK_RIGHT_HIP,
    ],
    "head_lateral_shift": [LANDMARK_NOSE],
    "finish_balance": [LANDMARK_LEFT_ANKLE, LANDMARK_RIGHT_ANKLE],
}


def _lead_landmark_indices(
    feature_name: str, phases: PhaseSegmentResult
) -> list[int] | None:
    """依赖手别的特征：按 ``phases.lead_wrist_idx`` / ``lead_shoulder_idx`` 动态算。

    返回 None 表示该特征不依赖手别（应去 ``_STATIC_FEATURE_LANDMARKS`` 查）。
    """
    lead_wrist = phases.lead_wrist_idx
    lead_shoulder = phases.lead_shoulder_idx
    # 对侧肘 idx：lead_wrist=15→LEFT_ELBOW=13；lead_wrist=16→RIGHT_ELBOW=14
    lead_elbow = (
        LANDMARK_LEFT_ELBOW if lead_wrist == LANDMARK_LEFT_WRIST else LANDMARK_RIGHT_ELBOW
    )
    if feature_name == "top_wrist_position":
        return [LANDMARK_NOSE, lead_wrist, lead_shoulder]
    if feature_name in ("wrist_release_angle", "wrist_release_timing"):
        return [lead_wrist, lead_elbow]
    if feature_name == "tempo_ratio":
        return [lead_wrist]
    if feature_name == "finish_height":
        return [lead_wrist, lead_shoulder]
    return None


def _landmark_indices_for(
    feature_name: str, phases: PhaseSegmentResult
) -> list[int]:
    """统一入口：feature_name → landmark idx 列表（含手别判定）。"""
    dyn = _lead_landmark_indices(feature_name, phases)
    if dyn is not None:
        return dyn
    return _STATIC_FEATURE_LANDMARKS.get(feature_name, [])


def _feature_phase_frames(
    feature_name: str, phases: PhaseSegmentResult, num_frames: int
) -> list[int]:
    """每特征对应的 phase 帧索引列表。

    选取策略（详 docs/05 §2.5 + features.py 实现）：
    - 单帧特征 → 该 key_frame ± 2 帧 window
    - 阶段区间特征 → start_frame..end_frame 闭区间
    - 跨阶段对比特征 → 两侧 key_frame 各取 window 后拼接
    - 全程特征 → swing_start..swing_end
    - finish_balance → follow_through 最后 10 帧
    """
    if num_frames <= 0:
        return []

    def _window(center: int, half: int = 2) -> list[int]:
        lo = max(0, center - half)
        hi = min(num_frames - 1, center + half)
        return list(range(lo, hi + 1)) if hi >= lo else []

    def _range(start: int, end: int) -> list[int]:
        s = max(0, start)
        e = min(num_frames - 1, end)
        return list(range(s, e + 1)) if e >= s else []

    phs = phases.phases
    if feature_name in ("spine_angle_setup", "knee_flexion_setup"):
        return _window(phs["setup"].key_frame)
    if feature_name in ("left_arm_straightness", "top_wrist_position"):
        return _window(phases.top_frame)
    if feature_name in ("shoulder_rotation_top", "hip_rotation_top", "x_factor"):
        # 跨 setup ↔ top：两侧各取 window
        return _window(phs["setup"].key_frame) + _window(phases.top_frame)
    if feature_name == "downswing_sequence":
        ds = phs.get("downswing")
        return _range(ds.start_frame, ds.end_frame) if ds else _range(phases.top_frame, phases.impact_frame)
    if feature_name in ("wrist_release_angle", "wrist_release_timing"):
        return _range(phases.top_frame, phases.impact_frame)
    if feature_name == "spine_angle_impact_delta":
        return _window(phs["setup"].key_frame) + _window(phases.impact_frame)
    if feature_name in ("head_lateral_shift", "tempo_ratio"):
        return _range(phases.swing_start, phases.swing_end)
    if feature_name == "finish_height":
        ft = phs.get("follow_through")
        return _window(ft.key_frame) if ft else []
    if feature_name == "finish_balance":
        ft = phs.get("follow_through")
        if ft is None:
            return []
        tail_start = max(ft.start_frame, ft.end_frame - 9)
        return _range(tail_start, ft.end_frame)
    # 未识别特征：保守取整个 swing 区间
    return _range(phases.swing_start, phases.swing_end)


def _visibility_sub_for_feature(
    pose,  # PoseResult
    phases: PhaseSegmentResult | None,
    feature_name: str,
) -> list[list[float]]:
    """从 ``pose.visibility[F, 33]`` 抠 (selected_frames, selected_landmarks) 子矩阵.

    返回 ``list[list[float]]``（pure-Python），匹配 ``confidence.feature_confidence``
    签名。``phases=None`` 或抠不到帧/landmark → 返回 ``[]``，让 ``feature_confidence``
    返回 0.0（不浮报）。
    """
    if phases is None or pose.num_frames <= 0:
        return []
    landmarks = _landmark_indices_for(feature_name, phases)
    if not landmarks:
        return []
    frames = _feature_phase_frames(feature_name, phases, pose.num_frames)
    if not frames:
        return []
    vis = pose.visibility  # numpy (F, 33)
    sub: list[list[float]] = []
    for f in frames:
        if f < 0 or f >= pose.num_frames:
            continue
        sub.append([float(vis[f, lm]) for lm in landmarks])
    return sub


# ============================================================
# P2-W9 ENG-D · issue_confidence 精算用：threshold_distance 实算
# ============================================================

# 触发方向（命中即 raw_dist > 0 还是 < 0）
_TRIGGER_SIGN_GREATER = {">", ">="}
_TRIGGER_SIGN_LESS = {"<", "<="}


def _compute_threshold_distance(
    feature_value: float, condition: RuleCondition
) -> float:
    """按 feature value 与 condition.threshold 的归一化距离算 td.

    归一化 scale = ``ideal_max - ideal_min``（从 ``constants.FEATURES`` 取，
    与 ``score_feature`` 的 tolerance 概念一致）；缺省 scale=1.0 兜底。

    方向判定：
    - operator ∈ {>, >=}：命中方向 = value > threshold；td = (value - threshold) / scale
    - operator ∈ {<, <=}：命中方向 = value < threshold；td = (threshold - value) / scale
    - 其它操作符（==/!=）：td = abs(value - threshold) / scale（兜底，不应在 V2 YAML 出现）
    - 反方向（value 在 threshold 错误侧）：td=0，issue_confidence 退化到 0.75 × feat_avg

    Clamp 到 [0, 5]：σ(5)≈0.993，factor≈0.997 ≈ 已饱和。
    """
    try:
        meta = feature_meta(condition.feature)
        scale = max(1e-6, float(meta["ideal_max"]) - float(meta["ideal_min"]))
    except KeyError:
        scale = 1.0

    op = condition.operator
    raw = float(feature_value) - float(condition.threshold)
    if op in _TRIGGER_SIGN_GREATER:
        signed = raw
    elif op in _TRIGGER_SIGN_LESS:
        signed = -raw
    else:
        signed = abs(raw)

    td = signed / scale
    if td < 0.0:
        return 0.0
    if td > 5.0:
        return 5.0
    return td


def _issue_threshold_distance(
    rule: Rule, features: dict[str, float]
) -> float:
    """聚合 rule 内 AND 条件的 threshold_distance。

    多条件 AND：取最小 td（短板原则——一个 condition 临界，整 issue 就不够确信）。
    无条件 → 0（落回 sigmoid 0.5 中位）。
    """
    if not rule.conditions:
        return 0.0
    tds: list[float] = []
    for c in rule.conditions:
        v = features.get(c.feature)
        if v is None:
            tds.append(0.0)
            continue
        tds.append(_compute_threshold_distance(v, c))
    return min(tds) if tds else 0.0


# ============================================================
# P2-W9 ENG-D · _enrich_v2 重写（精算 vs W7 MVP）
# ============================================================


def _enrich_v2(result: AnalyzeResult, ctx) -> None:
    """P2-W9 ENG-D · V2 enrichment hook（**精算版**）：三层 confidence + engine_warnings.

    与 W7 MVP 的差异
    -----------------
    Layer 1 (feature_confidences)
        W7: 所有特征同填 ``pose.mean_confidence``。
        W9: 每特征按 ``FEATURE_LANDMARK_DEPS[feature]`` 取 visibility 子矩阵 ×
            ``_feature_phase_frames(feature, phases)`` 选定帧 → 调
            ``feature_confidence(visibility_sub)`` 实算。**不同特征 confidence 真有差异**。

    Layer 2 (IssueItem.confidence / confidence_tier)
        W7: ``threshold_distance=0.5`` 固定常数。
        W9: 按 ``feature_value`` 与 ``rule.conditions[].threshold`` 的归一化距离实算
            （归一 scale = ideal_max - ideal_min）；多 AND 条件取 min td（短板）；
            sigmoid 折算后乘 feature_confidences 平均得 issue.confidence。
            **issue 偏离阈值越远，confidence 越高；临界值贴近时分档自动降到 leaning/hidden**。

    Layer 3 (analysis_confidence)
        与 W7 一致：``compute_analysis_confidence``，喂入 Layer 1 精算后的
        ``feature_confidences``（feat_avg 因此更"诚实"）。camera_angle_offset_deg
        仍 None（待 M7-04 落地后补）。

    engine_warnings
        W8 已落地：probe + fallback 由 ``run_real_analysis_v2`` 合并；本 hook 不动。
    """
    pose = ctx.pose_result
    phases = ctx.phases
    mean_vis = float(pose.mean_confidence) if pose.num_frames > 0 else 0.0

    # Layer 1 — feature_confidences（精算）
    feature_confs: dict[str, float] = {}
    feature_names = list(ctx.features.keys())
    for name in feature_names:
        sub = _visibility_sub_for_feature(pose, phases, name)
        if sub:
            conf = feature_confidence(sub)
        else:
            # 取不到子矩阵（phases 缺失 / 特征不在依赖表）：退化用 mean_vis 兜底，
            # 保证 ``analysis_confidence`` 的 feat_avg 不被 0 拖死
            conf = mean_vis
        feature_confs[name] = round(float(conf), 3)

    # Layer 2 — 每 issue confidence + tier（精算 td）
    rules = _get_rules()
    rules_by_name = {r.name: r for r in rules}
    for issue in result.issues:
        rule = rules_by_name.get(issue.type)
        if rule is None or not rule.conditions:
            # V1-only issue（不在 YAML 表）：用 mean_vis 兜底，没有 td 可算
            conf = mean_vis
        else:
            feats_for_issue = [
                feature_confs.get(c.feature, mean_vis) for c in rule.conditions
            ]
            td = _issue_threshold_distance(rule, ctx.features)
            conf = issue_confidence(feats_for_issue, threshold_distance=td)
        issue.confidence = round(conf, 3)
        issue.confidence_tier = issue_tier(conf)

    # P2-W12-2 · 机位独立标尺：M7-04 已落地（camera_angle.py），把 offset_deg 真正
    # 喂给 compute_analysis_confidence；>15° 偏角 angle_penalty=0.6（confidence.py
    # ANGLE_PENALTY_BAD），让"偏角太大的低质量视频"在 analysis_confidence 上真被惩罚。
    # 同时把 angle_engine_warnings 追加到 result.engine_warnings，让客户端能看到
    # 「camera_angle_large_offset / camera_angle_mismatch」具体原因。
    # P2-W13-B：传 ctx.declared_camera_angle 让 attach_declared 计算 mismatch
    # （用户声明 face_on 但 detected dtl 时追加 camera_angle_mismatch warning）
    angle_result = _maybe_detect_angle(
        pose, declared_camera_angle=getattr(ctx, "declared_camera_angle", None)
    )
    camera_offset = angle_result.offset_deg if angle_result is not None else None
    angle_warns = angle_engine_warnings(angle_result) if angle_result is not None else []

    # Layer 3 — analysis_confidence（用精算后的 feature_confs + 机位 offset 惩罚）
    ac = compute_analysis_confidence(
        mean_visibility=mean_vis,
        quality_warnings=ctx.quality_warnings,
        camera_angle_offset_deg=camera_offset,
        feature_confidences=feature_confs,
    )
    result.analysis_confidence = round(ac, 3)
    result.feature_confidences = feature_confs

    # angle warnings 与 run_real_analysis_v2 末尾合并的 probe + fallback warnings
    # 是不同来源；在这里先写到 result，由 run_real_analysis_v2 末尾**合并**而非
    # 覆盖（W12-2 同步调整了合并逻辑）
    if angle_warns:
        existing = list(result.engine_warnings or [])
        existing.extend(serialize_engine_warnings(angle_warns))
        result.engine_warnings = existing

    log.info(
        "v2_enrichment_done",
        extra={
            "analysis_id": result.analysis_id,
            "mean_visibility": round(mean_vis, 3),
            "feature_conf_min": (
                round(min(feature_confs.values()), 3) if feature_confs else 0.0
            ),
            "feature_conf_max": (
                round(max(feature_confs.values()), 3) if feature_confs else 0.0
            ),
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
            "camera_offset_deg": (
                round(camera_offset, 1) if camera_offset is not None else None
            ),
            "camera_detected_angle": (
                angle_result.detected_angle if angle_result is not None else None
            ),
        },
    )


def _summarize_pose_for_angle(pose) -> object | None:  # _PoseSummary 是私有类型，故 object
    """P2-W12-2 · 从 PoseResult 聚合机位检测所需的 6 个关键点几何摘要.

    策略：
    - 只用 valid 帧（``pose.valid_mask=True``）的均值，避开漏检帧引入噪声
    - 6 个 landmark：左右肩 / 左右髋 / 鼻（头部代理）的 x,y
    - ``valid_frame_ratio`` 直接走 ``pose.valid_frame_ratio``（已是 0-1）

    返回 ``None`` 表示输入不可用（无有效帧），调用方跳过 angle 注入。
    """
    if pose is None or pose.num_frames == 0 or pose.valid_mask.sum() == 0:
        return None
    kp = pose.keypoints  # (F, 33, 3)
    mask = pose.valid_mask
    try:
        valid = kp[mask]  # (V, 33, 3)
        left_shoulder = valid[:, LANDMARK_LEFT_SHOULDER]
        right_shoulder = valid[:, LANDMARK_RIGHT_SHOULDER]
        left_hip = valid[:, LANDMARK_LEFT_HIP]
        right_hip = valid[:, LANDMARK_RIGHT_HIP]
        nose = valid[:, LANDMARK_NOSE]
    except Exception:  # noqa: BLE001 - 关键点维度异常时直接放弃 angle 注入
        return None
    return summarize_pose_for_angle(
        left_shoulder_x=float(left_shoulder[:, 0].mean()),
        right_shoulder_x=float(right_shoulder[:, 0].mean()),
        left_hip_x=float(left_hip[:, 0].mean()),
        right_hip_x=float(right_hip[:, 0].mean()),
        head_x=float(nose[:, 0].mean()),
        head_y=float(nose[:, 1].mean()),
        valid_frame_ratio=float(pose.valid_frame_ratio),
    )


def _maybe_detect_angle(
    pose, declared_camera_angle: str | None = None
) -> CameraAngleResult | None:
    """W12-2 · 在 _enrich_v2 / _enrich_v2_fallback 共用的 angle 探测入口.

    W13-B：可选透传用户声明的机位 ``declared_camera_angle``，让
    ``attach_declared`` 计算 mismatch（detected != declared 且 confidence ≥ 0.7
    时 mismatch=True），从而 ``angle_engine_warnings`` 会再追加一条
    ``camera_angle_mismatch`` warning 让客户端调试浮层看到声明与检测不一致。

    任何一步失败（关键点异常 / detect 抛错 / declared 不在已知别名表）→ 返回
    None，调用方按"未知机位"继续走（``compute_analysis_confidence
    (camera_angle_offset_deg=None)``）。
    """
    summary = _summarize_pose_for_angle(pose)
    if summary is None:
        return None
    try:
        result = detect_camera_angle(summary)  # type: ignore[arg-type]
        if declared_camera_angle is not None:
            try:
                result = attach_declared(result, declared_camera_angle)
            except Exception as exc:  # noqa: BLE001
                # declared 不在已知别名表（ValueError）→ 不阻塞主流程，
                # 仅 log + 返回不带 mismatch 的 result
                log.info(
                    "v2_camera_angle_attach_declared_failed",
                    extra={
                        "declared": declared_camera_angle,
                        "err_type": type(exc).__name__,
                        "err": repr(exc)[:200],
                    },
                )
        return result
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "v2_camera_angle_detect_failed",
            extra={"err_type": type(exc).__name__, "err": repr(exc)[:200]},
        )
        return None


# ----------------------------------------------------------------------
# P2-W14-D · probe helpers 已抽到 app/integrations/probe.py
#
# 为什么这里仍然 re-export 下划线名：
# - 现有 W12-3 / W13-C 单测直接 from app.pipeline.real_pipeline_v2 import
#   _sanitize_probe_url / _rewrite_to_internal_url / _classify_probe_error
#   _probe_with_retry / _probe_video_warnings
# - 不能为了一次重构强行改 30+ 处测试 import；保留 thin alias 让历史测试稳过
# - 新代码（W15+）应**直接** from app.integrations.probe import probe_video_warnings 等
# - W18+ 单测集中迁移后这层 alias 可删
# ----------------------------------------------------------------------

from app.integrations.probe import (  # noqa: E402 (re-export 故意放在文件中段)
    _ProbeRetryOutcome,  # noqa: F401  (W12-3 测试 import)
    _probe_with_retry,  # noqa: F401  (W12-3 测试 import)
    classify_probe_error as _classify_probe_error,  # noqa: F401  (W12-3 测试 import)
    probe_video_warnings as _probe_video_warnings,
    rewrite_to_internal_url as _rewrite_to_internal_url,  # noqa: F401  (W13-C 测试 import)
    sanitize_probe_url as _sanitize_probe_url,  # noqa: F401  (W12-3 测试 import)
)


def _enrich_v2_fallback(result: AnalyzeResult, ctx) -> None:
    """V2 资源加载失败 → enrichment_fn 退化版.

    P2-W9+ review fix（P1-1）：之前 fallback 路径下 enrichment_fn=None，schema 默认
    ``analysis_confidence=1.0`` / ``feature_confidences={}``——客户端会看到「高可信
    + fallback_to_v1 warning」**自相矛盾**的报告。

    本退化版只做 Layer 3 的 ``analysis_confidence`` 兜底：用 pose mean_visibility
    + quality_warnings 算一个保守的 analysis_confidence，避免谎报 1.0。不动 Layer
    1/2（feature_confidences / IssueItem.confidence 都按 schema 默认空 / None）。

    P2-W12-2：fallback 路径也接入 camera_angle 检测——偏角过大时同样要惩罚
    confidence，避免"V2 资源缺 + 偏角大"双重低质量的报告还报 1.0。
    """
    pose = ctx.pose_result
    mean_vis = float(pose.mean_confidence) if pose.num_frames > 0 else 0.0
    # W13-B：fallback 路径也传 declared_camera_angle 让 mismatch warning 生成
    angle_result = _maybe_detect_angle(
        pose, declared_camera_angle=getattr(ctx, "declared_camera_angle", None)
    )
    camera_offset = angle_result.offset_deg if angle_result is not None else None
    ac = compute_analysis_confidence(
        mean_visibility=mean_vis,
        quality_warnings=ctx.quality_warnings,
        camera_angle_offset_deg=camera_offset,
        feature_confidences=None,  # 没精算，feat_avg=1.0 不惩罚
    )
    result.analysis_confidence = round(ac, 3)
    # fallback 路径仍把 angle warnings 灌进去，让客户端能看到具体诊断原因
    if angle_result is not None:
        angle_warns = angle_engine_warnings(angle_result)
        if angle_warns:
            existing = list(result.engine_warnings or [])
            existing.extend(serialize_engine_warnings(angle_warns))
            result.engine_warnings = existing


async def run_real_analysis_v2(req: AnalyzeRequest) -> AnalyzeResult:
    """V2 真实分析入口。

    P2-W5：通过 ``real_pipeline.run_real_analysis(diagnose_fn=diagnose_v2)`` 真正用
    YAML RuleEngine 重诊 issues；features 与 phases 由 V1 pipeline 计算后透传给
    ``diagnose_v2``。

    P2-W7：``enrichment_fn=_enrich_v2`` 在 result 组装完后注入三层 confidence + tier。

    P2-W9+ review fix：V2 资源加载失败 → enrichment 用 ``_enrich_v2_fallback`` 兜底
    Layer 3 的 ``analysis_confidence``，避免谎报 1.0。

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
        # YAML/locale 加载不上时不能跑 _enrich_v2（rules_by_name 为空），但仍要给
        # Layer 3 analysis_confidence 一个真值，否则客户端看「fallback + 高可信」矛盾。
        enrichment_impl = _enrich_v2_fallback
        fallback_warning = EngineWarning(
            code="fallback_to_v1",
            level="warn",
            detail=f"V2 资源加载失败: {type(exc).__name__}",
        )

    # P2-W8 ENG-C：对原始视频跑一次 ffprobe，拿 codec/hdr/slowmo/fps/audio 信息
    # 做成 engine_warnings。在 V1 pipeline 跑之前（甚至并行）做，避免阻塞主流程。
    # 探测失败静默返回 []，绝不影响主分析（metrics 仍记数，便于线上观察）。
    probe_warnings = _probe_video_warnings(req.video_url)

    result = await run_real_analysis(
        req, diagnose_fn=diagnose_impl, enrichment_fn=enrichment_impl
    )

    # 合并所有 engine_warnings：probe 探测 + fallback 占位（若有）
    # P2-W12-2：`_enrich_v2` / `_enrich_v2_fallback` 已经把 camera_angle warnings
    # 写到 result.engine_warnings；这里改成**合并而非覆盖**，否则 angle warnings
    # 会被覆盖丢掉。顺序：probe（前置）→ enrich 已有（含 angle）→ fallback。
    all_warnings: list[EngineWarning] = list(probe_warnings)
    if fallback_warning is not None:
        all_warnings.append(fallback_warning)
    if all_warnings:
        existing = list(result.engine_warnings or [])
        result.engine_warnings = existing + serialize_engine_warnings(all_warnings)

    return result


__all__ = [
    "_enrich_v2",
    "_enrich_v2_fallback",
    "diagnose_v2",
    "reset_caches",
    "run_real_analysis_v2",
]
