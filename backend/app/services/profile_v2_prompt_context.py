"""P2-M9-04 · 画像 2.0 LLM prompt 上下文构造器。

职责
----
- 从 `UserProfileV2` 抽取 **可向 LLM 透传** 的字段（含目标、训练偏好）
- **硬隔离 `known_injuries`**（docs/06 §13.1，与 M9-03 AC-3 配套）
- 输出一段 ≤200 字的 prompt 片段，由 `chat_prompt.build_system_prompt`
  在 V2 用户上拼接到 system prompt 之后

实现注意
--------
- M9-04 PR 不动 `chat_prompt.py` 主流程；外部调用方在合适位置追加本模块输出即可
- 若用户没启 PHASE2_PROFILE_V2_ENABLED → 调用 `build_v2_context(None)` 返回 ""
- 字段全空时返回 ""，避免给 LLM 灌空"】"
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# 与 M9-04 kickoff §3.2 一致
ALLOWED_STYLES = ("video", "text", "mixed")
ALLOWED_CADENCES = ("daily", "2x_per_week", "weekly")
ALLOWED_DRILL_TYPES = (
    "rhythm",
    "swing_plane",
    "tempo",
    "balance",
    "weight_transfer",
    "wrist_release",
    "follow_through",
    "setup",
)

# 中文标签（LLM 模板内呈现）
_STYLE_LABEL = {
    "video": "视频派（优先给可视化示范）",
    "text": "文字派（优先给步骤化文字说明）",
    "mixed": "视频/文字均可",
}

# style 对应的"作答风格指令"，写入 prompt 让 LLM 输出形态明显分化（AC-2）
_STYLE_DIRECTIVE = {
    "video": (
        "回复时优先推荐含视频示范的 drill_id，"
        "并提示『可看视频对照动作要点』；不要长篇文字步骤。"
    ),
    "text": (
        "回复时用编号步骤详细文字说明每个动作要点，"
        "不要堆叠视频链接；可引用关键时间戳但不依赖视觉对照。"
    ),
    "mixed": (
        "回复时视频示范与文字步骤兼顾，让用户自行选择对照方式。"
    ),
}
_CADENCE_LABEL = {
    "daily": "每日 1 次",
    "2x_per_week": "每周 2 次",
    "weekly": "每周 1 次",
}
_DRILL_LABEL = {
    "rhythm": "节奏",
    "swing_plane": "挥杆平面",
    "tempo": "节拍",
    "balance": "重心平衡",
    "weight_transfer": "重心转移",
    "wrist_release": "手腕释放",
    "follow_through": "完成动作",
    "setup": "站位 / 握杆",
}

# 已知伤病 → **永不**进入 LLM 上下文。
# 这里维护一份"禁止白名单"，调用方可 import 校验。
LLM_FORBIDDEN_PROFILE_FIELDS = frozenset(
    {
        "known_injuries",
        "height_cm",
        "weight_kg",
        "handicap_official",  # 真实差点（敏感等级"中"）；如需向 LLM 透传，单独评审
    }
)


def _coerce_style(value: Any) -> str | None:
    if value in ALLOWED_STYLES:
        return value
    return None


def _coerce_cadence(value: Any) -> str | None:
    if value in ALLOWED_CADENCES:
        return value
    return None


def _coerce_drill_types(value: Any) -> list[str]:
    if not value or not isinstance(value, (list, tuple)):
        return []
    return [v for v in value if isinstance(v, str) and v in ALLOWED_DRILL_TYPES]


def extract_v2_context(
    *,
    handicap_self: Any = None,
    mid_long_goals: Any = None,
    training_preference: Any = None,
    training_preference_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """从 raw 字段抽取 LLM 可消费的上下文 dict（结构清晰、可单测）。

    参数允许传 Decimal / None / 任意类型，函数内部做防御性转换。
    返回 dict 中的字段：
    - ``handicap_self``: Optional[float]（来自 user_profiles_v2.handicap_self）
    - ``mid_long_goals``: list[str]（最多取前 3 条；超长截断）
    - ``style``: 'video'|'text'|'mixed' | None
    - ``cadence``: 'daily'|'2x_per_week'|'weekly' | None
    - ``preferred_drill_types``: list[str]
    """
    # handicap_self
    h: float | None = None
    if handicap_self is not None:
        try:
            h = float(handicap_self)
        except (TypeError, ValueError):
            h = None

    # goals
    goals: list[str] = []
    if isinstance(mid_long_goals, (list, tuple)):
        goals = [str(g)[:80] for g in mid_long_goals if g][:3]

    # style
    style = _coerce_style(training_preference)

    # meta
    meta = training_preference_meta or {}
    cadence = _coerce_cadence(meta.get("cadence"))
    drill_types = _coerce_drill_types(meta.get("preferred_drill_types"))

    return {
        "handicap_self": h,
        "mid_long_goals": goals,
        "style": style,
        "cadence": cadence,
        "preferred_drill_types": drill_types,
    }


def render_v2_prompt_block(context: Mapping[str, Any]) -> str:
    """把抽取后的 context 渲染成 ≤200 字 prompt 片段。

    所有字段都缺 → 返回 ""（调用方决定拼不拼）。
    """
    parts: list[str] = []

    if context.get("handicap_self") is not None:
        parts.append(f"差点：{context['handicap_self']:g}")
    if context.get("mid_long_goals"):
        parts.append("目标：" + "、".join(context["mid_long_goals"]))

    style = context.get("style")
    if style:
        parts.append(_STYLE_LABEL[style])

    cadence = context.get("cadence")
    if cadence:
        parts.append(f"训练频率：{_CADENCE_LABEL[cadence]}")

    drill_types = context.get("preferred_drill_types") or []
    if drill_types:
        parts.append("drill 偏好：" + "、".join(_DRILL_LABEL[t] for t in drill_types))

    if not parts:
        return ""

    block = "【画像 2.0】" + "；".join(parts) + "。"

    # style 指令独立一行，让 LLM 输出形态有显著区分（AC-2 差异化门槛）
    if style and style in _STYLE_DIRECTIVE:
        block += "\n【作答风格】" + _STYLE_DIRECTIVE[style]

    return block


def build_v2_context(profile) -> str:
    """一站式入口：profile 可以是 ``UserProfileV2`` ORM、dict 或 None。

    返回空字符串当 profile 缺失或字段全空。
    """
    if profile is None:
        return ""

    # 兼容 ORM / dict 输入
    if isinstance(profile, Mapping):
        getter = profile.get
    else:
        def getter(key, default=None):  # type: ignore[no-redef]
            return getattr(profile, key, default)

    ctx = extract_v2_context(
        handicap_self=getter("handicap_self"),
        mid_long_goals=getter("mid_long_goals"),
        training_preference=getter("training_preference"),
        training_preference_meta=getter("training_preference_meta"),
    )
    return render_v2_prompt_block(ctx)


__all__ = [
    "ALLOWED_CADENCES",
    "ALLOWED_DRILL_TYPES",
    "ALLOWED_STYLES",
    "LLM_FORBIDDEN_PROFILE_FIELDS",
    "build_v2_context",
    "extract_v2_context",
    "render_v2_prompt_block",
]
