"""W6 ENG-A1 · metrics 计数器单测."""

from __future__ import annotations

import threading

import pytest

from app import metrics


@pytest.fixture(autouse=True)
def _reset_metrics():
    """每个用例前后都清零，防止用例互相污染."""
    metrics.reset()
    yield
    metrics.reset()


def test_incr_known_key_accumulates():
    metrics.incr("v1_count")
    metrics.incr("v1_count", by=3)
    snap = metrics.snapshot()
    assert snap["v1_count"] == 4


def test_incr_unknown_key_silently_ignored():
    """typo 不应该把整个引擎 KeyError 崩了."""
    metrics.incr("v3_count")  # 不存在
    metrics.incr("v1_count")
    assert metrics.snapshot()["v1_count"] == 1


def test_record_latency_accumulates_for_known_engine():
    metrics.record_latency("v1", 100.0)
    metrics.record_latency("v1", 200.0)
    metrics.incr("v1_count", by=2)
    snap = metrics.snapshot()
    # avg = (100 + 200) / 2 = 150
    assert snap["v1_avg_latency_ms"] == pytest.approx(150.0)


def test_record_latency_unknown_engine_ignored():
    metrics.record_latency("vX", 9999.0)
    metrics.incr("v1_count")
    assert metrics.snapshot()["v1_avg_latency_ms"] == 0.0


def test_snapshot_zero_counts_no_div_by_zero():
    snap = metrics.snapshot()
    assert snap["v1_count"] == 0
    assert snap["v2_count"] == 0
    assert snap["v1_error_rate"] == 0.0
    assert snap["v2_error_rate"] == 0.0
    assert snap["v1_avg_latency_ms"] == 0.0
    assert snap["v2_avg_latency_ms"] == 0.0
    assert snap["v2_traffic_ratio"] == 0.0


def test_error_rate_and_traffic_ratio_correct():
    # 模拟：V1 100 次成功 + V2 10 次（其中 1 次失败），总流量比 V2 ~9%
    for _ in range(100):
        metrics.incr("v1_count")
    for _ in range(10):
        metrics.incr("v2_count")
    metrics.incr("v2_errors")

    snap = metrics.snapshot()
    assert snap["v2_traffic_ratio"] == pytest.approx(10 / 110, rel=1e-3)
    assert snap["v2_error_rate"] == pytest.approx(0.1, rel=1e-3)
    assert snap["v1_error_rate"] == 0.0


def test_concurrent_incr_race_safe():
    """50 个线程各 incr 100 次，期望最终值精确 = 5000（验证 Lock 生效）."""
    n_threads = 50
    per_thread = 100

    def worker():
        for _ in range(per_thread):
            metrics.incr("v2_count")

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert metrics.snapshot()["v2_count"] == n_threads * per_thread


def test_v2_fallback_count_tracked():
    metrics.incr("v2_fallback_count")
    metrics.incr("v2_fallback_count")
    assert metrics.snapshot()["v2_fallback_count"] == 2


def test_uptime_is_positive_float():
    snap = metrics.snapshot()
    # 进程已运行至少一瞬，uptime 应严格 >0
    assert isinstance(snap["uptime_s"], float)
    assert snap["uptime_s"] >= 0.0
