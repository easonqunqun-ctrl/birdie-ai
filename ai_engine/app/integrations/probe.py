"""ffprobe / 对象存储探测模块（P2-W14-D 从 real_pipeline_v2 抽离）.

历史脉络
--------
- **W7** 首版 ``_probe_video_warnings`` 落在 ``real_pipeline_v2.py``，纯 ffprobe 包一层
- **W8 ENG-C2** 加 codec/HDR/慢动作/fps/audio 分类
- **W9** review fix · 失败不再静默 + metrics
- **W12-3** 5xx/timeout 指数退避 retry + 错误分类 + URL 脱敏 + ``probe_failed``
  ``EngineWarning``（不再返 ``[]``，让客户端调试浮层能看到失败原因）+ 6 个分桶 metrics
- **W13-C** RCA 出"ai_engine 经公网→nginx→minio 绕 4 跳"的 5xx 根因，加
  ``_rewrite_to_internal_url`` 缩短到 docker 内网 1 跳
- **W14-D**（本提交）把所有 probe 相关 helper（rewrite/sanitize/classify/retry +
  公开入口 ``probe_video_warnings``）从 ``real_pipeline_v2.py`` 抽到本模块

为什么独立成模块
----------------
1. **复用预期**：W16+ backend 也想给 share_card 跑 thumbnail 探测；W18+ 切 COS 时
   `_rewrite_to_internal_url` 还要复用（只改 endpoint 不改逻辑）
2. **单测独立性**：probe 行为不依赖 mediapipe 推理；单测可在普通 dev venv 跑
3. **可观测性集中**：所有 ``v2_probe_*`` metrics 来源只此一家，方便 W13-D
   Prometheus alerting 维护
4. **real_pipeline_v2.py 已经 1000+ 行**：再加 ~250 行 probe 代码主线太长

公开 API（``__all__``）
----------------------
- ``probe_video_warnings(video_url) -> list[EngineWarning]``：单一入口，对外只暴露这个
- ``rewrite_to_internal_url(url) -> str``：单测和未来扩展用（不暴露给 pipeline 业务层）
- ``sanitize_probe_url(url) -> str``：log 脱敏；其它模块写日志时如果带 video_url 也应该用这个
- ``classify_probe_error(exc) -> str``：错误分类；W16+ backend probe 集成时复用同套桶

向后兼容
--------
- ``real_pipeline_v2.py`` 里仍保留 ``_probe_video_warnings`` / ``_rewrite_to_internal_url``
  等下划线名作为 thin re-export，让 W12-3 / W13-C 现有单测（直接 import
  ``rp2_mod._sanitize_probe_url``）继续通过；W15+ 再迁单测路径
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass

from app import metrics
from app.config import settings
from app.pipeline.engine_warnings import EngineWarning
from app.pipeline.preprocess_v2 import TARGET_FPS_V2, _ffprobe_extended

__all__ = [
    "probe_video_warnings",
    "rewrite_to_internal_url",
    "sanitize_probe_url",
    "classify_probe_error",
]

log = logging.getLogger("ai_engine.integrations.probe")


# ----------------------------------------------------------------------
# URL helpers
# ----------------------------------------------------------------------


def sanitize_probe_url(url: str) -> str:
    """W12-3 · MinIO 预签名 URL 的 query string 含 X-Amz-Signature 等机密；log 时只留 path."""
    if not url:
        return ""
    q_idx = url.find("?")
    return url if q_idx < 0 else url[:q_idx]


def rewrite_to_internal_url(url: str) -> str:
    """W13-C · 把公网 video_url 改写成容器内网 URL，避免 ffprobe 绕公网回环.

    详见 docs/release-notes/minio-ffprobe-5xx-rca.md。

    例子：
    ::

        input  = "https://api.birdieai.cn/minio/xiaoniao-videos/uploads/x.mp4"
                  └─ MINIO_PUBLIC_ENDPOINT = https://api.birdieai.cn/minio ─┘
        output = "http://minio:9000/xiaoniao-videos/uploads/x.mp4"
                  └─ MINIO_ENDPOINT = http://minio:9000 ─┘

    链路从"ai_engine → 公网 DNS → CVM nginx → /minio/ → minio:9000" (4 跳)
    缩短到"ai_engine → docker 内网 → minio:9000" (1 跳)。

    不命中 / endpoint 缺失 / 两者相等（dev 本机）→ 原样返回，仍走 W12-3 retry 兜底。
    保留 query string（X-Amz-Signature 等）以兼容签名 URL。
    """
    pub = (settings.MINIO_PUBLIC_ENDPOINT or "").rstrip("/")
    internal = (settings.MINIO_ENDPOINT or "").rstrip("/")
    if not pub or not internal or pub == internal:
        return url
    if not url.startswith(pub + "/"):
        return url
    return internal + url[len(pub):]


# ----------------------------------------------------------------------
# Error classification + retry
# ----------------------------------------------------------------------


def classify_probe_error(exc: Exception) -> str:
    """W12-3 · 把 ffprobe 失败粗分桶（线上 dashboard 用），用于 engine_warning.detail.

    返回值（窄集合，便于 metrics 聚合）：
    - ``5xx``：MinIO/对象存储返回 5XX（最常见，应 retry）
    - ``4xx``：URL 鉴权过期 / 404（retry 无用）
    - ``timeout``：subprocess timeout
    - ``binary_missing``：ffprobe 二进制缺失（CI / 本地）
    - ``unknown``：兜底
    """
    err = repr(exc).lower()
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout"
    if "server returned 5" in err or "5xx" in err:
        return "5xx"
    if "server returned 4" in err or "403" in err or "404" in err or "expired" in err:
        return "4xx"
    if "ffprobe" in err and "not found" in err:
        return "binary_missing"
    return "unknown"


# 5XX / timeout 默认重试 2 次（共 3 次尝试），指数退避 0.5s / 1.5s.
# 4xx / binary_missing 等不会重试（retry 无用，浪费 wall time + 拖慢 pipeline）。
_PROBE_RETRY_REASONS = frozenset({"5xx", "timeout"})
_PROBE_MAX_ATTEMPTS = 3
_PROBE_BACKOFF_SECONDS = (0.5, 1.5)


@dataclass
class _ProbeRetryOutcome:
    """``_probe_with_retry`` 返回值；用 dataclass 避免 3 元 tuple 解构 noisy."""

    probe: object | None  # _ProbeInfoExtended 但避免循环 import
    attempts: int
    last_error_reason: str | None
    last_error: Exception | None = None


def _probe_with_retry(video_url: str) -> _ProbeRetryOutcome:
    """W12-3 · 包一层带退避 retry 的 ffprobe 调用.

    ffprobe 直接读 MinIO 预签名 URL 时，对象存储 5XX / 短暂网络抖动占据线上
    ``v2_probe_errors`` 大头；2 次重试足以把绝大多数恢复掉，且不会让 retry 4xx
    （URL 已过期）白费时间。
    """
    last_exc: Exception | None = None
    last_reason: str = "unknown"
    for attempt in range(1, _PROBE_MAX_ATTEMPTS + 1):
        try:
            probe = _ffprobe_extended(video_url)
            return _ProbeRetryOutcome(
                probe=probe, attempts=attempt, last_error_reason=None
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            last_reason = classify_probe_error(exc)
            if last_reason not in _PROBE_RETRY_REASONS or attempt == _PROBE_MAX_ATTEMPTS:
                break
            backoff = _PROBE_BACKOFF_SECONDS[
                min(attempt - 1, len(_PROBE_BACKOFF_SECONDS) - 1)
            ]
            metrics.incr("v2_probe_retries")
            log.info(
                "v2_probe_retry",
                extra={
                    "video_url": sanitize_probe_url(video_url),
                    "attempt": attempt,
                    "reason": last_reason,
                    "backoff": backoff,
                },
            )
            time.sleep(backoff)
    assert last_exc is not None  # 上面 break 一定走过 except 分支
    return _ProbeRetryOutcome(
        probe=None,
        attempts=_PROBE_MAX_ATTEMPTS,
        last_error_reason=last_reason,
        last_error=last_exc,
    )


# ----------------------------------------------------------------------
# Public entry · probe_video_warnings
# ----------------------------------------------------------------------


def probe_video_warnings(video_url: str) -> list[EngineWarning]:
    """P2-W8 ENG-C2 · 对原始 ``video_url`` 跑 ffprobe 探测，生成 engine_warnings.

    ffprobe 直接支持 HTTP / HTTPS URL（只读 header / 几 KB metadata，无需完整下载）。
    探测项：
    - ``decoded_hevc`` / ``decoded_vp9`` / ``decoded_h264``：codec_name
    - ``hdr_tonemapped``：color_transfer ∈ {smpte2084, arib-std-b67}
    - ``slowmo_detected`` + ``nominal_fps_used``：mov/mp4 tags 检出真实帧率
    - ``fps_upsampled`` / ``fps_downsampled``：raw fps ≠ TARGET_FPS_V2
    - ``audio_kept`` / ``audio_dropped``：原视频是否含音轨
    - ``probe_failed``（W12-3）：ffprobe 失败时返回带 reason+attempts 的 warning，
      不再静默返回 ``[]``，让客户端"调试浮层"（W10 已落地）能直接看到原因

    流程：
    1. W13-C `rewrite_to_internal_url`：MinIO 公网 URL → docker 内网 URL（绕 nginx 反代）
    2. W12-3 `_probe_with_retry`：5xx/timeout 指数退避 retry 2 次
    3. W12-3 分类后落分桶 metric `v2_probe_errors_{reason}`，便于 W13-D Prometheus 告警
    4. 失败时返 1 条 `probe_failed` warning；成功时返 0~N 条 codec/HDR/fps/audio warning

    **绝不阻塞主分析流程**——pipeline 主体仍走 V1，engine_warnings 仅为辅助。
    """
    if not video_url:
        return []

    metrics.incr("v2_probe_count")
    # W13-C：先把公网 URL 改成内网（去掉 nginx 反代这一跳），治根 5xx
    probe_url = rewrite_to_internal_url(video_url)
    if probe_url != video_url:
        log.debug(
            "v2_probe_url_rewritten_to_internal",
            extra={
                "public_path": sanitize_probe_url(video_url),
                "internal_path": sanitize_probe_url(probe_url),
            },
        )
    outcome = _probe_with_retry(probe_url)

    if outcome.probe is None:
        metrics.incr("v2_probe_errors")
        # 按错误类型再细分（5xx_after_retries vs 4xx 立即放弃）做 metric tag
        if outcome.last_error_reason in _PROBE_RETRY_REASONS:
            metrics.incr(f"v2_probe_errors_{outcome.last_error_reason}_after_retries")
        else:
            metrics.incr(f"v2_probe_errors_{outcome.last_error_reason}")
        log.warning(
            "v2_probe_failed",
            extra={
                "video_url": sanitize_probe_url(video_url),
                "attempts": outcome.attempts,
                "reason": outcome.last_error_reason,
                "err_type": type(outcome.last_error).__name__
                if outcome.last_error
                else None,
                "err": (repr(outcome.last_error)[:200] if outcome.last_error else None),
            },
        )
        return [
            EngineWarning(
                code="probe_failed",
                level="info",
                detail=(
                    f"ffprobe 探测失败 reason={outcome.last_error_reason} "
                    f"attempts={outcome.attempts}"
                ),
            )
        ]

    probe = outcome.probe

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
