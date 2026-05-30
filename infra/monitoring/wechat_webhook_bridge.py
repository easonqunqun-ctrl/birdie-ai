#!/usr/bin/env python3
"""Alertmanager → 企微 / PushPlus 告警桥接（W19-C）。

Alertmanager webhook payload 与企微机器人格式不兼容；本服务转成可读消息后转发。
优先企微群机器人；无企微时可配 PushPlus，用个人微信扫码即可收告警。

环境变量
--------
WECOM_WEBHOOK_KEY    企微群机器人 key（可选）
PUSHPLUS_TOKEN       PushPlus 用户 token（可选，https://www.pushplus.plus）
ALERT_NOTIFY_TITLE   消息标题，默认「领翼golf 监控告警」
WECOM_WEBHOOK_PORT   监听端口，默认 9095
"""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("wechat_webhook_bridge")

PORT = int(os.environ.get("WECOM_WEBHOOK_PORT", "9095"))
WEBHOOK_KEY = (os.environ.get("WECOM_WEBHOOK_KEY") or "").strip()
PUSHPLUS_TOKEN = (os.environ.get("PUSHPLUS_TOKEN") or "").strip()
ALERT_TITLE = (os.environ.get("ALERT_NOTIFY_TITLE") or "领翼golf 监控告警").strip()


def _format_alert(payload: dict) -> str:
    status = payload.get("status", "unknown")
    alerts = payload.get("alerts") or []
    lines = [f"**Alertmanager · {status.upper()}**", ""]
    if not alerts:
        lines.append("_（无 alerts 明细）_")
        return "\n".join(lines)

    for i, alert in enumerate(alerts[:8], start=1):
        labels = alert.get("labels") or {}
        annotations = alert.get("annotations") or {}
        name = labels.get("alertname", "unknown")
        severity = labels.get("severity", "-")
        service = labels.get("service", "-")
        summary = annotations.get("summary") or annotations.get("description") or ""
        lines.append(f"{i}. **{name}** `[{severity}]` `{service}`")
        if summary:
            lines.append(f"   {summary[:200]}")
    if len(alerts) > 8:
        lines.append(f"\n… 另有 {len(alerts) - 8} 条")
    return "\n".join(lines)


def _plain_text(content: str) -> str:
    return content.replace("**", "").replace("_", "")


def _post_json(url: str, payload: dict) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, raw[:500]
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500]
    except URLError as e:
        return 502, str(e)


def _post_to_wecom(content: str) -> tuple[int, str]:
    if not WEBHOOK_KEY:
        return 0, "skip"

    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={WEBHOOK_KEY}"
    body = {"msgtype": "markdown", "markdown": {"content": content}}
    code, raw = _post_json(url, body)
    if code >= 400:
        return code, raw
    data = json.loads(raw) if raw else {}
    if data.get("errcode") == 0:
        return 200, "ok"
    return 502, raw


def _post_to_pushplus(content: str) -> tuple[int, str]:
    if not PUSHPLUS_TOKEN:
        return 0, "skip"

    code, raw = _post_json(
        "https://www.pushplus.plus/send",
        {
            "token": PUSHPLUS_TOKEN,
            "title": ALERT_TITLE,
            "content": _plain_text(content),
            "template": "txt",
            "channel": "wechat",
        },
    )
    if code >= 400:
        return code, raw
    data = json.loads(raw) if raw else {}
    if data.get("code") == 200:
        return 200, "ok"
    return 502, raw


def _forward_alert(content: str) -> tuple[int, str]:
    if not WEBHOOK_KEY and not PUSHPLUS_TOKEN:
        log.warning("WECOM_WEBHOOK_KEY and PUSHPLUS_TOKEN both empty; dry-run only")
        log.info("dry-run content:\n%s", content)
        return 200, "dry-run"

    results: list[tuple[str, int, str]] = []
    for name, fn in (("wecom", _post_to_wecom), ("pushplus", _post_to_pushplus)):
        code, detail = fn(content)
        if code == 0:
            continue
        results.append((name, code, detail))
        if code < 400:
            log.info("%s forward ok", name)
        else:
            log.warning("%s forward failed: %s", name, detail)

    if any(code < 400 for _, code, _ in results):
        return 200, "ok"
    if results:
        return 502, "; ".join(f"{name}:{detail}" for name, _, detail in results)
    return 200, "dry-run"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: ARG002
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("", "/health", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") not in ("/alert", "/"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8") if raw else "{}")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        content = _format_alert(payload)
        code, detail = _forward_alert(content)
        log.info(
            "alert forwarded status=%s alerts=%s result=%s",
            payload.get("status"),
            len(payload.get("alerts") or []),
            code,
        )

        self.send_response(200 if code < 400 else 502)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"code": code, "detail": detail}).encode("utf-8"))


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info(
        "listening on :%s wecom=%s pushplus=%s",
        PORT,
        bool(WEBHOOK_KEY),
        bool(PUSHPLUS_TOKEN),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown")
        sys.exit(0)


if __name__ == "__main__":
    main()
