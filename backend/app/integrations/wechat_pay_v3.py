"""微信支付 V3：JSAPI 下单、小程序调起支付参数、回调验签与解密。"""

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings
from app.schemas.payment import PrepayParams


class WechatPayRequestError(Exception):
    """调用微信 API 失败."""


@dataclass
class _PlatformCert:
    """微信「平台公钥」缓存（从 /v3/certificates 拉取后解密 PEM）。"""

    by_serial: dict[str, bytes] = field(default_factory=dict)
    not_after: datetime | None = None


def _load_merchant_private_key(pem_data: str):
    return serialization.load_pem_private_key(
        pem_data.encode() if isinstance(pem_data, str) else pem_data,
        password=None,
    )


def _sign_wechat_v3_request(
    *,
    mchid: str,
    mch_serial: str,
    private_key_pem: str,
    method: str,
    path: str,
    body: str,
) -> str:
    """构造 Authorization: WECHATPAY2-SHA256-RSA2048 ..."""
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    msg = f"{method}\n{path}\n{ts}\n{nonce}\n{body}\n"
    pkey = _load_merchant_private_key(private_key_pem)
    sig = pkey.sign(
        msg.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    b64 = base64.b64encode(sig).decode("ascii")
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{mchid}",'
        f'nonce_str="{nonce}",signature="{b64}",timestamp="{ts}",serial_no="{mch_serial}"'
    )


def _aes_gcm_decrypt(*, apiv3_key: str, nonce_b64: str, aad: str, ciphertext_b64: str) -> str:
    key = apiv3_key.encode("utf-8")
    if len(key) != 32:
        # 与微信约定：32 字符长度 APIv3 密钥
        raise ValueError("APIv3 key must be 32 bytes/characters")
    nonce = base64.b64decode(nonce_b64)
    ct = base64.b64decode(ciphertext_b64)
    aesgcm = AESGCM(key)
    plain = aesgcm.decrypt(nonce, ct, aad.encode("utf-8") if aad else b"")
    return plain.decode("utf-8")


def _build_miniprogram_pay_sign(*, private_key_pem: str, appid: str, time_stamp: str, nonce_str: str, package: str) -> str:
    """小程序/公众号调起支付：签名串 = appid\\n + timeStamp + ...（timeStamp 为字符串，秒级）。"""
    msg = f"{appid}\n{time_stamp}\n{nonce_str}\n{package}\n"
    pkey = _load_merchant_private_key(private_key_pem)
    sig = pkey.sign(
        msg.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("ascii")


def _decode_success_json(r: httpx.Response, path: str) -> dict[str, Any]:
    """微信 V3 成功响应须为 JSON object；解析失败转为业务可读错误."""
    try:
        data = r.json()
    except json.JSONDecodeError as e:
        raise WechatPayRequestError(
            f"wechat v3 {path} HTTP {r.status_code} invalid json: {r.text[:400]!r}"
        ) from e
    if not isinstance(data, dict):
        raise WechatPayRequestError(
            f"wechat v3 {path} expected JSON object, got {type(data).__name__}"
        )
    return data


@dataclass
class WechatPayV3Context:
    """请求级上下文，持有商户与密钥（每次请求新建）。"""

    mchid: str
    appid: str
    apiv3_key: str
    mch_serial: str
    private_key_pem: str
    notify_url: str
    _certs: _PlatformCert = field(default_factory=_PlatformCert)

    def _auth_header(self, method: str, path: str, body: str) -> str:
        return _sign_wechat_v3_request(
            mchid=self.mchid,
            mch_serial=self.mch_serial,
            private_key_pem=self.private_key_pem,
            method=method,
            path=path,
            body=body,
        )

    async def _http_post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        url = f"https://api.mch.weixin.qq.com{path}"
        h = {
            "Authorization": self._auth_header("POST", path, body),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(url, content=body.encode("utf-8"), headers=h)
        except httpx.RequestError as e:
            raise WechatPayRequestError(f"wechat v3 POST {path} network: {e!s}") from e
        if r.status_code >= 300:
            try:
                err = r.json()
            except Exception:
                err = {"raw": r.text}
            raise WechatPayRequestError(
                f"wechat v3 {path} {r.status_code}: {err}",
            )
        return _decode_success_json(r, path)

    async def _http_get(self, path: str) -> dict[str, Any]:
        body = ""  # GET 不签 body
        url = f"https://api.mch.weixin.qq.com{path}"
        h = {
            "Authorization": self._auth_header("GET", path, body),
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(url, headers=h)
        except httpx.RequestError as e:
            raise WechatPayRequestError(f"wechat v3 GET {path} network: {e!s}") from e
        if r.status_code >= 300:
            try:
                err = r.json()
            except Exception:
                err = {"raw": r.text}
            raise WechatPayRequestError(f"wechat v3 GET {path} {r.status_code}: {err}")
        return _decode_success_json(r, path)

    async def ensure_platform_certs(self) -> None:
        if (
            self._certs.not_after
            and self._certs.not_after > datetime.now(UTC)
            and self._certs.by_serial
        ):
            return
        data = await self._http_get("/v3/certificates")
        for item in data.get("data", []):
            enc = item.get("encrypt_certificate", {})
            if not enc:
                continue
            serial = item.get("serial_no", "")
            aad = enc.get("associated_data") or "certificate"
            pem_plain = _aes_gcm_decrypt(
                apiv3_key=self.apiv3_key,
                nonce_b64=enc["nonce"],
                aad=aad,
                ciphertext_b64=enc["ciphertext"],
            )
            if pem_plain.strip().startswith("-----"):
                self._certs.by_serial[serial] = pem_plain.encode("utf-8")
        from datetime import timedelta

        self._certs.not_after = datetime.now(UTC) + timedelta(hours=4)

    def verify_callback_signature(
        self,
        *,
        wechatpay_serial: str,
        wechatpay_signature: str,
        wechatpay_timestamp: str,
        wechatpay_nonce: str,
        body: bytes,
    ) -> bool:
        """验证 notify 的 Wechatpay-Signature。"""
        msg = f"{wechatpay_timestamp}\n{wechatpay_nonce}\n{body.decode('utf-8')}\n"
        cert_pem = self._certs.by_serial.get(wechatpay_serial)
        if not cert_pem:
            return False
        try:
            cert = x509.load_pem_x509_certificate(cert_pem)
            pub = cert.public_key()
            sig = base64.b64decode(wechatpay_signature)
            pub.verify(
                sig,
                msg.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    async def prepare_notify_verification(self) -> None:
        await self.ensure_platform_certs()

    async def create_jsapi_order(
        self,
        *,
        out_trade_no: str,
        openid: str,
        amount_cents: int,
        description: str,
    ) -> str:
        path = "/v3/pay/transactions/jsapi"
        payload: dict[str, Any] = {
            "mchid": self.mchid,
            "appid": self.appid,
            "out_trade_no": out_trade_no,
            "description": (description or "会员服务")[:127],
            "notify_url": self.notify_url,
            "amount": {"total": amount_cents, "currency": "CNY"},
            "payer": {"openid": openid},
        }
        r = await self._http_post(path, payload)
        return r.get("prepay_id", "")

    async def query_transaction_by_out_trade_no(
        self,
        out_trade_no: str,
    ) -> dict[str, Any]:
        """按商户订单号查单：``GET /v3/pay/transactions/out-trade-no/{no}?mchid={mchid}``.

        返回明文 JSON（trade_state / transaction_id / amount.total 等）。
        注意：签名必须包含 query string（含 mchid），否则微信侧 401。
        """
        from urllib.parse import quote

        encoded_no = quote(out_trade_no, safe="")
        path = f"/v3/pay/transactions/out-trade-no/{encoded_no}?mchid={self.mchid}"
        return await self._http_get(path)

    async def papay_pre_entrust_mini_program(
        self,
        *,
        openid: str,
        plan_id: int,
        out_contract_code: str,
        contract_display_account: str,
        contract_notify_url: str,
        estimated_deduct_date: str,
        estimated_deduct_total: int,
        description: str,
    ) -> dict[str, Any]:
        """预约扣费 / 委托代扣：小程序预签约（返回跳转微信签约页参数）。"""
        path = "/v3/papay/scheduled-deduct-sign/contracts/pre-entrust-sign/mini-program"
        payload: dict[str, Any] = {
            "appid": self.appid,
            "openid": openid,
            "plan_id": int(plan_id),
            "out_contract_code": out_contract_code[:32],
            "contract_display_account": contract_display_account[:32],
            "contract_notify_url": contract_notify_url[:256],
            "deduct_schedule": {
                "estimated_deduct_date": estimated_deduct_date,
                "estimated_deduct_amount": {
                    "total": int(estimated_deduct_total),
                    "currency": "CNY",
                },
                "description": description[:32],
            },
        }
        return await self._http_post(path, payload)

    async def domestic_refund(
        self,
        *,
        out_trade_no: str,
        out_refund_no: str,
        refund_cents: int,
        total_cents: int,
        notify_url: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """调用 `/v3/refund/domestic/refunds`（全额退款与 order.amount 对齐）."""
        path = "/v3/refund/domestic/refunds"
        why = (reason or "用户发起退款").strip() or "退款"
        payload: dict[str, Any] = {
            "out_trade_no": out_trade_no,
            "out_refund_no": out_refund_no[:64],
            "notify_url": notify_url,
            "reason": why[:80],
            "amount": {
                "refund": refund_cents,
                "total": total_cents,
                "currency": "CNY",
            },
        }
        return await self._http_post(path, payload)


    def build_miniprogram_prepay(self, prepay_id: str) -> PrepayParams:
        time_stamp = str(int(time.time()))
        nonce_str = secrets.token_hex(8)
        package = f"prepay_id={prepay_id}"
        pay_sign = _build_miniprogram_pay_sign(
            private_key_pem=self.private_key_pem,
            appid=self.appid,
            time_stamp=time_stamp,
            nonce_str=nonce_str,
            package=package,
        )
        return PrepayParams(
            mock=False,
            time_stamp=time_stamp,
            nonce_str=nonce_str,
            package=package,
            sign_type="RSA",
            pay_sign=pay_sign,
        )

    def decrypt_notify_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        """解密 `transaction` 通知 resource。"""
        c = resource.get("ciphertext")
        n = resource.get("nonce")
        if not c or not n:
            return {}
        aad = resource.get("associated_data") or ""
        s = _aes_gcm_decrypt(
            apiv3_key=self.apiv3_key,
            nonce_b64=n,
            aad=aad,
            ciphertext_b64=c,
        )
        return json.loads(s)


def load_private_key_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as e:
        raise RuntimeError(
            f"商户私钥文件不存在：{path}。"
            "Docker/CVM 请在仓库根复制 docker-compose.wechat-pay-key.example.yml 为 "
            "docker-compose.wechat-pay-key.yml，挂载 apiclient_key.pem，并在 .env.local 设置 "
            "WECHAT_PAY_CERT_PATH=/secrets/apiclient_key.pem（与 make deploy-cvm-up 叠加）。"
        ) from e
    except OSError as e:
        raise RuntimeError(f"无法读取商户私钥文件 {path}: {e}") from e


def get_wechat_pay_v3() -> WechatPayV3Context:
    if settings.WECHAT_PAY_MOCK_MODE or not settings.WECHAT_PAY_MCH_ID:
        raise RuntimeError("wechat pay v3 not configured")
    inline = (getattr(settings, "WECHAT_PAY_PRIVATE_KEY_PEM", None) or "").strip()
    if inline:
        pem = inline
    else:
        p = (settings.WECHAT_PAY_CERT_PATH or "").strip()
        if not p:
            raise RuntimeError("WECHAT_PAY_CERT_PATH 或 WECHAT_PAY_PRIVATE_KEY_PEM 未设置")
        pem = load_private_key_file(p)
    if not settings.WECHAT_PAY_MCH_SERIAL:
        raise RuntimeError("WECHAT_PAY_MCH_SERIAL 未设置（商户 API 证书序列号）")
    if not settings.WECHAT_PAY_API_V3_KEY and not settings.WECHAT_PAY_API_KEY:
        raise RuntimeError("WECHAT_PAY_API_V3_KEY 未设置")
    apiv3 = (settings.WECHAT_PAY_API_V3_KEY or settings.WECHAT_PAY_API_KEY or "").strip()
    if len(apiv3) != 32:
        raise ValueError("APIv3 密钥须为 32 字符，请检查 WECHAT_PAY_API_V3_KEY")
    if not (settings.WECHAT_PAY_NOTIFY_URL or "").strip():
        raise RuntimeError("WECHAT_PAY_NOTIFY_URL 未设置")
    return WechatPayV3Context(
        mchid=settings.WECHAT_PAY_MCH_ID,
        appid=settings.WECHAT_MINIPROGRAM_APPID,
        apiv3_key=apiv3,
        mch_serial=settings.WECHAT_PAY_MCH_SERIAL,
        private_key_pem=pem,
        notify_url=settings.WECHAT_PAY_NOTIFY_URL.strip(),
    )


def _head_ci(headers: dict[str, str], key: str) -> str:
    m = {k.lower(): v for k, v in headers.items()}
    return m.get(key.lower(), "")


def resolve_wechat_pay_refund_notify_url() -> str:
    """退款结果 notify_url：`WECHAT_PAY_REFUND_NOTIFY_URL` 或从支付回调 URL 推导。"""
    ru = (getattr(settings, "WECHAT_PAY_REFUND_NOTIFY_URL", "") or "").strip()
    if ru:
        return ru
    base = (settings.WECHAT_PAY_NOTIFY_URL or "").strip()
    if not base:
        return ""
    needle = "/payments/wechat/notify"
    if needle in base:
        return base.replace(needle, "/payments/wechat/refund-notify")
    return ""


async def decrypt_wechat_pay_notify_resource(
    *, raw_body: bytes, headers: dict[str, str]
) -> dict[str, Any] | None:
    """验签 + 解密微信支付 / 退款结果通知的统一 resource ciphertext。"""
    ctx = get_wechat_pay_v3()
    await ctx.prepare_notify_verification()
    serial = _head_ci(headers, "wechatpay-serial")
    signature = _head_ci(headers, "wechatpay-signature")
    ts = _head_ci(headers, "wechatpay-timestamp")
    nonce = _head_ci(headers, "wechatpay-nonce")
    if not all([serial, signature, ts, nonce]):
        return None
    ok = ctx.verify_callback_signature(
        wechatpay_serial=serial,
        wechatpay_signature=signature,
        wechatpay_timestamp=ts,
        wechatpay_nonce=nonce,
        body=raw_body,
    )
    if not ok:
        return None
    try:
        outer = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    res = outer.get("resource")
    if not res:
        return None
    return ctx.decrypt_notify_resource(res)


async def handle_payment_notify(
    *, raw_body: bytes, headers: dict[str, str]
) -> dict[str, Any] | None:
    """验签 + 解密支付 `transaction.success` resource（与解密函数同路径）."""
    return await decrypt_wechat_pay_notify_resource(raw_body=raw_body, headers=headers)
