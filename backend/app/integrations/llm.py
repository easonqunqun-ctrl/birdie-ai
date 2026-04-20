"""LLM 客户端抽象（OpenAI 兼容） + Fake 实现.

设计目标
--------
1. **对业务透明**：`chat_service` 只依赖 `AbstractLLMClient.stream_chat(messages) -> AsyncIterator[LLMChunk]`，
   线上（DeepSeek / Qwen / GLM / OpenAI）和测试（FakeLLM）走同一份代码。
2. **故障可控**：`FakeLLMClient.set_mode("timeout" | "error" | "ok" | "slow")` 模拟不同失败，
   测试里复现"LLM 超时应退配额"等场景时不依赖外网。
3. **流式**：返回异步迭代器，每个 chunk 是一小段 delta；业务层做 SSE 序列化。
4. **OpenAI 兼容但收敛**：只用 `chat/completions` + `stream=true`；不做 function-calling（W6 再说），
   不做 tool-choice；不做 JSON mode。drill_card 附件用启发式关键词匹配（见 chat_service）。

依赖的是 httpx（项目里已有）；**不引入 openai SDK**，避免再锁死一套依赖版本，
也避免官方 SDK 对非 OpenAI 的 DeepSeek 出现 tokenizer/endpoint 的兼容问题。
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from typing import Any, Literal

import httpx
import structlog

from app.config import settings

log = structlog.get_logger("integrations.llm")


# ==================== 数据结构 ====================
@dataclass
class LLMChunk:
    """LLM 流式返回的单个增量。

    - `type="content"`：`delta` 是本次新增的文本片段
    - `type="done"`：流结束；`usage` 可能含 prompt_tokens / completion_tokens（非所有供应商都返回）
    - `type="error"`：底层出错；`delta` 为空，`error` 描述原因
    """

    type: Literal["content", "done", "error"]
    delta: str = ""
    usage: dict[str, int] | None = None
    error: str | None = None


Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": "..."}


# ==================== 抽象基类 ====================
class AbstractLLMClient(ABC):
    """所有 LLM 客户端需实现的接口."""

    @abstractmethod
    def stream_chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """流式发送 messages 并 yield LLMChunk。

        注意：实现里建议**整个方法体都在 async generator 里**，外层直接 `async for` 消费；
        返回 coroutine 再取 iterator 会多一层绕。
        """
        raise NotImplementedError


# ==================== 真实 LLM（OpenAI 兼容） ====================
class OpenAICompatibleClient(AbstractLLMClient):
    """打 OpenAI 兼容的 /chat/completions 接口."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.timeout = timeout_seconds if timeout_seconds is not None else float(settings.LLM_TIMEOUT_SECONDS)

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        url = f"{self.base_url}/chat/completions"
        log.info("llm_call_start", model=self.model, msg_count=len(messages))

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout) as http_client,
                http_client.stream("POST", url, json=payload, headers=headers) as resp,
            ):
                resp.raise_for_status()
                async for chunk in self._iter_openai_sse(resp):
                    yield chunk
        except httpx.TimeoutException as exc:
            log.warning("llm_call_timeout", model=self.model, error=str(exc))
            yield LLMChunk(type="error", error=f"LLM 超时: {exc}")
        except httpx.HTTPStatusError as exc:
            log.warning("llm_call_http_error", model=self.model, status=exc.response.status_code)
            yield LLMChunk(type="error", error=f"LLM HTTP {exc.response.status_code}")
        except Exception as exc:
            log.exception("llm_call_failed", model=self.model)
            yield LLMChunk(type="error", error=f"LLM 调用失败: {exc}")

    async def _iter_openai_sse(
        self, resp: httpx.Response
    ) -> AsyncIterator[LLMChunk]:
        """解析 OpenAI-style SSE：`data: {json}\\n\\n`，终止符 `data: [DONE]`."""
        usage: dict[str, int] | None = None
        async for line in resp.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            # choices[0].delta.content 可能是 None / 空 / 文本
            delta = (
                data.get("choices", [{}])[0]
                .get("delta", {})
                .get("content")
            )
            if delta:
                yield LLMChunk(type="content", delta=delta)
            # DeepSeek / OpenAI 最后一个 chunk 可能带 usage（取决于 stream_options）
            if data.get("usage"):
                usage = data["usage"]
        yield LLMChunk(type="done", usage=usage)


# ==================== Fake（无 API key / 测试） ====================
class FakeLLMClient(AbstractLLMClient):
    """测试替身 & 无 API key 的本地联调替身.

    - `set_mode("ok")`：按字符 yield 回复文本，每 chunk 50ms，模拟"逐字打字"
    - `set_mode("timeout")`：yield 第 0 个 chunk 后 yield error（不做真的 asyncio.sleep(999)，
      避免测试卡住；语义上等价于"流中超时"）
    - `set_mode("error", message=...)`：直接 yield error chunk
    - `set_mode("slow", delay_per_chunk=0.1)`：真的慢，测 FE 打字节奏
    - `set_reply(...)`：测试里指定"下一次 stream_chat 返回什么文本"；不设置则用默认模板
    - `calls` 记录每次调用的 messages 参数，供测试断言 system prompt 注入
    """

    def __init__(self) -> None:
        self.mode: Literal["ok", "timeout", "error", "slow"] = "ok"
        self.reply_text: str = (
            "好的，我帮你看看。你描述的情况在业余球手里很常见，建议先从髋部旋转开始练起。"
        )
        self.chunk_size: int = 8  # ok/slow 模式下每 chunk 多少字符
        self.delay_per_chunk: float = 0.0  # ok 模式 0，slow 模式 > 0
        self.error_message: str = "LLM 调用失败（mock）"
        self.calls: list[dict[str, Any]] = []

    def set_mode(
        self,
        mode: Literal["ok", "timeout", "error", "slow"],
        *,
        error_message: str = "LLM 调用失败（mock）",
        delay_per_chunk: float = 0.1,
    ) -> None:
        self.mode = mode
        self.error_message = error_message
        self.delay_per_chunk = delay_per_chunk if mode == "slow" else 0.0

    def set_reply(self, text: str, *, chunk_size: int = 8) -> None:
        self.reply_text = text
        self.chunk_size = chunk_size

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        self.calls.append(
            {
                "messages": [dict(m) for m in messages],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.mode == "error":
            yield LLMChunk(type="error", error=self.error_message)
            return
        if self.mode == "timeout":
            # 先吐一小段，再以 error 终止——模拟"流中超时"
            yield LLMChunk(type="content", delta=self.reply_text[:4])
            yield LLMChunk(type="error", error="LLM 超时（mock）")
            return

        # ok / slow
        for chunk in _chunk_string(self.reply_text, self.chunk_size):
            if self.delay_per_chunk > 0:
                await asyncio.sleep(self.delay_per_chunk)
            yield LLMChunk(type="content", delta=chunk)
        yield LLMChunk(
            type="done",
            usage={
                # 简单估计：按字符数 / 4 作为 token 数占位；测试只断言 >0
                "prompt_tokens": max(1, sum(len(m["content"]) for m in messages) // 4),
                "completion_tokens": max(1, len(self.reply_text) // 4),
            },
        )


def _chunk_string(text: str, size: int) -> Iterable[str]:
    for i in range(0, len(text), size):
        yield text[i : i + size]


# ==================== 工厂函数 ====================
_default_client: AbstractLLMClient | None = None


def _is_placeholder_key(key: str) -> bool:
    """识别 `.env.example` 里常见的占位 key，避免它们被误当成真实凭证去打外网."""
    if not key:
        return True
    lowered = key.lower()
    return any(
        marker in lowered
        for marker in ("placeholder", "change-me", "your-key", "xxx", "todo")
    )


def get_llm_client() -> AbstractLLMClient:
    """按配置选择客户端。

    FakeLLM 启用条件（任一满足）：
    - `LLM_MOCK_MODE=true` 强制开
    - `LLM_API_KEY` 为空或匹配占位模式（本地/测试默认，自动降级）

    供测试 monkeypatch 该工厂函数的返回值。
    """
    global _default_client
    if _default_client is None:
        if settings.LLM_MOCK_MODE or _is_placeholder_key(settings.LLM_API_KEY):
            log.info("llm_client_init", impl="FakeLLMClient")
            _default_client = FakeLLMClient()
        else:
            log.info(
                "llm_client_init",
                impl="OpenAICompatibleClient",
                model=settings.LLM_MODEL,
                base_url=settings.LLM_BASE_URL,
            )
            _default_client = OpenAICompatibleClient()
    return _default_client


def reset_llm_client() -> None:
    """测试/热重载用."""
    global _default_client
    _default_client = None
