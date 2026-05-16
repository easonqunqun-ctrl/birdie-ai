"""通用响应模型，对齐 docs/02-API接口设计文档.md 中的统一响应格式."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一成功响应：{ code, message, data }."""

    code: int = 0
    message: str = "success"
    data: T | None = None


class ErrorResponse(BaseModel):
    """统一错误响应."""

    code: int
    message: str
    detail: str | None = None
    request_id: str | None = None


class PageMeta(BaseModel):
    """分页元数据."""

    total: int
    page: int
    page_size: int
    has_more: bool


class PageData(BaseModel, Generic[T]):
    """分页数据载体."""

    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool


class PageQuery(BaseModel):
    """分页查询参数."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


def ok(data: T | None = None, message: str = "success") -> APIResponse[T]:
    """快捷构造成功响应."""
    return APIResponse(code=0, message=message, data=data)


def page_data(items: list[T], total: int, page: int, page_size: int) -> PageData[T]:
    """快捷构造分页数据."""
    return PageData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=page * page_size < total,
    )
