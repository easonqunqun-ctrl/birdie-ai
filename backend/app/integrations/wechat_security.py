"""微信内容安全 API 封装（W8-T5 / P1-C1）。

封装两个接口：
1. `img_sec_check`（图片合规，W8-T5）
2. `msg_sec_check` v2（文本合规，P1-C1：用户在 AI 教练里发的消息必须先过审）

文档
----
- 图片：https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/sec-check/security.imgSecCheck.html
- 文本：https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/sec-check/security.msgSecCheck.html

关键事实（图片）
----------------
- 请求：`POST /wxa/img_sec_check?access_token=...`，multipart/form-data，字段名固定 `media`
- 响应：
    - `errcode=0`            → 通过
    - `errcode=87014`        → 内容违规（色情/暴力/辱骂等）
    - `errcode=40001/42001`  → access_token 失效，应刷新后重试一次
    - 其它 errcode           → 记录日志，按业务降级（本项目默认"放过 + 告警"）
- 图片限制：≤ 1MB，JPG/PNG/BMP/GIF，一次只能一张

关键事实（文本 v2）
-------------------
- 请求：`POST /wxa/msg_sec_check?access_token=...`，JSON body 必带：
    - `version=2`（v2 才有 `result.suggest` 三态）
    - `openid`：**必须**传，且必须是已经访问过该小程序的 openid，否则 errcode=42012
    - `scene`：1 资料 / 2 评论 / 3 论坛 / 4 社交日志（chat 取 4）
    - `content`：≤ 2500 字（超长要先截）
- 响应里看 `result.suggest`：
    - `pass`   → 通过
    - `risky`  → 命中违规，必须拒绝
    - `review` → 疑似违规，业务自定（这里**保守 fail open** + 高风险标签时拦截）
- 同样要处理 40001/42001 token 失效重试一次

工程决策
--------
- 本项目**只对视频首帧**做图片审核：视频本身的逐帧审核（`media_check_async`）
  要走异步回调 + 登记 CallbackURL，成本和联调周期都高，W8 先省略
- 当 `WECHAT_MOCK_LOGIN=true` 时，本模块走 mock 分支：
    - 普通路径返回 `passed=True`
    - 文件名/文本里包含 "violation" / "unsafe" / "违规" / "色情" / "暴力" 时返回 `passed=False`
  让本地/CI 联调不依赖真实网络，又能覆盖"违规"分支
- 42001 自动重试一次（刷 token）；其它错误直接按"fail open"处理，由调用方
  决定是否 toast "审核服务暂不可用，请稍后再试"
- **文本审核 fail open 的理由**：聊天属高频低危场景；微信侧短暂故障不应该让
  用户的对话被全量阻塞。真正的合规底线由微信运营审 + 我方人审兜底。
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings
from app.core.logging import get_logger
from app.integrations.wechat_access_token import get_access_token

logger = get_logger("wechat_security")

IMG_SEC_CHECK_URL = "https://api.weixin.qq.com/wxa/img_sec_check"
MSG_SEC_CHECK_URL = "https://api.weixin.qq.com/wxa/msg_sec_check"

# 违规错误码（87014）+ access_token 过期（40001/42001）
ERRCODE_VIOLATION = 87014
ERRCODE_TOKEN_EXPIRED = {40001, 42001}

# msg_sec_check 文本上限：微信文档 2500 字符；超出我们截断（保留前 2500）
TEXT_CHECK_MAX_LEN = 2500
# 命中"高风险"标签时，即使 suggest=review 也直接拒绝
# label 100 = 正常；其它如 20001 政治、20002 色情、20003 辱骂、20006 违法犯罪等都是高风险
HIGH_RISK_LABELS: set[int] = {20001, 20002, 20003, 20006, 20008, 20012, 20013}


@dataclass
class ImgCheckResult:
    """单张图片审核结论。"""

    passed: bool
    """是否合规；True = 可继续业务，False = 必须拒绝。"""

    reason: str | None = None
    """失败原因（面向用户的 toast 文案或内部日志）。"""

    errcode: int | None = None
    """微信返回的 errcode，用于调用方上报日志/埋点。"""


@dataclass
class TextCheckResult:
    """单段文本审核结论（msg_sec_check v2）。"""

    passed: bool
    """是否合规；True = 可继续业务，False = 必须拒绝。"""

    reason: str | None = None
    """失败原因（面向用户的 toast 文案或内部日志）。"""

    suggest: str | None = None
    """微信返回的 `suggest`：pass/risky/review，None 表示未拿到（fail open 兜底）。"""

    label: int | None = None
    """微信返回的 `label`，用于细分违规类型。"""

    errcode: int | None = None
    """微信返回的 errcode，用于调用方上报日志/埋点。"""


async def check_image(file_bytes: bytes, file_name: str = "thumb.jpg") -> ImgCheckResult:
    """对单张图片调用微信 `img_sec_check`。

    Args:
        file_bytes: 图片原始字节（≤ 1MB，否则微信直接 40005）
        file_name: 上传时 multipart 的 `filename` 字段（不影响判定，仅日志/mock 判断用）

    Returns:
        ImgCheckResult：调用方按 `passed` 决定放行 / 拒绝。

    Note:
        本函数不抛 `ThirdPartyError`——内容审核链路更适合"fail open 并记录"，
        让主流程别被微信侧临时故障（比如 access_token 限流）阻塞整个拍摄闭环。
        严格模式（必须"通过"才放行）留到 W9 正式上线时加开关。
    """
    # mock 模式：根据文件名走通过 / 违规两条分支
    if settings.WECHAT_MOCK_LOGIN:
        lower = file_name.lower()
        if any(kw in lower for kw in ("violation", "unsafe", "违规")):
            return ImgCheckResult(
                passed=False,
                reason="内容涉嫌违规（mock）",
                errcode=ERRCODE_VIOLATION,
            )
        return ImgCheckResult(passed=True)

    access_token = await get_access_token()
    return await _call_remote(access_token, file_bytes, file_name, retried=False)


async def _call_remote(
    access_token: str,
    file_bytes: bytes,
    file_name: str,
    retried: bool,
) -> ImgCheckResult:
    """实际发起微信 HTTP 请求；token 过期时递归重试一次。"""
    params = {"access_token": access_token}
    files = {"media": (file_name, file_bytes, "application/octet-stream")}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(IMG_SEC_CHECK_URL, params=params, files=files)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        # 网络 / HTTP 异常 → fail open，但日志要显式，方便上线后看曲线
        logger.warning("wechat_img_sec_check_http_error", error=str(e))
        return ImgCheckResult(passed=True, reason="审核服务超时（fail open）")
    except ValueError as e:
        logger.warning("wechat_img_sec_check_decode_error", error=str(e))
        return ImgCheckResult(passed=True, reason="审核服务响应异常（fail open）")

    errcode = data.get("errcode", 0)

    if errcode == 0:
        return ImgCheckResult(passed=True, errcode=0)

    if errcode == ERRCODE_VIOLATION:
        logger.info("wechat_img_sec_check_violation", **data)
        return ImgCheckResult(
            passed=False,
            reason="内容涉嫌违规，请更换图片",
            errcode=errcode,
        )

    # access_token 过期：强制刷新后重试一次（只重试一次，避免死循环）
    if errcode in ERRCODE_TOKEN_EXPIRED and not retried:
        logger.info("wechat_img_sec_check_token_expired_retry", **data)
        fresh_token = await get_access_token(force_refresh=True)
        return await _call_remote(fresh_token, file_bytes, file_name, retried=True)

    # 其它错误 → 记录 + fail open，让主流程不被第三方拖垮
    logger.warning("wechat_img_sec_check_unknown_error", **data)
    return ImgCheckResult(
        passed=True,
        reason=f"审核服务返回未知错误 errcode={errcode}（fail open）",
        errcode=errcode,
    )


# ==================== 文本审核（msg_sec_check v2） ====================
# 用于 P1-C1：AI 教练用户消息入口必须先过审，违规直接拒绝（不消耗配额）。

_TEXT_VIOLATION_KEYWORDS = ("violation", "unsafe", "违规", "色情", "暴力", "辱骂")


async def check_text(
    content: str,
    *,
    openid: str,
    scene: int = 4,
) -> TextCheckResult:
    """对用户提交的文本调用微信 `msg_sec_check` v2。

    Args:
        content: 待审核文本。会被截断到 `TEXT_CHECK_MAX_LEN`。
        openid: 用户 wechat_openid（v2 强制要求；必须是已访问过本小程序的 openid，
            否则 errcode=42012）。
        scene: 业务场景，1 资料 / 2 评论 / 3 论坛 / 4 社交日志。chat 取 4。

    Returns:
        TextCheckResult：调用方按 `passed` 决定放行 / 拒绝。

    Note:
        和 `check_image` 同样的"fail open"策略：第三方服务故障时不阻断主流程。
        严格模式留到合规专项（W9 之后）按运营要求加开关。
    """
    text = (content or "").strip()
    if not text:
        # 空字符串没有审核必要；调用方一般也不会让空消息走到这里
        return TextCheckResult(passed=True, suggest="pass")

    if len(text) > TEXT_CHECK_MAX_LEN:
        text = text[:TEXT_CHECK_MAX_LEN]

    # mock 模式：根据关键词决定，开发/CI 不依赖外网
    if settings.WECHAT_MOCK_LOGIN:
        lowered = text.lower()
        if any(kw in lowered for kw in _TEXT_VIOLATION_KEYWORDS):
            return TextCheckResult(
                passed=False,
                reason="内容涉嫌违规（mock）",
                suggest="risky",
                errcode=ERRCODE_VIOLATION,
            )
        return TextCheckResult(passed=True, suggest="pass")

    access_token = await get_access_token()
    return await _call_msg_sec_check(
        access_token=access_token,
        content=text,
        openid=openid,
        scene=scene,
        retried=False,
    )


async def _call_msg_sec_check(
    *,
    access_token: str,
    content: str,
    openid: str,
    scene: int,
    retried: bool,
) -> TextCheckResult:
    """实际发起微信 `msg_sec_check` v2 请求；token 过期时递归重试一次。"""
    params = {"access_token": access_token}
    body = {
        "version": 2,
        "openid": openid,
        "scene": scene,
        "content": content,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(MSG_SEC_CHECK_URL, params=params, json=body)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning("wechat_msg_sec_check_http_error", error=str(e))
        return TextCheckResult(passed=True, reason="审核服务超时（fail open）")
    except ValueError as e:
        logger.warning("wechat_msg_sec_check_decode_error", error=str(e))
        return TextCheckResult(passed=True, reason="审核服务响应异常（fail open）")

    errcode = data.get("errcode", 0)

    # access_token 过期：强制刷新后重试一次
    if errcode in ERRCODE_TOKEN_EXPIRED and not retried:
        logger.info("wechat_msg_sec_check_token_expired_retry", **data)
        fresh_token = await get_access_token(force_refresh=True)
        return await _call_msg_sec_check(
            access_token=fresh_token,
            content=content,
            openid=openid,
            scene=scene,
            retried=True,
        )

    if errcode != 0:
        # 其它错误（如 87014 历史/单次失败、42012 openid 非法等）
        # 87014 在 v2 接口里也可能直接给 errcode；统一按"违规"处理
        if errcode == ERRCODE_VIOLATION:
            logger.info("wechat_msg_sec_check_violation_errcode", **data)
            return TextCheckResult(
                passed=False,
                reason="内容涉嫌违规，请调整后重试",
                suggest="risky",
                errcode=errcode,
            )
        logger.warning("wechat_msg_sec_check_unknown_error", **data)
        return TextCheckResult(
            passed=True,
            reason=f"审核服务返回 errcode={errcode}（fail open）",
            errcode=errcode,
        )

    # 解析 v2 result（理论上 v2 必返回；若没有则当通过）
    result = data.get("result") or {}
    suggest = (result.get("suggest") or "pass").lower()
    label = result.get("label")

    if suggest == "risky":
        logger.info("wechat_msg_sec_check_risky", suggest=suggest, label=label)
        return TextCheckResult(
            passed=False,
            reason="内容涉嫌违规，请调整后重试",
            suggest=suggest,
            label=label,
            errcode=0,
        )

    if suggest == "review":
        # 默认 fail open，但若是高风险标签则拦截，避免明显违规漏过
        if isinstance(label, int) and label in HIGH_RISK_LABELS:
            logger.info(
                "wechat_msg_sec_check_review_high_risk",
                suggest=suggest,
                label=label,
            )
            return TextCheckResult(
                passed=False,
                reason="内容涉嫌违规，请调整后重试",
                suggest=suggest,
                label=label,
                errcode=0,
            )
        logger.info(
            "wechat_msg_sec_check_review_pass",
            suggest=suggest,
            label=label,
        )
        return TextCheckResult(
            passed=True,
            reason="审核建议人工复核（已放行）",
            suggest=suggest,
            label=label,
            errcode=0,
        )

    return TextCheckResult(passed=True, suggest=suggest, label=label, errcode=0)
