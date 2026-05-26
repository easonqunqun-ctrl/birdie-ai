"""P2-M7-02：`engine_warnings[]` 字段 v0.1 数据结构与 collector。

设计要点（详 kickoff §4 / §4.4）
-------------------------------
- 与一期 `quality_warnings: list[str]`（low_light / camera_shake 等）**并存不合并**：
  `quality_warnings` 仍保持一期"画质/姿态软提示"语义；
  `engine_warnings` 仅承载"解码 / 归一化 / codec 降级"等引擎侧诊断信息。
- 单条 analysis 内 `engine_warnings` ≤ 32 项；超出由调用方截断 + Sentry
- V1 路径始终返回 `[]`（行为冻结），V2 路径才填值
- API 响应里全量返回（不做索引、不做过滤）

字段约束（kickoff §4.2）
| 字段 | 类型 | 说明 |
| code | str | 受控枚举：`decoded_hevc` / `hdr_tonemapped` / `fps_upsampled` 等 |
| level | str | `info` / `warn` / `error` 三档 |
| detail | str | 自由文本，便于排错（≤ 200 字符；本模块自动截断） |
| ts | str | ISO-8601 UTC 时间戳 |

> 本文件 M7-02 先落基础结构；M7-04 追加机位类码（camera_angle_*）；M7-07 追加阶段分割 V2 类码。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal

EngineWarningLevel = Literal["info", "warn", "error"]

KNOWN_CODES: frozenset[str] = frozenset(
    {
        # 容器/codec 类（M7-02）
        "decoded_hevc",
        "decoded_vp9",
        "decoded_h264",
        # 色彩管线类（M7-02）
        "hdr_tonemapped",
        "color_space_normalized",
        # 帧率类（M7-02）
        "fps_upsampled",
        "fps_downsampled",
        "slowmo_detected",
        "nominal_fps_used",
        # 音频类（M7-02）
        "audio_kept",
        "audio_dropped",
        # 降级提示
        "fallback_to_v1",
        "fixture_normalized",
        # 机位类（M7-04）
        "camera_angle_large_offset",
        "camera_angle_mismatch",
        # 阶段分割 V2 类（M7-07）
        "phase_seg_nn_not_ready",
        "phase_seg_v2_nn_failure",
        "phase_seg_v2_low_confidence",
        "phase_seg_v2_hard_constraint_fail",
    }
)

MAX_ENGINE_WARNINGS = 32
MAX_DETAIL_LEN = 200


@dataclass(frozen=True)
class EngineWarning:
    """单条 engine_warning 记录（可直接 `asdict` 序列化进 API 响应）。"""

    code: str
    level: EngineWarningLevel = "info"
    detail: str = ""
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def __post_init__(self) -> None:
        if self.level not in ("info", "warn", "error"):
            object.__setattr__(self, "level", "info")
        if len(self.detail) > MAX_DETAIL_LEN:
            object.__setattr__(self, "detail", self.detail[:MAX_DETAIL_LEN])

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def truncate_engine_warnings(
    warnings: list[EngineWarning],
    *,
    max_items: int = MAX_ENGINE_WARNINGS,
) -> list[EngineWarning]:
    """超过 max_items 时截断并追加一条 `engine_warnings_truncated` 提示。

    Sentry 上报由调用方决定（避免引入 raven/sentry-sdk 强依赖）。
    """
    if len(warnings) <= max_items:
        return warnings
    head = warnings[: max_items - 1]
    head.append(
        EngineWarning(
            code="engine_warnings_truncated",
            level="warn",
            detail=f"截断 {len(warnings) - (max_items - 1)} 条，详 Sentry",
        )
    )
    return head


def serialize_engine_warnings(
    warnings: list[EngineWarning],
) -> list[dict[str, str]]:
    """转为 API 响应可序列化的 list[dict]，自动截断。"""
    return [w.to_dict() for w in truncate_engine_warnings(warnings)]
