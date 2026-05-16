"""自定义异常体系，对齐 docs/02-API接口设计文档.md 的错误码规范."""

from __future__ import annotations


class AppException(Exception):  # noqa: N818 - 保留历史命名；具体子类均遵循 *Error 后缀
    """业务异常基类。code 对应文档错误码，http_status 对应 HTTP 状态码."""

    code: int = 50001
    http_status: int = 500
    message: str = "服务内部错误"

    def __init__(
        self,
        code: int | None = None,
        message: str | None = None,
        detail: str | None = None,
        http_status: int | None = None,
    ) -> None:
        if code is not None:
            self.code = code
        if message is not None:
            self.message = message
        if http_status is not None:
            self.http_status = http_status
        self.detail = detail
        super().__init__(self.message)


# ==================== 4xx 错误 ====================
class BadRequestError(AppException):
    code = 40001
    http_status = 400
    message = "参数错误"


class UnauthorizedError(AppException):
    code = 40101
    http_status = 401
    message = "Token 缺失"


class ForbiddenError(AppException):
    code = 40301
    http_status = 403
    message = "无权限"


class NotFoundError(AppException):
    code = 40401
    http_status = 404
    message = "资源不存在"


class TooManyRequestsError(AppException):
    code = 42901
    http_status = 429
    message = "请求过于频繁"


class QuotaExceededError(AppException):
    code = 40006
    http_status = 403
    message = "配额已用完"


class UploadTokenInvalidError(AppException):
    """上传凭证无效/过期/被他人占用（`upload_id` 语义失败）."""

    code = 40011
    http_status = 400
    message = "上传凭证无效或已过期"


class UploadObjectMissingError(AppException):
    """视频对象未上传到对象存储（前端拿了凭证但没传完）."""

    code = 40012
    http_status = 400
    message = "视频对象不存在，请先完成上传"


class ChatQuotaExhaustedError(AppException):
    """今日 AI 对话轮次已用完（M3-T1）."""

    code = 40007
    http_status = 403
    message = "今日对话次数已达上限"


class RateLimitError(AppException):
    """用户维度的速率限制命中（比 `TooManyRequestsError` 语义更聚焦业务轮次）.

    注意：M3 设计文档里 40009 专用于"对话发送过快"。框架级通用 429 仍用 42901。
    """

    code = 40009
    http_status = 429
    message = "操作过于频繁，请稍后再试"


class ConflictError(AppException):
    """资源状态冲突（如分析尚未完成就去取报告）."""

    code = 40904
    http_status = 409
    message = "资源状态不允许本次操作"


class AnalysisDispatchError(AppException):
    """挥杆分析任务已落库，但 Celery / Redis broker 入队失败（用户应稍后重试或由运维补偿调度）."""

    code = 50301
    http_status = 503
    message = "分析任务暂时无法排队，请稍后重试"


# ==================== 5xx 错误 ====================
class InternalError(AppException):
    code = 50001
    http_status = 500
    message = "服务内部错误"


class AIEngineError(AppException):
    code = 50101
    http_status = 502
    message = "AI 引擎错误"


class ThirdPartyError(AppException):
    code = 50201
    http_status = 502
    message = "第三方服务异常"


class AIChatServiceError(AppException):
    """LLM 服务不可用（超时 / HTTP 错误 / 流中断）.

    不用 `ThirdPartyError(50201)` 是因为对话场景希望前端**单独**处理 50106：
    例如"AI 教练暂时开小差了，请稍后重试"，而不是通用的"服务异常"。
    """

    code = 50106
    http_status = 502
    message = "AI 对话服务暂时不可用"
