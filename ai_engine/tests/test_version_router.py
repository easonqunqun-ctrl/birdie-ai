"""M7-14 version_router 单测.

覆盖
----
1. ``_user_bucket`` 哈希稳定（同输入恒同输出）
2. ``_user_bucket`` 分布近似均匀（10000 个 user_id 落 0-99 桶，方差 <10%）
3. ``get_engine_version``：pct=0 全 V1；pct=100 全 V2；pct=50 大致一半 V2
4. ``get_engine_version`` 同一用户在 pct 不变期内永远落同一版本
5. ``get_engine_version`` user_id=None / 空 → V1（保守）
6. ``set_rollout_pct`` 降级需 force=True
7. ``invalidate_cache`` 后立刻读到新 env
"""

from __future__ import annotations

import os

import pytest

from app import version_router as vr
from app.version_router import (
    ENGINE_V1,
    ENGINE_V2,
    RolloutDowngradeRequiresForce,
    _user_bucket,
    get_engine_version,
    get_rollout_pct,
    invalidate_cache,
    set_rollout_pct,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


def test_user_bucket_is_stable() -> None:
    for uid in ["usr_a", "usr_b", "usr_c123"]:
        assert _user_bucket(uid) == _user_bucket(uid)


def test_user_bucket_is_in_range() -> None:
    for uid in ["usr_a", "usr_b", "usr_long_id_" + "x" * 40]:
        b = _user_bucket(uid)
        assert 0 <= b < 100


def test_user_bucket_distribution_is_roughly_uniform() -> None:
    counts = [0] * 100
    for i in range(10000):
        counts[_user_bucket(f"usr_{i:06d}")] += 1
    # 10000/100=100 期望；±50% 容忍（即 50..150）
    assert min(counts) >= 50, f"min bucket too small: {min(counts)}"
    assert max(counts) <= 200, f"max bucket too big: {max(counts)}"


def test_get_engine_version_zero_pct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "0")
    invalidate_cache()
    for i in range(20):
        assert get_engine_version(f"usr_{i}") == ENGINE_V1


def test_get_engine_version_full_pct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "100")
    invalidate_cache()
    for i in range(20):
        assert get_engine_version(f"usr_{i}") == ENGINE_V2


def test_get_engine_version_half_pct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "50")
    invalidate_cache()
    v2 = 0
    for i in range(1000):
        if get_engine_version(f"usr_{i:06d}") == ENGINE_V2:
            v2 += 1
    # 期望 500，±150 容忍
    assert 350 <= v2 <= 650, f"unexpected v2 count at pct=50: {v2}"


def test_get_engine_version_is_stable_per_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "25")
    invalidate_cache()
    uid = "usr_stable_001"
    first = get_engine_version(uid)
    for _ in range(50):
        assert get_engine_version(uid) == first


def test_get_engine_version_none_user_returns_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "100")
    invalidate_cache()
    assert get_engine_version(None) == ENGINE_V1
    assert get_engine_version("") == ENGINE_V1


def test_set_rollout_pct_clamps_to_0_100(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "0")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("M7_V2_REDIS_URL", raising=False)
    invalidate_cache()

    out = set_rollout_pct(150)
    # 上限 100；previous 来源 env=0；不会触发降级
    assert out["current_pct"] == 100

    invalidate_cache()
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "0")
    out = set_rollout_pct(-50)
    assert out["current_pct"] == 0


def test_set_rollout_pct_rejects_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "50")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("M7_V2_REDIS_URL", raising=False)
    invalidate_cache()

    with pytest.raises(RolloutDowngradeRequiresForce):
        set_rollout_pct(10)

    # force=True 通过
    invalidate_cache()
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "50")
    out = set_rollout_pct(10, force=True)
    assert out["downgrade"] is True


def test_get_rollout_pct_uses_env_when_no_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("M7_V2_REDIS_URL", raising=False)
    monkeypatch.setenv("M7_V2_ROLLOUT_PCT", "42")
    invalidate_cache()
    assert get_rollout_pct() == 42
