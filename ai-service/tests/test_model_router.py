"""多模型路由 / 降级 / 运行时切换的单元测试。"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.llm.providers import MOCK_PROVIDER, ModelRouter


class FakeProvider:
    def __init__(self, name: str, reply: str = "ok", error: str | None = None,
                 delay: float = 0.0, configured: bool = True) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.reply = reply
        self.error = error
        self.delay = delay
        self.configured = configured
        self.spec = SimpleNamespace(
            name=name, model=self.model, base_url="http://fake",
            api_key="fake" if configured else "", configured=configured,
        )

    async def _before(self) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise RuntimeError(self.error)

    async def chat(self, messages, temperature: float = 0.0) -> str:
        await self._before()
        return self.reply

    async def chat_stream(self, messages, temperature: float = 0.0):
        await self._before()
        for char in self.reply:
            yield char


class TruncatingProvider(FakeProvider):
    """先输出一个 token，再中断流。"""

    async def chat_stream(self, messages, temperature: float = 0.0):
        yield "你"
        raise RuntimeError("stream broken")


def _messages() -> list[dict]:
    return [{"role": "user", "content": "库存周转情况如何"}]


@pytest.mark.asyncio
async def test_fallback_to_second_provider() -> None:
    router = ModelRouter(
        providers={
            "bad": FakeProvider("bad", error="connection refused"),
            "good": FakeProvider("good", reply="SELECT 1"),
        },
        routes={"nl2sql": ["bad", "good"], "chat": ["good"]},
        log_to_db=False,
    )
    result = await router.chat_result(_messages(), task="nl2sql")
    assert result.text == "SELECT 1"
    assert result.provider == "good"
    assert result.degraded is True
    assert result.fallback_from == "bad"
    assert result.as_dict()["fallback_from"] == "bad"
    assert result.attempts[0]["status"] == "failed"
    assert "connection refused" in (result.attempts[0]["error"] or "")


@pytest.mark.asyncio
async def test_timeout_triggers_fallback() -> None:
    router = ModelRouter(
        providers={
            "slow": FakeProvider("slow", reply="too late", delay=0.3),
            "fast": FakeProvider("fast", reply="quick"),
        },
        routes={"chat": ["slow", "fast"]},
        timeout=0.05,
        log_to_db=False,
    )
    result = await router.chat_result(_messages(), task="chat")
    assert result.provider == "fast"
    assert result.text == "quick"
    assert result.degraded is True
    assert result.fallback_from == "slow"
    assert "超时" in (result.attempts[0]["error"] or "")


@pytest.mark.asyncio
async def test_stream_fallback_before_first_token() -> None:
    router = ModelRouter(
        providers={
            "bad": FakeProvider("bad", error="network down"),
            "good": FakeProvider("good", reply="你好"),
        },
        routes={"chat": ["bad", "good"]},
        log_to_db=False,
    )
    text = "".join([chunk async for chunk in router.chat_stream(_messages(), task="chat")])
    assert text == "你好"
    trace = router.get_trace(next(iter(router._traces)))
    assert trace["provider"] == "good"
    assert trace["degraded"] is True


@pytest.mark.asyncio
async def test_all_failed_degrades_to_mock() -> None:
    router = ModelRouter(
        providers={"bad": FakeProvider("bad", error="offline")},
        routes={"chat": ["bad", "mock"]},
        log_to_db=False,
    )
    result = await router.chat_result(_messages(), task="chat")
    assert result.provider == MOCK_PROVIDER
    assert "Mock 降级模式" in result.text
    assert result.degraded is True
    assert result.fallback_from == "bad"

    log = router.recent_logs(1)[0]
    assert log["provider"] == MOCK_PROVIDER
    assert log["status"] == "degraded"
    assert log["fallback_from"] == "bad"


@pytest.mark.asyncio
async def test_runtime_route_switch() -> None:
    router = ModelRouter(
        providers={
            "a": FakeProvider("a", reply="A"),
            "b": FakeProvider("b", reply="B"),
        },
        routes={"chat": ["a"]},
        log_to_db=False,
    )
    assert (await router.chat_result(_messages(), task="chat")).text == "A"

    router.set_route("chat", ["b"])
    assert router.route_for("chat") == ["b"]
    assert (await router.chat_result(_messages(), task="chat")).text == "B"

    with pytest.raises(ValueError):
        router.set_route("chat", ["not-exists"])

    router.reset_routes()
    assert router.route_for("chat") == ["a"]


@pytest.mark.asyncio
async def test_unconfigured_provider_is_skipped() -> None:
    router = ModelRouter(
        providers={
            "no-key": FakeProvider("no-key", reply="should not use", configured=False),
            "good": FakeProvider("good", reply="used"),
        },
        routes={"chat": ["no-key", "good"]},
        log_to_db=False,
    )
    result = await router.chat_result(_messages(), task="chat")
    assert result.provider == "good"
    assert len(result.attempts) == 1


@pytest.mark.asyncio
async def test_failed_attempt_logs_input_cost_and_success_logs_fallback_from() -> None:
    router = ModelRouter(
        providers={
            "deepseek": FakeProvider("deepseek", error="500 server error"),
            "openai": FakeProvider("openai", reply="SELECT 2"),
        },
        routes={"nl2sql": ["deepseek", "openai"]},
        log_to_db=False,
    )
    result = await router.chat_result(_messages(), task="nl2sql", tenant_id="hospital-demo")

    assert result.degraded is True
    assert result.fallback_from == "deepseek"

    logs = router.recent_logs(2)
    success, failed = logs[0], logs[1]
    # 失败调用仍按输入 tokens 计成本，避免成本统计为 0
    assert failed["provider"] == "deepseek"
    assert failed["status"] == "failed"
    assert failed["tokens"] > 0
    assert failed["cost"] > 0
    # 降级成功的日志要能追溯来源 provider
    assert success["status"] == "degraded"
    assert success["fallback_from"] == "deepseek"
    assert success["tokens"] > 0
    assert success["cost"] > 0
    assert success["tenant_id"] == "hospital-demo"


@pytest.mark.asyncio
async def test_stream_truncation_logs_partial_cost() -> None:
    router = ModelRouter(
        providers={"deepseek": TruncatingProvider("deepseek")},
        routes={"chat": ["deepseek"]},
        log_to_db=False,
    )
    text = "".join([chunk async for chunk in router.chat_stream(_messages(), task="chat")])

    assert text.startswith("你")
    assert "模型连接中断" in text

    log = router.recent_logs(1)[0]
    assert log["provider"] == "deepseek"
    assert log["status"] == "truncated"
    assert log["tokens"] > 0
    assert log["cost"] > 0
    assert "stream broken" in (log["error"] or "")
