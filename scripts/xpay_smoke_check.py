#!/usr/bin/env python3
"""W19-B · xpay 体验版冒烟自检（环境 + mp-push 可达性）。

用法：
  python3 scripts/xpay_smoke_check.py
  python3 scripts/xpay_smoke_check.py --env-file infra/deploy/.env.local
  python3 scripts/xpay_smoke_check.py --api-base https://api.birdieai.cn/v1
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_WHEN_ENABLED = (
    "WECHAT_XPAY_OFFER_ID",
    "WECHAT_XPAY_APP_KEY",
    "WECHAT_XPAY_PRODUCT_MONTHLY",
    "WECHAT_XPAY_PRODUCT_YEARLY",
    "WECHAT_MP_PUSH_TOKEN",
    "WECHAT_APPID",
    "WECHAT_SECRET",
)

OPTIONAL_SANDBOX = ("WECHAT_XPAY_SANDBOX_APP_KEY",)


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def merge_env(file_vals: dict[str, str]) -> dict[str, str]:
    merged = dict(file_vals)
    for k, v in os.environ.items():
        if k.startswith("WECHAT_") or k in {"APP_ENV"}:
            merged.setdefault(k, v)
    return merged


def check_mp_push(api_base: str, token: str) -> tuple[bool, str]:
    ts = str(int(time.time()))
    nonce = "smoke1234"
    raw = "".join(sorted([token, ts, nonce]))
    sig = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    qs = urllib.parse.urlencode(
        {"signature": sig, "timestamp": ts, "nonce": nonce, "echostr": "xpay_smoke_ok"}
    )
    url = f"{api_base.rstrip('/')}/wechat/mp-push?{qs}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if resp.status == 200 and "xpay_smoke_ok" in body:
                return True, "mp-push GET 200 + echostr"
            return False, f"mp-push unexpected: HTTP {resp.status} body={body[:120]}"
    except urllib.error.HTTPError as e:
        return False, f"mp-push HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
    except urllib.error.URLError as e:
        return False, f"mp-push unreachable: {e.reason}"


def main() -> int:
    parser = argparse.ArgumentParser(description="xpay smoke self-check")
    parser.add_argument("--env-file", default="", help="Path to .env.local or prod env")
    parser.add_argument("--api-base", default="https://api.birdieai.cn/v1")
    args = parser.parse_args()

    env_path = Path(args.env_file) if args.env_file else ROOT / "infra" / "deploy" / ".env.local"
    vals = merge_env(load_env_file(env_path))

    enabled = vals.get("WECHAT_XPAY_ENABLED", "false").lower() in {"1", "true", "yes"}
    mock_pay = vals.get("WECHAT_PAY_MOCK_MODE", "true").lower() in {"1", "true", "yes"}

    print("=== W19-B xpay smoke check ===")
    print(f"env_file: {env_path} ({'found' if env_path.is_file() else 'missing'})")
    print(f"WECHAT_XPAY_ENABLED={vals.get('WECHAT_XPAY_ENABLED', '(unset)')}")
    print(f"WECHAT_PAY_MOCK_MODE={vals.get('WECHAT_PAY_MOCK_MODE', '(unset)')}")

    errors: list[str] = []
    warnings: list[str] = []

    if not enabled:
        warnings.append("WECHAT_XPAY_ENABLED 未开启 — 仅做字段预检，跳过 mp-push")
    if mock_pay and enabled:
        warnings.append("WECHAT_PAY_MOCK_MODE=true 与 xpay 同时开 — 生产应设 false")

    if enabled:
        for key in REQUIRED_WHEN_ENABLED:
            if not (vals.get(key) or "").strip():
                errors.append(f"缺少 {key}")
        env = (vals.get("WECHAT_XPAY_ENV") or "0").strip()
        if env == "1" and not (vals.get("WECHAT_XPAY_SANDBOX_APP_KEY") or "").strip():
            errors.append("沙箱 env=1 但 WECHAT_XPAY_SANDBOX_APP_KEY 为空")

    token = (vals.get("WECHAT_MP_PUSH_TOKEN") or "").strip()
    if enabled and token:
        ok, msg = check_mp_push(args.api_base, token)
        print(f"mp-push: {msg}")
        if not ok:
            errors.append(msg)
    elif enabled:
        errors.append("WECHAT_MP_PUSH_TOKEN 为空，无法验 mp-push")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")

    if errors:
        print("\n结果: FAIL — 见 docs/release-notes/w19-xpay-smoke-runbook.md")
        return 1
    print("\n结果: PASS（环境 + mp-push 自检通过；真机虚拟支付仍须体验版手工走单）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
