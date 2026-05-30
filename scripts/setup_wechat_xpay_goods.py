#!/usr/bin/env python3
"""通过虚拟支付 API 上传并发布月度/年度会员道具（沙箱 + 现网）。

依赖 .env.local 或 --env-file 中的：
  WECHAT_MINIPROGRAM_APPID / WECHAT_MINIPROGRAM_SECRET
  WECHAT_XPAY_SANDBOX_APP_KEY / WECHAT_XPAY_APP_KEY

用法：
  python3 scripts/setup_wechat_xpay_goods.py
  python3 scripts/setup_wechat_xpay_goods.py --env 1          # 仅沙箱
  python3 scripts/setup_wechat_xpay_goods.py --env 0          # 仅现网
  python3 scripts/setup_wechat_xpay_goods.py --skip-publish   # 只上传
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
UPLOAD_URL = "https://api.weixin.qq.com/xpay/start_upload_goods"
QUERY_UPLOAD_URL = "https://api.weixin.qq.com/xpay/query_upload_goods"
PUBLISH_URL = "https://api.weixin.qq.com/xpay/start_publish_goods"
QUERY_PUBLISH_URL = "https://api.weixin.qq.com/xpay/query_publish_goods"

PRODUCT_MONTHLY_ID = "birdie_membership_monthly"
PRODUCT_YEARLY_ID = "birdie_membership_yearly"
# 须公网 HTTPS；微信会转存。默认用线上 MinIO 示例图（可 --item-url 覆盖）
DEFAULT_IMAGE_PATH = ROOT / "infra" / "deploy" / "static" / "xpay" / "membership-200.jpg"
DEFAULT_ITEM_URL = "https://api.birdieai.cn/v1/public/xpay/membership-product.png"
ADD_MATERIAL_URL = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"

GOODS = [
    {
        "id": PRODUCT_MONTHLY_ID,
        "name": "月度会员",
        "price": 3900,
        "remark": "领翼golf 月度会员，30 天 AI 分析与服务权益",
    },
    {
        "id": PRODUCT_YEARLY_ID,
        "name": "年度会员",
        "price": 29900,
        "remark": "领翼golf 年度会员，365 天 AI 分析与服务权益",
    },
]


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def merge_env(env_file: Path) -> None:
    vals = load_env_file(env_file)
    for k, v in vals.items():
        os.environ.setdefault(k, v)


def calc_pay_sig(uri: str, sign_data_json: str, app_key: str) -> str:
    msg = f"{uri}&{sign_data_json}"
    return hmac.new(app_key.encode(), msg.encode(), hashlib.sha256).hexdigest()


def xpay_app_key_for_env(env: int, vals: dict[str, str]) -> str:
    if env == 1:
        key = (vals.get("WECHAT_XPAY_SANDBOX_APP_KEY") or "").strip()
        if not key:
            raise RuntimeError("WECHAT_XPAY_SANDBOX_APP_KEY 未配置")
        return key
    key = (vals.get("WECHAT_XPAY_APP_KEY") or "").strip()
    if not key:
        raise RuntimeError("WECHAT_XPAY_APP_KEY 未配置")
    return key


def http_get_json(url: str, params: dict[str, str]) -> dict:
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{q}", timeout=20) as resp:
        return json.loads(resp.read().decode())


def http_post_json(url: str, body_json: str) -> dict:
    req = urllib.request.Request(
        url,
        data=body_json.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def upload_material_image(access_token: str, image_path: Path) -> str:
    """上传图文素材图，返回微信 CDN URL（供 xpay item_url 拉取）。"""
    if not image_path.is_file():
        raise RuntimeError(f"道具图不存在: {image_path}")
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    boundary = f"----BirdieXpay{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="media"; filename="{image_path.name}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode())
    body.extend(image_path.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode())

    url = f"{ADD_MATERIAL_URL}?access_token={urllib.parse.quote(access_token)}"
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    if data.get("errcode", 0) not in (0, None) and "url" not in data:
        raise RuntimeError(f"upload material failed: {data}")
    item_url = (data.get("url") or "").strip()
    if not item_url:
        raise RuntimeError(f"upload material missing url: {data}")
    print(f"  material image url: {item_url}")
    return item_url


def get_access_token(appid: str, secret: str) -> str:
    data = http_get_json(
        ACCESS_TOKEN_URL,
        {
            "grant_type": "client_credential",
            "appid": appid,
            "secret": secret,
        },
    )
    if data.get("errcode", 0) not in (0, None) and "access_token" not in data:
        raise RuntimeError(f"access_token 失败: {data}")
    return data["access_token"]


def xpay_post(
    url: str,
    uri: str,
    access_token: str,
    body: dict,
    *,
    app_key: str,
) -> dict:
    body_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    pay_sig = calc_pay_sig(uri, body_json, app_key)
    full = f"{url}?access_token={urllib.parse.quote(access_token)}&pay_sig={pay_sig}"
    return http_post_json(full, body_json)


def xpay_uri(action: str) -> str:
    """官方服务端 pay_sig 的 uri 带前导 /，如 /xpay/start_upload_goods。"""
    action = action.lstrip("/")
    return f"/xpay/{action}" if not action.startswith("xpay/") else f"/{action}"


def wait_upload(access_token: str, env: int, app_key: str, product_id: str) -> None:
    uri = xpay_uri("query_upload_goods")
    for _ in range(30):
        data = xpay_post(
            QUERY_UPLOAD_URL,
            uri,
            access_token,
            {"env": env},
            app_key=app_key,
        )
        status = int(data.get("status", -1))
        items = data.get("upload_item") or []
        item = next((i for i in items if i.get("id") == product_id), None)
        if status == 3:
            if item and int(item.get("upload_status", 0)) in (1, 2):
                print(f"    upload ok: {product_id} (status={item.get('upload_status')})")
                return
            raise RuntimeError(f"upload failed: {product_id} -> {data}")
        if status == 2:
            raise RuntimeError(f"upload failed: {product_id} -> {data}")
        if status == 0 and item and int(item.get("upload_status", 0)) in (1, 2):
            print(f"    upload ok: {product_id}")
            return
        time.sleep(2)
    raise RuntimeError(f"upload timeout: {product_id}")


def wait_publish(access_token: str, env: int, app_key: str, product_id: str) -> None:
    uri = xpay_uri("query_publish_goods")
    for _ in range(30):
        data = xpay_post(
            QUERY_PUBLISH_URL,
            uri,
            access_token,
            {"env": env},
            app_key=app_key,
        )
        status = int(data.get("status", -1))
        items = data.get("publish_item") or []
        item = next((i for i in items if i.get("id") == product_id), None)
        if status == 3:
            print(f"    publish ok: {product_id}")
            return
        if status == 2:
            raise RuntimeError(f"publish failed: {product_id} -> {data}")
        if item and int(item.get("publish_status", 0)) == 2:
            print(f"    publish ok: {product_id}")
            return
        time.sleep(2)
    raise RuntimeError(f"publish timeout: {product_id}")


def provision_one(
    access_token: str,
    env: int,
    app_key: str,
    good: dict,
    item_url: str,
    *,
    skip_publish: bool,
) -> None:
    upload_body = {
        "env": env,
        "upload_item": [
            {
                "id": good["id"],
                "name": good["name"],
                "price": good["price"],
                "remark": good["remark"],
                "item_url": item_url,
            }
        ],
    }
    print(f"  upload {good['id']} env={env} ...")
    up = xpay_post(UPLOAD_URL, xpay_uri("start_upload_goods"), access_token, upload_body, app_key=app_key)
    if up.get("errcode", 0) not in (0, None):
        if up.get("errcode") == 268490004:
            print(f"    upload duplicate (ok): {good['id']}")
        else:
            raise RuntimeError(f"start_upload_goods: {up}")
    wait_upload(access_token, env, app_key, good["id"])

    if skip_publish:
        return

    pub_body = {"env": env, "publish_item": [{"id": good["id"]}]}
    print(f"  publish {good['id']} ...")
    pub = xpay_post(PUBLISH_URL, xpay_uri("start_publish_goods"), access_token, pub_body, app_key=app_key)
    if pub.get("errcode", 0) not in (0, None):
        if pub.get("errcode") == 268490004:
            print(f"    publish duplicate (ok): {good['id']}")
            return
        raise RuntimeError(f"start_publish_goods: {pub}")
    wait_publish(access_token, env, app_key, good["id"])


def provision_env(
    env: int,
    vals: dict[str, str],
    *,
    item_url: str | None,
    image_path: Path,
    skip_publish: bool,
) -> None:
    label = "sandbox" if env == 1 else "production"
    print(f"\n=== xpay goods ({label}, env={env}) ===")
    app_key = xpay_app_key_for_env(env, vals)

    appid = vals.get("WECHAT_MINIPROGRAM_APPID", "").strip()
    secret = vals.get("WECHAT_MINIPROGRAM_SECRET", "").strip()
    if not appid or not secret or "placeholder" in secret:
        raise RuntimeError("WECHAT_MINIPROGRAM_APPID/SECRET 未配置")

    token = get_access_token(appid, secret)
    resolved_item_url = item_url or upload_material_image(token, image_path)
    for good in GOODS:
        provision_one(token, env, app_key, good, resolved_item_url, skip_publish=skip_publish)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(ROOT / ".env.local"))
    parser.add_argument("--env", type=int, choices=[0, 1], action="append", dest="envs")
    parser.add_argument(
        "--item-url",
        default="",
        help=f"自定义道具图 URL；默认上传 {DEFAULT_IMAGE_PATH.name} 到微信永久素材",
    )
    parser.add_argument("--image-path", default=str(DEFAULT_IMAGE_PATH))
    parser.add_argument("--skip-publish", action="store_true")
    args = parser.parse_args()

    merge_env(Path(args.env_file))
    env_path = Path(args.env_file)
    vals = load_env_file(env_path)
    for k, v in vals.items():
        os.environ.setdefault(k, v)
    envs = args.envs if args.envs else [1, 0]

    item_url = args.item_url.strip() or None
    image_path = Path(args.image_path).expanduser()

    try:
        for env in envs:
            provision_env(
                env,
                vals,
                item_url=item_url,
                image_path=image_path,
                skip_publish=args.skip_publish,
            )
    except Exception as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    print("\n✓ 道具 provisioning 完成")
    print(f"  WECHAT_XPAY_PRODUCT_MONTHLY={PRODUCT_MONTHLY_ID}")
    print(f"  WECHAT_XPAY_PRODUCT_YEARLY={PRODUCT_YEARLY_ID}")
    print("\n下一步：写入 env 并配置 mp 消息推送 Token（见 scripts/apply_wechat_xpay_env.py）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
