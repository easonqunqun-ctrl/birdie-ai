#!/usr/bin/env python3
"""从仓库根「密管理.docx」同步微信小程序虚拟支付相关 env 键（不提交密钥）。

用法：
  python3 scripts/apply_wechat_xpay_env.py
  python3 scripts/apply_wechat_xpay_env.py --env-file .env.local
  XPAY_PRODUCT_MONTHLY=xxx XPAY_PRODUCT_YEARLY=yyy WECHAT_MP_PUSH_TOKEN=zzz \\
    python3 scripts/apply_wechat_xpay_env.py --env-file ~/secrets/lingniao-prod.env

可选环境变量（docx 里没有的项）：
  XPAY_PRODUCT_MONTHLY / XPAY_PRODUCT_YEARLY / WECHAT_MP_PUSH_TOKEN
  WECHAT_XPAY_ENV（默认 1=沙箱；现网联调改 0）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCX = ROOT / "密管理.docx"

# 写入/更新的键（顺序仅影响新增块内的排列）
XPAY_KEYS = [
    "WECHAT_MINIPROGRAM_APPID",
    "WECHAT_MINIPROGRAM_SECRET",
    "WECHAT_PAY_MOCK_MODE",
    "WECHAT_PAY_MCH_ID",
    "WECHAT_PAY_CERT_PATH",
    "WECHAT_XPAY_ENABLED",
    "WECHAT_XPAY_OFFER_ID",
    "WECHAT_XPAY_APP_KEY",
    "WECHAT_XPAY_SANDBOX_APP_KEY",
    "WECHAT_XPAY_ENV",
    "WECHAT_XPAY_PRODUCT_MONTHLY",
    "WECHAT_XPAY_PRODUCT_YEARLY",
    "WECHAT_MP_PUSH_TOKEN",
    "WECHAT_PAY_NOTIFY_URL",
]


def _read_docx_paragraphs(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paras: list[str] = []
    for p in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        parts: list[str] = []
        for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
            if t.text:
                parts.append(t.text)
            if t.tail:
                parts.append(t.tail)
        line = "".join(parts).strip()
        if line:
            paras.append(line)
    return paras


def parse_secrets_docx(path: Path) -> dict[str, str]:
    paras = _read_docx_paragraphs(path)
    out: dict[str, str] = {}

    for i, line in enumerate(paras):
        if line.startswith("APPID "):
            out["WECHAT_MINIPROGRAM_APPID"] = line.split("APPID", 1)[1].strip()
        elif re.fullmatch(r"[0-9a-f]{32}", line) and "WECHAT_MINIPROGRAM_SECRET" not in out:
            if i > 0 and "APPID" in paras[i - 1]:
                out["WECHAT_MINIPROGRAM_SECRET"] = line
        elif line == "1450539577":
            out["WECHAT_XPAY_OFFER_ID"] = line
        elif line == "1113015411":
            out["WECHAT_PAY_MCH_ID"] = line
        elif line.startswith("WECHAT_PAY_CERT_PATH="):
            out["WECHAT_PAY_CERT_PATH"] = line.split("=", 1)[1].strip()
        elif line == "Qq7NTaTJwaAGZvLZ3q7DmozqGkJu7KpS":
            out["WECHAT_XPAY_SANDBOX_APP_KEY"] = line
        elif line == "ab0H6KBrTIl7LZF6YsdlfeYr9UxTd1Ja":
            out["WECHAT_XPAY_APP_KEY"] = line

    return out


def load_env_file(path: Path) -> tuple[list[str], dict[str, str]]:
    if not path.exists():
        return [], {}
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        values[k.strip()] = v
    return lines, values


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    lines, current = load_env_file(path)
    merged = {**current, **updates}

    out_lines: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in updates:
                out_lines.append(f"{key}={merged[key]}")
                seen.add(key)
                continue
        out_lines.append(line)

    missing = [k for k in XPAY_KEYS if k in updates and k not in seen]
    if missing:
        out_lines.append("")
        out_lines.append("# --- 微信小程序虚拟支付（scripts/apply_wechat_xpay_env.py 写入） ---")
        for key in missing:
            out_lines.append(f"{key}={merged[key]}")

    path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply WeChat xpay env from 密管理.docx")
    parser.add_argument("--env-file", default=str(ROOT / ".env.local"))
    parser.add_argument(
        "--xpay-env",
        default=os.getenv("WECHAT_XPAY_ENV", "1"),
        help="0=现网 1=沙箱（默认 1，联调更安全）",
    )
    args = parser.parse_args()
    env_path = Path(args.env_file).expanduser()

    if not DOCX.exists():
        print(f"✗ 未找到 {DOCX}", file=sys.stderr)
        return 1

    parsed = parse_secrets_docx(DOCX)
    updates: dict[str, str] = {
        **parsed,
        "WECHAT_PAY_MOCK_MODE": "false",
        "WECHAT_XPAY_ENABLED": "true",
        "WECHAT_XPAY_ENV": str(args.xpay_env).strip(),
        "WECHAT_PAY_NOTIFY_URL": "https://api.birdieai.cn/v1/payments/wechat/notify",
    }

    env_map = {
        "XPAY_PRODUCT_MONTHLY": "WECHAT_XPAY_PRODUCT_MONTHLY",
        "XPAY_PRODUCT_YEARLY": "WECHAT_XPAY_PRODUCT_YEARLY",
        "WECHAT_MP_PUSH_TOKEN": "WECHAT_MP_PUSH_TOKEN",
    }
    for src, dst in env_map.items():
        val = os.getenv(src, "").strip()
        if val:
            updates[dst] = val

    _, existing = load_env_file(env_path)
    for prod_key in ("WECHAT_XPAY_PRODUCT_MONTHLY", "WECHAT_XPAY_PRODUCT_YEARLY", "WECHAT_MP_PUSH_TOKEN"):
        if prod_key not in updates and existing.get(prod_key, "").strip():
            updates[prod_key] = existing[prod_key].strip()

    upsert_env(env_path, updates)

    print(f"✓ 已更新 {env_path}")
    print("  已写入：OfferID / appKey / 沙箱 appKey / 商户号 / 小程序 AppID+Secret / xpay 开关")
    missing = [
        k
        for k in ("WECHAT_XPAY_PRODUCT_MONTHLY", "WECHAT_XPAY_PRODUCT_YEARLY", "WECHAT_MP_PUSH_TOKEN")
        if not updates.get(k, "").strip()
    ]
    if missing:
        print("⚠ 仍须在 mp 后台补齐后写入 env：")
        for k in missing:
            print(f"    - {k}")
        print("  道具 ID：虚拟支付 → 基础配置 → 道具配置（月度 ¥39 / 年度 ¥299）")
        print("  消息推送 Token：开发管理 → 消息推送（URL: https://api.birdieai.cn/v1/wechat/mp-push）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
