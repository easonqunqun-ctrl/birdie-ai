"""staging / prod：启动时输出「微信公众平台 → 服务器域名」自查提示。

不涉及任何网络探测；仅从当前 Settings 推导 request / uploadFile / downloadFile
应匹配的 https 主机，减少配置疏漏导致的真机静默失败。"""
from __future__ import annotations

from urllib.parse import urlparse

from app.config import Settings


def log_wechat_miniprogram_domain_hints(logger, settings: Settings) -> None:
    if settings.APP_ENV not in {"staging", "prod"}:
        return

    api_base = settings.effective_api_public_base_url
    stor_base = settings.storage_presign_origin_base

    api_host = urlparse(api_base).hostname
    stor_host = urlparse(stor_base).hostname if stor_base else None

    same_host = api_host and stor_host and api_host == stor_host

    note = ""
    if settings.STORAGE_PROVIDER == "cos" and stor_host and "myqcloud.com" in stor_host.lower():
        note = (
            "COS 直传主机常为 cos.<region>.myqcloud.com，"
            "与 API 域名不同属正常情况：请务必在公众平台「uploadFile 合法域名」单独登记该主机，"
            "或将 COS_PUBLIC_BASE 指到已通过备案并与后台一致的 CDN 域名。"
        )

    if api_host:
        lh = api_host.lower()
        if lh == "localhost" or lh.startswith("127.") or api_base.startswith("http://"):
            logger.warning(
                "wechat_deploy_bad_api_public",
                api_public_base=api_base,
                detail="staging/prod 下 API_PUBLIC_BASE_URL 仍为 loopback/http，"
                "小程序真机将无法请求后端；图片代理/downloadFile(request 同源) 也会失败。"
                "请设为公网 HTTPS。",
            )

    logger.warning(
        "wechat_miniprogram_server_domain_hints",
        request_download_file_host_https=f"https://{api_host}" if api_host else None,
        upload_file_host_https=f"https://{stor_host}" if stor_host else None,
        upload_same_host_as_api=same_host,
        storage_provider=settings.STORAGE_PROVIDER,
        extra_note=note or None,
    )
