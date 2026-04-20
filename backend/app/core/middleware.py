"""HTTP 中间件：请求日志、请求 ID、统一异常处理.

实现采用「纯 ASGI 中间件」而不是 `BaseHTTPMiddleware`，原因：
- `BaseHTTPMiddleware` 会把 `call_next` 派发到独立的 AnyIO task，在同一进程内
  与 asyncpg/SQLAlchemy 的异步连接池配合时容易触发
  `got Future attached to a different loop`（尤其在测试/ASGI 直连场景）。
- 纯 ASGI 中间件层更轻、性能更好，也是 Starlette 官方推荐的做法。
"""

import time
import uuid

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger("http")


class RequestContextMiddleware:
    """注入 request_id 并记录访问日志（纯 ASGI 实现）."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        request_id = headers.get("x-request-id") or uuid.uuid4().hex[:16]

        # 暴露给下游：request.state.request_id
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        start = time.perf_counter()
        status_holder: dict[str, int] = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                raw_headers = list(message.get("headers") or [])
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(
                "request_failed",
                request_id=request_id,
                method=scope.get("method"),
                path=scope.get("path"),
                duration_ms=duration_ms,
                error=str(e),
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "request",
            request_id=request_id,
            method=scope.get("method"),
            path=scope.get("path"),
            status=status_holder["code"],
            duration_ms=duration_ms,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，统一响应格式."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": 50001,
                "message": "服务内部错误",
                "detail": str(exc) if request.app.debug else None,
            },
        )
