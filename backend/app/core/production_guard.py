"""生产环境启动门禁：挡住「进程能起来但链路全断」的常见占位配置."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from app.config import Settings
from app.integrations.llm import _is_placeholder_key


def _hostname(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None
    return urlparse(url).hostname


def _has_legacy_angle_bracket_placeholder(raw: str) -> bool:
    """检出历史上 `.env.test` 等模板里的 `<change-me-*>` / `<your-*>` 误粘贴。"""
    if not raw or "<" not in raw:
        return False
    low = raw.lower()
    return any(
        frag in low
        for frag in (
            "<change-me",
            "<your-wx",
            "<your-deepseek",
            "<placeholder",
            "<replace",
        )
    )


def audit_wechat_pay_real_mode(settings: Settings) -> list[str]:
    """``WECHAT_PAY_MOCK_MODE=false`` 时微信支付 APIv3 必填项。

    staging / prod 在进程启动阶段强制执行，避免「容器起来了但下单立刻 502」。
    """
    errors: list[str] = []
    if settings.WECHAT_PAY_MOCK_MODE:
        return errors

    if not (settings.WECHAT_PAY_MCH_ID or "").strip():
        errors.append("WECHAT_PAY_MCH_ID 为空（微信支付商户号）")

    if not (settings.WECHAT_PAY_MCH_SERIAL or "").strip():
        errors.append("WECHAT_PAY_MCH_SERIAL 为空（商户平台「API 安全」证书序列号）")

    apiv3 = (
        settings.WECHAT_PAY_API_V3_KEY or settings.WECHAT_PAY_API_KEY or ""
    ).strip()
    if len(apiv3) != 32:
        errors.append(
            "WECHAT_PAY_API_V3_KEY（或 WECHAT_PAY_API_KEY）须为 32 位，"
            "与商户平台「API 安全 → APIv3 密钥」一致",
        )

    notify = (settings.WECHAT_PAY_NOTIFY_URL or "").strip()
    if not notify:
        errors.append(
            "WECHAT_PAY_NOTIFY_URL 为空（须 HTTPS 公网可访问，"
            "例如 https://api.example.com/v1/payments/wechat/notify）",
        )
    elif not notify.lower().startswith("https://"):
        errors.append("WECHAT_PAY_NOTIFY_URL 须为 https://")
    elif "localhost" in notify.lower() or "127.0.0.1" in notify:
        errors.append("WECHAT_PAY_NOTIFY_URL 不可为 localhost（微信服务器无法回调）")

    pem_inline = (getattr(settings, "WECHAT_PAY_PRIVATE_KEY_PEM", None) or "").strip()
    cert_path = (settings.WECHAT_PAY_CERT_PATH or "").strip()
    if pem_inline:
        if "BEGIN" not in pem_inline or "PRIVATE KEY" not in pem_inline:
            errors.append(
                "WECHAT_PAY_PRIVATE_KEY_PEM 不似 PEM 私钥（应含 BEGIN PRIVATE KEY / RSA PRIVATE KEY）",
            )
    elif cert_path:
        if not os.path.isfile(cert_path):
            errors.append(
                f"WECHAT_PAY_CERT_PATH 在进程内不存在或不可读：{cert_path}。"
                "CVM 须在仓库根提供 docker-compose.wechat-pay-key.yml 挂载 apiclient_key.pem，"
                "并使用 make deploy-cvm-up（或与 Makefile 相同的 compose -f 列表）启动 backend。"
                "勿仅用不含该文件的 docker compose up，否则下单必 502。"
            )
    else:
        errors.append(
            "商户 API 私钥未配置：在 .env.local 设置 WECHAT_PAY_PRIVATE_KEY_PEM，"
            "或使用 docker-compose.wechat-pay-key.yml 挂载 apiclient_key.pem 并设置 "
            "WECHAT_PAY_CERT_PATH=/secrets/apiclient_key.pem",
        )

    return errors


def _is_ephemeral_tunnel_hostname(host: str) -> bool:
    """识别 Cloudflare quick tunnel / ngrok 等临时公网地址，签进 upload_url 会导致微信无法配置合法域名。"""
    h = host.strip().lower()
    if not h:
        return False
    if ".trycloudflare.com" in h:
        return True
    if "ngrok" in h:
        return True
    if h.endswith(".loca.lt") or h.endswith(".localtunnel.me"):
        return True
    if "serveo.net" in h:
        return True
    return h.endswith(".bore.pub")


def audit_production_config(settings: Settings) -> tuple[list[str], list[str]]:
    """返回 (fatal_errors, warnings).

    fatal：APP_ENV=prod 时须在启动阶段直接失败。
    warnings：prod / staging 均打日志提示。
    """
    errors: list[str] = []
    warns: list[str] = []

    if settings.WECHAT_MOCK_LOGIN:
        errors.append(
            "WECHAT_MOCK_LOGIN=true：生产必须使用真实 wx.login（code2session），请设为 false",
        )

    pid = settings.WECHAT_MINIPROGRAM_APPID.strip()
    if not pid or "placeholder" in pid.lower():
        errors.append("WECHAT_MINIPROGRAM_APPID 未配置或为占位符")

    sec = settings.WECHAT_MINIPROGRAM_SECRET.strip()
    if not sec or "placeholder" in sec.lower():
        errors.append("WECHAT_MINIPROGRAM_SECRET 未配置或为占位符")

    if settings.APP_ENV == "prod" and settings.QUOTA_MODE == "unlimited":
        errors.append(
            "QUOTA_MODE=unlimited 不可用于生产环境（等价于全员无限配额）；请改回 strict",
        )

    weak_app = {"", "change-me", "change-me-to-a-random-32-char-string"}
    if settings.APP_SECRET_KEY.strip() in weak_app:
        errors.append("APP_SECRET_KEY 仍为占位值")
    weak_jwt = {"", "change-me-jwt"}
    jwt = settings.JWT_SECRET_KEY.strip()
    if jwt in weak_jwt or len(jwt) < 16:
        errors.append("JWT_SECRET_KEY 过弱或未改默认（建议 ≥32 字符随机串）")

    for label, blob in (
        ("APP_SECRET_KEY", settings.APP_SECRET_KEY),
        ("JWT_SECRET_KEY", settings.JWT_SECRET_KEY),
        ("DATABASE_URL", settings.database_url),
        ("REDIS_URL", settings.redis_url),
        ("REDIS_PASSWORD", settings.REDIS_PASSWORD),
        ("MINIO_ACCESS_KEY", settings.MINIO_ACCESS_KEY),
        ("MINIO_SECRET_KEY", settings.MINIO_SECRET_KEY),
        ("COS_SECRET_ID", settings.COS_SECRET_ID),
        ("COS_SECRET_KEY", settings.COS_SECRET_KEY),
        ("LLM_API_KEY", settings.LLM_API_KEY),
    ):
        if _has_legacy_angle_bracket_placeholder(blob):
            errors.append(
                f"{label} 含尖括号模板片段（形如 <change-me…>）：易被原样拷贝进运行时，请删除并填入真实凭证",
            )

    api = settings.effective_api_public_base_url.strip()
    al = api.lower()
    if not al.startswith("https://"):
        errors.append(
            "API_PUBLIC_BASE_URL 必须为 https（微信小程序与主流 CDN 硬性要求）",
        )
    if "localhost" in al or "127.0.0.1" in al:
        errors.append("API_PUBLIC_BASE_URL 含 localhost / 127.0.0.1")

    stor = settings.storage_presign_origin_base.strip()
    shl = stor.lower()
    sh = _hostname(stor)
    if not sh:
        errors.append("storage_presign_origin_base 无效，无法解析上传域名")
    elif sh.lower() == "localhost" or sh.startswith("127."):
        errors.append(f"直传域名指向环回地址（{stor}），wx.uploadFile 真机不可用")
    elif (
        settings.APP_ENV in {"prod", "staging"}
        and sh
        and _is_ephemeral_tunnel_hostname(sh)
    ):
        errors.append(
            f"直传域名指向临时穿透主机（{sh}），wx.uploadFile 无法在公众平台配置；"
            "请把 MINIO_PUBLIC_ENDPOINT 改为备案 HTTPS 域名（常见：与网关一致的 https://api…/minio），"
            "或改回占位地址 http://localhost:9000 / http://127.0.0.1:9000 "
            "以在 staging/prod 自动回落到 API_PUBLIC_BASE_URL/minio（须已在网关反代 MinIO）。",
        )

    if settings.STORAGE_PROVIDER == "cos":
        if not (settings.COS_SECRET_ID.strip() and settings.COS_SECRET_KEY.strip()):
            errors.append("STORAGE_PROVIDER=cos 但 COS 密钥为空")
        if not settings.COS_BUCKET.strip():
            errors.append("STORAGE_PROVIDER=cos 但 COS_BUCKET 为空")
        if "myqcloud.com" in shl:
            warns.append(
                "COS 直传域名为 *.myqcloud.com：公众平台「uploadFile 合法域名」须单独添加该 HTTPS 主机；"
                "与 API(request)域名不同属正常情况。",
            )

    api_h = _hostname(api)
    stor_h = sh
    if (
        settings.STORAGE_PROVIDER == "minio"
        and api_h
        and stor_h
        and api_h.lower() != stor_h.lower()
    ):
        warns.append(
            f"上传直传主机 ({stor_h}) 与 API 主机 ({api_h}) 不同：微信公众平台须同时登记两段 https 域名"
            "（request 与 uploadFile）。",
        )

    if settings.APP_ENV == "prod" and settings.WECHAT_PAY_MOCK_MODE:
        warns.append(
            "WECHAT_PAY_MOCK_MODE=true：当前仍为微信支付 mock；接真实商户号后设为 false，并补齐证书 / notify_url。",
        )

    if settings.APP_ENV in {"prod", "staging"} and (
        settings.LLM_MOCK_MODE or _is_placeholder_key(settings.LLM_API_KEY)
    ):
        warns.append(
            "LLM 当前将使用 FakeLLM（LLM_MOCK_MODE 或 LLM_API_KEY 为空/占位）；"
            "对话等能力会变成测试替身而非真实模型。",
        )

    return errors, warns


def startup_production_guards(logger, settings: Settings) -> None:
    if os.getenv("SKIP_PRODUCTION_GUARD", "").strip().lower() in {"1", "true", "yes"}:
        logger.warning(
            "production_config_audit_skipped",
            detail="SKIP_PRODUCTION_GUARD 已启用：生产门禁未执行（仅紧急排障时使用）。",
        )
        return

    errs, warns = audit_production_config(settings)

    pay_errs: list[str] = []
    if settings.APP_ENV in {"staging", "prod"} and not settings.WECHAT_PAY_MOCK_MODE:
        pay_errs = audit_wechat_pay_real_mode(settings)

    for w in warns:
        logger.warning("production_config_audit", severity="warn", detail=w)

    if settings.APP_ENV == "staging":
        for e in errs:
            logger.error("production_config_audit", severity="would_fail_in_prod", detail=e)
        if pay_errs:
            msg = "[微信支付·真实商户] 配置不完整，进程拒绝启动（避免下单才返回 502）：\n" + "\n".join(
                f"  • {e}" for e in pay_errs
            )
            logger.error("wechat_pay_config_audit", severity="fatal", errors=pay_errs)
            raise RuntimeError(msg)
        return

    if settings.APP_ENV == "prod":
        fatal = [*errs, *pay_errs]
        if fatal:
            msg = "[生产门禁] 进程拒绝启动：\n" + "\n".join(f"  • {e}" for e in fatal)
            logger.error("production_config_audit", severity="fatal", errors=fatal)
            raise RuntimeError(msg)
