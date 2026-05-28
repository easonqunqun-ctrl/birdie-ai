"""P2-W6 ENG-A1 · ai_engine 进程级 metrics 计数器。

设计目的
--------
W5 V2 灰度上线后，需要最小可观测能力支撑「灰度从 5% 推到 50%/100%」的决策：
- 看 V1/V2 实际命中数，验证 rollout pct 真的在按比例分流；
- 看 V2 错误率 / fallback 次数，判断是否到了回滚或前进的阈值；
- 看每路平均耗时，看 V2 是否引入性能回归。

为什么不直接上 prometheus_client
--------------------------------
- ai_engine 当前部署是 **uvicorn 单 worker**（Dockerfile `CMD` 不带 `--workers`），
  进程内共享 dict + Lock 就够 race-safe；
- 多进程 / Prometheus pull 模型留给 W7+，看监控基建是否真的拉起来再说；
- 现阶段先求「能用 1 个 curl 看清数」，避免引入 prometheus_client + 多进程目录的复杂度。

数据正确性
----------
- 所有写都走 ``_LOCK``；
- 读用 ``snapshot()`` 拷贝出去再算派生指标，避免读到中间态。
"""

from __future__ import annotations

import threading
import time

# 计数器键集中声明，避免拼写 typo 导致默写空指标
_COUNTER_KEYS = (
    "v1_count",
    "v2_count",
    "v1_errors",
    "v2_errors",
    "v2_fallback_count",  # V2 资源加载失败回落到 V1 的次数
    # P2-W9+ ENG-C2: V2 probe（ffprobe 原始 URL）调用次数与失败次数
    # 用于回答「ffprobe 是否在真流量下被普遍跑通 / 失败原因是什么」
    "v2_probe_count",
    "v2_probe_errors",
    # P2-W9+ ENG-D: V2 enrichment fallback——YAML / locale / pose 缺失导致退化路径次数
    # 与 v2_fallback_count 区别：v2_fallback_count = 整 V2 资源加载失败回落 V1；
    # v2_enrich_fallback_count = enrichment hook 内部 issue 找不到 YAML rule 走 mean_vis 兜底
    "v2_enrich_fallback_count",
)
_LATENCY_KEYS = ("v1_latency_ms_total", "v2_latency_ms_total")

_LOCK = threading.Lock()
_COUNTERS: dict[str, int] = {k: 0 for k in _COUNTER_KEYS}
_LATENCIES: dict[str, float] = {k: 0.0 for k in _LATENCY_KEYS}
_START_TIME = time.time()


def incr(key: str, by: int = 1) -> None:
    """计数器自增；未知 key 直接静默忽略（避免上游一次 typo 把整个引擎崩了）."""
    if key not in _COUNTERS:
        return
    with _LOCK:
        _COUNTERS[key] += by


def record_latency(engine_version: str, latency_ms: float) -> None:
    """记录一次 analyze 的耗时；仅在 status=success 时调用更有意义."""
    key = f"{engine_version}_latency_ms_total"
    if key not in _LATENCIES:
        return
    with _LOCK:
        _LATENCIES[key] += max(0.0, latency_ms)


def snapshot() -> dict[str, float | int | str]:
    """快照当前所有指标 + 派生指标。

    返回字段（key/含义）：
    - ``uptime_s``：进程启动至今秒数
    - ``v1_count`` / ``v2_count``：成功 + 失败均计入（区别仅看 errors）
    - ``v1_errors`` / ``v2_errors``：``status=failed`` 或捕获 PipelineError
    - ``v2_fallback_count``：YAML / locale 加载失败被迫走 V1 的次数
    - ``v2_probe_count`` / ``v2_probe_errors``：V2 入口 ffprobe 原始 URL 调用次数 / 失败次数
    - ``v2_enrich_fallback_count``：``_enrich_v2`` 内 issue 找不到 YAML rule 走 mean_vis 兜底次数
    - ``v1_error_rate`` / ``v2_error_rate``：errors / count（计数为 0 时返回 0.0）
    - ``v2_probe_error_rate``：probe_errors / probe_count
    - ``v1_avg_latency_ms`` / ``v2_avg_latency_ms``：成功请求平均耗时
    - ``v2_traffic_ratio``：v2_count / (v1_count + v2_count)，与 rollout pct 对照
    """
    with _LOCK:
        counters = dict(_COUNTERS)
        latencies = dict(_LATENCIES)
    uptime = time.time() - _START_TIME

    v1 = counters["v1_count"]
    v2 = counters["v2_count"]
    total = v1 + v2

    def _rate(num: int, den: int) -> float:
        return round(num / den, 4) if den > 0 else 0.0

    return {
        "uptime_s": round(uptime, 1),
        **counters,
        "v1_error_rate": _rate(counters["v1_errors"], v1),
        "v2_error_rate": _rate(counters["v2_errors"], v2),
        "v2_probe_error_rate": _rate(
            counters["v2_probe_errors"], counters["v2_probe_count"]
        ),
        "v1_avg_latency_ms": round(latencies["v1_latency_ms_total"] / v1, 1)
        if v1 > 0
        else 0.0,
        "v2_avg_latency_ms": round(latencies["v2_latency_ms_total"] / v2, 1)
        if v2 > 0
        else 0.0,
        "v2_traffic_ratio": _rate(v2, total),
    }


def reset() -> None:
    """单测用：清空所有计数器和耗时累计；不重置 uptime（避免单测之间互扰）."""
    with _LOCK:
        for k in _COUNTERS:
            _COUNTERS[k] = 0
        for k in _LATENCIES:
            _LATENCIES[k] = 0.0


__all__ = ["incr", "record_latency", "reset", "snapshot"]
