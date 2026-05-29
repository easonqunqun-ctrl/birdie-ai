"""W18+ · COS 切换自检脚本单测（scripts/cos_switch_selfcheck.py）。

纯逻辑（parse_extra_rewrites / match_pair / render_report）直接测；main() 走
``--rewrites`` what-if 注入，并把 MinIO endpoint 置空保证只有注入的对生效（确定性）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cos_switch_selfcheck.py"
_spec = importlib.util.spec_from_file_location("cos_switch_selfcheck", _SCRIPT)
assert _spec and _spec.loader
cos = importlib.util.module_from_spec(_spec)
# 必须先登记到 sys.modules，否则模块内 @dataclass（配 from __future__ annotations）
# 解析自身模块字典时拿到 None 报 AttributeError。
sys.modules[_spec.name] = cos
_spec.loader.exec_module(cos)


# ---------------- parse_extra_rewrites ----------------


def test_parse_valid_single_pair():
    parsed = cos.parse_extra_rewrites(
        "https://cos.example.com=http://internal-cos:443"
    )
    assert parsed.valid == [("https://cos.example.com", "http://internal-cos:443")]
    assert parsed.skipped == []


def test_parse_strips_trailing_slash():
    parsed = cos.parse_extra_rewrites(
        "https://cos.example.com/=http://internal-cos:443/"
    )
    assert parsed.valid == [("https://cos.example.com", "http://internal-cos:443")]


def test_parse_multi_pairs_in_order():
    parsed = cos.parse_extra_rewrites(
        "https://cos.example.com=http://internal-cos:443;"
        "https://oss.example.cn=http://internal-oss:443"
    )
    assert parsed.valid == [
        ("https://cos.example.com", "http://internal-cos:443"),
        ("https://oss.example.cn", "http://internal-oss:443"),
    ]


def test_parse_skips_malformed_with_reasons():
    parsed = cos.parse_extra_rewrites(
        "no-equals-sign;"  # 缺 =
        "=http://internal:443;"  # 公网端空
        "https://x.com=;"  # 内网端空
        "https://same.com=https://same.com;"  # 两端相等
        "https://ok.com=http://internal-ok:443"  # 唯一合法
    )
    assert parsed.valid == [("https://ok.com", "http://internal-ok:443")]
    reasons = {chunk: reason for chunk, reason in parsed.skipped}
    assert "no-equals-sign" in reasons
    assert any("空" in r for r in reasons.values())
    assert any("相等" in r for r in reasons.values())


def test_parse_empty_string_is_noop():
    parsed = cos.parse_extra_rewrites("")
    assert parsed.valid == []
    assert parsed.skipped == []
    assert cos.parse_extra_rewrites(None).valid == []


# ---------------- match_pair ----------------


def test_match_pair_first_match_wins():
    pairs = [
        ("https://cos.example.com", "http://internal-cos:443"),
        ("https://oss.example.cn", "http://internal-oss:443"),
    ]
    assert cos.match_pair("https://oss.example.cn/b/x.mp4", pairs) == (
        "https://oss.example.cn",
        "http://internal-oss:443",
    )


def test_match_pair_no_match_returns_none():
    pairs = [("https://cos.example.com", "http://internal-cos:443")]
    assert cos.match_pair("https://kodo.example.io/x.mp4", pairs) is None


def test_match_pair_requires_slash_boundary():
    """前缀必须以 '/' 收边，避免 cos.example.com 误命中 cos.example.com.evil。"""
    pairs = [("https://cos.example.com", "http://internal-cos:443")]
    assert cos.match_pair("https://cos.example.com.evil/x.mp4", pairs) is None


# ---------------- render_report ----------------


def test_render_report_smoke():
    md = cos.render_report(
        active_pairs=[("https://cos.example.com", "http://internal-cos:443")],
        skipped=[("bad-chunk", "缺少 '='")],
        url="https://cos.example.com/x.mp4",
        rewritten="http://internal-cos:443/x.mp4",
        matched=("https://cos.example.com", "http://internal-cos:443"),
        expect_internal="http://internal-cos:443",
        ok=True,
    )
    assert "COS 切换自检报告" in md
    assert "internal-cos" in md
    assert "bad-chunk" in md
    assert "✅ 自检通过" in md


# ---------------- main() 集成 ----------------


@pytest.fixture
def _minio_empty(monkeypatch):
    """把 MinIO endpoint 置空，main() 里只剩 --rewrites 注入的对（确定性）。"""
    from app import config

    monkeypatch.setattr(config.settings, "MINIO_PUBLIC_ENDPOINT", "", raising=False)
    monkeypatch.setattr(config.settings, "MINIO_ENDPOINT", "", raising=False)
    monkeypatch.setattr(config.settings, "EXTRA_INTERNAL_URL_REWRITES", "", raising=False)


def test_main_pass_with_expect_internal(_minio_empty, capsys):
    rc = cos.main(
        [
            "--rewrites",
            "https://cos.example.com=http://internal-cos:443",
            "--url",
            "https://cos.example.com/birdie/x.mp4",
            "--expect-internal",
            "http://internal-cos:443",
            "--require-match",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "http://internal-cos:443/birdie/x.mp4" in out


def test_main_fail_on_expect_mismatch(_minio_empty):
    rc = cos.main(
        [
            "--rewrites",
            "https://cos.example.com=http://internal-cos:443",
            "--url",
            "https://cos.example.com/x.mp4",
            "--expect-internal",
            "http://WRONG:443",
        ]
    )
    assert rc == 1


def test_main_fail_on_require_match_miss(_minio_empty):
    rc = cos.main(
        [
            "--rewrites",
            "https://cos.example.com=http://internal-cos:443",
            "--url",
            "https://kodo.example.io/x.mp4",  # 不命中
            "--require-match",
        ]
    )
    assert rc == 1


def test_main_strict_config_fails_on_malformed(_minio_empty):
    rc = cos.main(
        [
            "--rewrites",
            "this-has-no-equals",
            "--strict-config",
        ]
    )
    assert rc == 1


def test_main_ok_when_no_url_and_clean_config(_minio_empty):
    rc = cos.main(
        ["--rewrites", "https://cos.example.com=http://internal-cos:443"]
    )
    assert rc == 0
