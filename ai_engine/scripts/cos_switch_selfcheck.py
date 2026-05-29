#!/usr/bin/env python3
"""W18+ · 切对象存储（COS / OSS / KODO）前的 URL 改写自检（CLI）。

定位
----
对应 ``docs/release-notes/wait-for-triggers-checklist.md`` §2.10。从 MinIO 切到腾讯云
COS / 阿里云 OSS / 七牛 KODO 时，运维只需在 ``.env.local`` 配
``EXTRA_INTERNAL_URL_REWRITES``，**不改代码**（rewrite 逻辑已泛化，单测覆盖）。

但单测验的是**代码**，验不了运维实际填进 env 的那行字符串——typo（少写 ``=``、
两端写反、忘去 ``https://``、漏掉某个新 bucket 域名）会让公网 URL **悄悄不被改写**，
ffprobe 退回绕公网回环，重现 W13-C 的 5xx。本脚本就是**部署前的最后一道离线门禁**：

1. 打印当前生效的改写对（MinIO 历史那对 + ``EXTRA_INTERNAL_URL_REWRITES`` 解析出的）
2. 把 env 里**被静默跳过的非法 chunk**显式报出来（probe 运行时只 warning log，易漏）
3. 对一个示例公网对象 URL 做 **dry-run 改写**（纯本地，不发任何网络请求）：
   - 命中 → 给出改写后的内网 URL
   - 未命中 → 警告"切 COS 后该 URL 仍走公网，5xx 风险"
4. ``--expect-internal`` / ``--require-match`` 提供时做断言，失败 **退出码 1**，
   可直接挂进 ``infra/deploy`` 发布前自检（与 ``make deploy-check-*`` 同思路）

纯逻辑（``parse_extra_rewrites`` / ``match_pair``）可单测，见 ``tests/test_cos_switch_selfcheck.py``；
实际改写结果委托 ``app/integrations/probe.py``（rewrite 的唯一真源），避免逻辑漂移。

用法
----
    # 用当前 .env.local 配置，校验一条 COS 示例 URL 会被改写到内网
    python scripts/cos_switch_selfcheck.py \\
        --url 'https://cos.ap-guangzhou.myqcloud.com/birdie/uploads/x.mp4' \\
        --expect-internal 'http://internal-cos:443'

    # what-if：不动真实 env，临时试一行候选配置
    python scripts/cos_switch_selfcheck.py \\
        --rewrites 'https://cos.ap-guangzhou.myqcloud.com=http://internal-cos:443' \\
        --url 'https://cos.ap-guangzhou.myqcloud.com/birdie/uploads/x.mp4' \\
        --require-match
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ----------------------------------------------------------------------
# 纯逻辑（可单测）—— 语义与 app.integrations.probe._iter_rewrite_pairs 一致
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedExtra:
    """``EXTRA_INTERNAL_URL_REWRITES`` 解析结果。"""

    valid: list[tuple[str, str]] = field(default_factory=list)
    # 每项 (原始 chunk, 跳过原因)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def parse_extra_rewrites(extra_raw: str | None) -> ParsedExtra:
    """把 ``EXTRA_INTERNAL_URL_REWRITES`` 解析成合法对 + 被跳过的 chunk（带原因）。

    解析规则与 ``probe._iter_rewrite_pairs`` 完全一致（分号分隔、首个 ``=`` 切分、
    两端 ``rstrip('/')``）；区别只在于：本函数把被跳过的 chunk 连同原因收集出来，
    供运维肉眼核对（probe 运行时只打 warning log，部署现场容易漏看）。
    """
    valid: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    for raw_chunk in (extra_raw or "").split(";"):
        chunk = raw_chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            skipped.append((chunk, "缺少 '='（格式应为 <public>=<internal>）"))
            continue
        pub, internal = chunk.split("=", 1)
        pub = pub.strip().rstrip("/")
        internal = internal.strip().rstrip("/")
        if not pub or not internal:
            skipped.append((chunk, "公网端或内网端为空"))
            continue
        if pub == internal:
            skipped.append((chunk, "两端相等（无意义改写）"))
            continue
        valid.append((pub, internal))
    return ParsedExtra(valid=valid, skipped=skipped)


def match_pair(url: str, pairs: list[tuple[str, str]]) -> tuple[str, str] | None:
    """返回 url 命中的第一个 ``(public, internal)`` 对；都不命中 → None。

    匹配规则镜像 ``probe.rewrite_to_internal_url``：``url.startswith(public + '/')``，
    按 pairs 声明顺序首个命中即返回。
    """
    for pub, internal in pairs:
        if url.startswith(pub + "/"):
            return (pub, internal)
    return None


# ----------------------------------------------------------------------
# 报告渲染
# ----------------------------------------------------------------------


def render_report(
    *,
    active_pairs: list[tuple[str, str]],
    skipped: list[tuple[str, str]],
    url: str | None,
    rewritten: str | None,
    matched: tuple[str, str] | None,
    expect_internal: str | None,
    ok: bool,
) -> str:
    lines: list[str] = ["# COS 切换自检报告", ""]

    lines.append("## 1. 当前生效的改写对（按命中优先级）")
    lines.append("")
    if active_pairs:
        lines.append("| # | 公网前缀 (public) | 内网目标 (internal) |")
        lines.append("|---|---|---|")
        for idx, (pub, internal) in enumerate(active_pairs, 1):
            lines.append(f"| {idx} | `{pub}` | `{internal}` |")
    else:
        lines.append("> ⚠️ 一个改写对都没有：所有 URL 都会原样走公网（切 COS 后必现 5xx）。")
    lines.append("")

    if skipped:
        lines.append("## 2. 被静默跳过的非法配置（请修正）")
        lines.append("")
        lines.append("| 原始 chunk | 跳过原因 |")
        lines.append("|---|---|")
        for chunk, reason in skipped:
            lines.append(f"| `{chunk}` | {reason} |")
        lines.append("")

    if url:
        lines.append("## 3. dry-run 改写")
        lines.append("")
        lines.append(f"- 输入：`{url}`")
        if matched:
            lines.append(f"- ✅ 命中：`{matched[0]}` → `{matched[1]}`")
            lines.append(f"- 改写后：`{rewritten}`")
        else:
            lines.append("- ❌ 未命中任何改写对：该 URL 切 COS 后仍走公网回环（5xx 风险）。")
        if expect_internal:
            hit = bool(rewritten and rewritten.startswith(expect_internal))
            lines.append(
                f"- 期望内网前缀 `{expect_internal}`：{'✅' if hit else '❌'}"
            )
        lines.append("")

    lines.append("## 4. 结论")
    lines.append("")
    lines.append(f"- {'✅ 自检通过' if ok else '❌ 自检未通过（见上）'}")
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W18+ 切对象存储前的 URL 改写自检（离线，无网络请求）。"
    )
    parser.add_argument("--url", help="示例公网对象 URL，做 dry-run 改写校验")
    parser.add_argument(
        "--expect-internal", help="期望改写后命中的内网前缀；不符 → 退出码 1"
    )
    parser.add_argument(
        "--require-match",
        action="store_true",
        help="要求 --url 必须命中某改写对，否则退出码 1",
    )
    parser.add_argument(
        "--rewrites",
        help="what-if：覆盖 EXTRA_INTERNAL_URL_REWRITES（仅本进程内，不改真实 env）",
    )
    parser.add_argument(
        "--strict-config",
        action="store_true",
        help="存在被跳过的非法 chunk 时退出码 1",
    )
    parser.add_argument(
        "--report-md", help="把报告写到该路径（同时仍打印到 stdout）"
    )
    args = parser.parse_args(argv)

    from app.config import settings
    from app.integrations import probe

    if args.rewrites is not None:
        settings.EXTRA_INTERNAL_URL_REWRITES = args.rewrites

    active_pairs = probe._iter_rewrite_pairs()
    parsed = parse_extra_rewrites(getattr(settings, "EXTRA_INTERNAL_URL_REWRITES", ""))
    skipped = parsed.skipped

    rewritten: str | None = None
    matched: tuple[str, str] | None = None
    ok = True

    if args.url:
        rewritten = probe.rewrite_to_internal_url(args.url)
        matched = match_pair(args.url, active_pairs)
        if args.require_match and matched is None:
            ok = False
        if args.expect_internal and not (
            rewritten and rewritten.startswith(args.expect_internal)
        ):
            ok = False

    if args.strict_config and skipped:
        ok = False

    report = render_report(
        active_pairs=active_pairs,
        skipped=skipped,
        url=args.url,
        rewritten=rewritten,
        matched=matched,
        expect_internal=args.expect_internal,
        ok=ok,
    )
    print(report)
    if args.report_md:
        out = Path(args.report_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"[cos-selfcheck] 报告已写入 {out}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
