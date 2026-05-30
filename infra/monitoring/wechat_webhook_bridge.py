#!/usr/bin/env python3
"""Alertmanager → 企业微信群机器人 webhook 桥接（W19-C）。

Alertmanager 默认 webhook payload 与企业微信机器人格式不兼容；
本服务接收 Alertmanager POST，转成 markdown 消息转发到企微。

环境变量
--------
WECOM_WEBHOOK_KEY   企微群机器人 key（必填才真发；空则 dry-run 打日志）
WECOM_WEBHOOK_PORT  监听端口，默认 9095
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


def _post_to_wecom(content: str) -> tuple[int, str]:
    if not WEBHOOK_KEY:
        log.warning("WECOM_WEBHOOK_KEY empty; dry-run only")
        return 200, "dry-run"

    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={WEBHOOK_KEY}"
    body = json.dumps({"msgtype": "markdown", "markdown": {"content": content}}).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            if data.get("errcode") == 0:
                return 200, "ok"
            return 502, raw[:500]
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500]
    except URLError as e:
        return 502, str(e)


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
        code, detail = _post_to_wecom(content)
        log.info("alert forwarded status=%s alerts=%s wecom=%s", payload.get("status"), len(payload.get("alerts") or []), code)
        if code >= 400:
            log.warning("wecom forward failed: %s", detail)

        self.send_response(200 if code < 400 else 502)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"code": code, "detail": detail}).encode("utf-8"))


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info("listening on :%s key_configured=%s", PORT, bool(WEBHOOK_KEY))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutdown")
        sys.exit(0)


if __name__ == "__main__":
    main()
