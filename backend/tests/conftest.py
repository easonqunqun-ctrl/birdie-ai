"""共享 pytest 夹具。

说明：
- 使用同进程 ASGITransport 调用 FastAPI 应用，不起额外 HTTP 服务。
- 依赖真实的 Postgres / Redis（容器内跑 `make backend-test` 时 host 走容器网络；
  宿主机直接跑需保证 5432/6379 已映射）。
- 每个测试用唯一 `code` 确保生成的 mock openid 不冲突（mock 模式下 code→openid
  是稳定哈希映射），避免测试间相互污染。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.integrations.llm import FakeLLMClient
from app.integrations.minio import get_minio_storage
from app.main import app
from tests.fakes import FakeAIEngine, FakeMinioStorage


@pytest.fixture
def fake_minio() -> FakeMinioStorage:
    """为每个测试返回一个独立的 FakeMinio。依赖测试自行在 app 上 override。"""
    return FakeMinioStorage()


@pytest.fixture
def fake_ai_engine() -> FakeAIEngine:
    """每个测试独立的 FakeAIEngine；测试用 `fake_ai_engine.set_mode(...)` 控制行为。"""
    return FakeAIEngine()


@pytest.fixture(autouse=True)
def _skip_celery_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认拦截 `_dispatch_analysis_task`，避免测试去真连 Celery broker。

    autouse 是为了让未显式声明该 fixture 的测试（如 M2-T1 的 lifecycle 测试）也受益，
    否则 POST /analyses 会尝试走 celery，Redis DB 1 上会堆起脏任务。
    """
    from app.services import analysis_service

    monkeypatch.setattr(analysis_service, "_dispatch_analysis_task", lambda _aid: None)


@pytest.fixture
def use_fake_ai_engine(
    monkeypatch: pytest.MonkeyPatch, fake_ai_engine: FakeAIEngine
) -> FakeAIEngine:
    """把 `get_ai_engine()` 替换成返回 FakeAIEngine，供 T2 的 _run_swing_analysis_async 使用。"""
    from app.tasks import analysis_tasks as tasks_mod

    monkeypatch.setattr(tasks_mod, "get_ai_engine", lambda: fake_ai_engine)
    return fake_ai_engine


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    """每个测试独立的 FakeLLMClient；配合 `use_fake_llm` fixture 注入。"""
    return FakeLLMClient()


@pytest.fixture(autouse=True)
def _autouse_fake_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认拦截 `get_llm_client()` → 返回一个 FakeLLMClient。

    autouse 是为了让 M3 之前写的测试（比如 T1 chat_lifecycle）即便误走到 LLM 路径
    也不会去真连 DeepSeek；M3 之后流式测试会显式用 `use_fake_llm` 拿到同一个实例。
    """
    from app.integrations import llm as llm_mod
    from app.services import chat_service as chat_svc

    # 每次测试重置；不复用全局单例
    default = FakeLLMClient()
    factory = lambda: default  # noqa: E731
    monkeypatch.setattr(llm_mod, "get_llm_client", factory)
    # chat_service 用 `from ... import get_llm_client` 绑定了本地 name，也要 patch
    monkeypatch.setattr(chat_svc, "get_llm_client", factory)


@pytest.fixture
def use_fake_llm(
    monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLMClient
) -> FakeLLMClient:
    """显式注入一个测试可控的 FakeLLM；覆盖 `_autouse_fake_llm`。

    用法：
        def test_xxx(use_fake_llm: FakeLLMClient, client):
            use_fake_llm.set_mode("timeout")
            ...
    """
    from app.integrations import llm as llm_mod
    from app.services import chat_service as chat_svc

    factory = lambda: fake_llm  # noqa: E731
    monkeypatch.setattr(llm_mod, "get_llm_client", factory)
    monkeypatch.setattr(chat_svc, "get_llm_client", factory)
    return fake_llm


@pytest_asyncio.fixture
async def client(fake_minio: FakeMinioStorage) -> AsyncIterator[AsyncClient]:
    """绑定 FastAPI ASGI 的 httpx 客户端，并把 MinIO 替身注入 FastAPI 依赖图。"""
    app.dependency_overrides[get_minio_storage] = lambda: fake_minio
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_minio_storage, None)


@pytest.fixture
def fresh_code() -> str:
    """生成本次测试独占的 mock 登录 code（每次都唯一）."""
    return f"pytest_{uuid.uuid4().hex}"


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, fresh_code: str) -> dict[str, str]:
    """以一个新 mock 用户登录，返回携带 Bearer Token 的请求头."""
    resp = await client.post("/v1/auth/wechat-login", json={"code": fresh_code})
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}
