"""LLM 多模型路由：任务级路由、超时/失败降级、调用日志（Day 7）。

路由规则：
- 每个任务（chat / nl2sql / report）按 `LLM_ROUTE_*` 顺序尝试提供者；
- 未配置 API Key 的提供者自动跳过；
- 连接失败/超时/空响应时切到下一个提供者；
- 全部失败后降级为 mock，保证接口始终可用；
- 每次真实调用写入 model_call_log（失败也写），用于成本与降级分析。
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

from app.config import settings

logger = logging.getLogger(__name__)

MOCK_PROVIDER = "mock"

# 单价：美元 / 1K tokens（输入，输出），用于成本估算
_PROVIDER_COSTS: dict[str, tuple[float, float]] = {
    "deepseek": (0.00027, 0.0011),
    "qwen": (0.0008, 0.0020),
    "openai": (0.00015, 0.0006),
    "ollama": (0.0, 0.0),
}


def estimate_tokens(text: str) -> int:
    """粗略估算 token：中文约 2 字符/token，英文约 4 字符/token。"""
    if not text:
        return 0
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    others = len(text) - cjk
    return max(1, cjk // 2 + others // 4)


@dataclass
class ProviderSpec:
    name: str
    api_key: str
    base_url: str
    model: str

    @property
    def configured(self) -> bool:
        # Ollama 是本地服务，不需要 Key
        return bool(self.api_key) or self.name == "ollama"


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    first_token_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    degraded: bool = False
    fallback_from: Optional[str] = None
    attempts: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "first_token_ms": self.first_token_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "tokens": self.prompt_tokens + self.completion_tokens,
            "cost": round(self.cost, 6),
            "degraded": self.degraded,
            "fallback_from": self.fallback_from,
            "attempts": self.attempts,
        }


def _with_context(messages: list[dict], context: str) -> list[dict]:
    """把检索上下文注入 system 消息，保证真实模型基于文档作答。"""
    if not context:
        return messages
    block = (
        "\n\n参考资料：\n"
        f"{context}\n\n"
        "请优先依据以上参考资料回答，并标注引用的文档；资料不足时明确说明。"
    )
    merged = [dict(m) for m in messages]
    for i, msg in enumerate(merged):
        if msg.get("role") == "system":
            merged[i]["content"] = f"{msg.get('content', '')}{block}"
            return merged
    return [{"role": "system", "content": block.strip()}] + merged


class OpenAICompatProvider:
    """OpenAI 兼容接口（DeepSeek / Qwen / GPT / Ollama 均适用）。"""

    def __init__(self, spec: ProviderSpec) -> None:
        self.spec = spec

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def model(self) -> str:
        return self.spec.model

    @property
    def configured(self) -> bool:
        return self.spec.configured

    def _client(self):
        from openai import AsyncOpenAI  # type: ignore

        return AsyncOpenAI(
            api_key=self.spec.api_key or "ollama",
            base_url=self.spec.base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )

    async def chat(self, messages: list[dict], temperature: float = 0.0) -> str:
        resp = await self._client().chat.completions.create(
            model=self.spec.model,
            messages=messages,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()

    async def chat_stream(
        self, messages: list[dict], temperature: float = 0.0
    ) -> AsyncGenerator[str, None]:
        stream = await self._client().chat.completions.create(
            model=self.spec.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content


class ModelRouter:
    """按任务选择模型，失败自动降级，并记录调用日志。"""

    def __init__(
        self,
        providers: Optional[dict[str, object]] = None,
        routes: Optional[dict[str, list[str]]] = None,
        timeout: Optional[float] = None,
        stream_idle_timeout: Optional[float] = None,
        log_to_db: Optional[bool] = None,
    ) -> None:
        self._providers = providers if providers is not None else self._build_default_providers()
        self._timeout = timeout if timeout is not None else settings.llm_timeout_seconds
        self._stream_idle_timeout = (
            stream_idle_timeout
            if stream_idle_timeout is not None
            else settings.llm_stream_idle_timeout
        )
        self._log_to_db = settings.llm_log_to_db if log_to_db is None else log_to_db
        self._default_routes = self._parse_routes(routes)
        self._routes = {k: list(v) for k, v in self._default_routes.items()}
        self._traces: dict[str, dict] = {}
        self._trace_order: deque[str] = deque(maxlen=200)
        self._memory_logs: deque[dict] = deque(maxlen=200)

        if self.mock_mode:
            logger.warning("未配置任何模型 API Key，当前全部任务使用 mock 模式")

    # ---------- 初始化 ----------
    @staticmethod
    def _build_default_providers() -> dict[str, OpenAICompatProvider]:
        specs = [
            ProviderSpec("deepseek", settings.deepseek_api_key,
                         settings.deepseek_base_url, settings.deepseek_model),
            ProviderSpec("qwen", settings.qwen_api_key,
                         settings.qwen_base_url, settings.qwen_model),
            ProviderSpec("openai", settings.openai_api_key,
                         settings.openai_base_url, settings.openai_model),
            ProviderSpec("ollama", "ollama",
                         settings.ollama_base_url, settings.ollama_model),
        ]
        return {s.name: OpenAICompatProvider(s) for s in specs}

    @staticmethod
    def _parse_routes(routes: Optional[dict[str, list[str]]]) -> dict[str, list[str]]:
        if routes is not None:
            return {task: [p.strip().lower() for p in names if p and p.strip()]
                    for task, names in routes.items()}
        return {
            "chat": _split_names(settings.llm_route_chat),
            "nl2sql": _split_names(settings.llm_route_nl2sql),
            "report": _split_names(settings.llm_route_report),
        }

    # ---------- 状态 ----------
    @property
    def mock_mode(self) -> bool:
        """所有任务的路由中都没有可用的真实提供者时为 mock 模式。"""
        names = {name for route in self._routes.values() for name in route}
        return not any(
            name in self._providers and self._providers[name].configured  # type: ignore[attr-defined]
            for name in names
        )

    def has_real_provider(self, task: str) -> bool:
        """该任务的路由中是否存在已配置的真实提供者。"""
        return any(
            name != MOCK_PROVIDER
            and name in self._providers
            and self._providers[name].configured  # type: ignore[attr-defined]
            for name in self.route_for(task)
        )

    @property
    def provider_names(self) -> list[str]:
        return list(self._providers.keys())

    def route_for(self, task: str) -> list[str]:
        return list(self._routes.get(task, self._routes.get("chat", [])))

    def set_route(self, task: str, names: list[str]) -> list[str]:
        """运行时切换路由（内存级，重启后回到环境变量配置）。"""
        allowed = set(self._providers.keys()) | {MOCK_PROVIDER}
        cleaned = [n.strip().lower() for n in names if n and n.strip()]
        invalid = [n for n in cleaned if n not in allowed]
        if invalid:
            raise ValueError(f"未知模型提供者: {', '.join(invalid)}")
        if not cleaned:
            raise ValueError("路由不能为空")
        self._routes[task] = cleaned
        logger.info("模型路由切换: task=%s -> %s", task, cleaned)
        return cleaned

    def reset_routes(self) -> dict[str, list[str]]:
        self._routes = {k: list(v) for k, v in self._default_routes.items()}
        return self.describe()["routes"]

    def describe(self) -> dict:
        providers = []
        for name, provider in self._providers.items():
            spec = provider.spec  # type: ignore[attr-defined]
            providers.append({
                "name": name,
                "model": spec.model,
                "base_url": spec.base_url,
                "configured": spec.configured,
                "api_key": _mask_key(spec.api_key) if name != "ollama" else "(local)",
            })
        return {
            "mock_mode": self.mock_mode,
            "timeout_seconds": self._timeout,
            "stream_idle_timeout": self._stream_idle_timeout,
            "routes": {task: list(names) for task, names in self._routes.items()},
            "providers": providers,
            "log_to_db": self._log_to_db,
        }

    def get_trace(self, trace_id: str) -> Optional[dict]:
        return self._traces.get(trace_id)

    def recent_logs(self, limit: int = 20) -> list[dict]:
        return list(self._memory_logs)[-limit:][::-1]

    # ---------- 调用 ----------
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        task: str = "nl2sql",
        tenant_id: str = "",
        trace_id: str = "",
    ) -> str:
        """非流式调用，保持原接口返回 str。"""
        result = await self.chat_result(messages, temperature, task, tenant_id, trace_id)
        return result.text

    async def chat_result(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        task: str = "nl2sql",
        tenant_id: str = "",
        trace_id: str = "",
    ) -> LLMResult:
        trace_id = trace_id or uuid.uuid4().hex
        attempts: list[dict] = []
        started = time.perf_counter()
        prompt_tokens = _prompt_tokens(messages)

        for name in self.route_for(task):
            if name == MOCK_PROVIDER:
                break
            provider = self._providers.get(name)
            if provider is None or not provider.configured:
                continue

            attempt_started = time.perf_counter()
            try:
                text = await asyncio.wait_for(
                    provider.chat(messages, temperature), timeout=self._timeout  # type: ignore[attr-defined]
                )
                if not (text or "").strip():
                    raise RuntimeError("模型返回空响应")
            except Exception as exc:
                latency = _elapsed_ms(attempt_started)
                error = _describe_error(exc, self._timeout)
                logger.warning("模型调用失败，准备降级: provider=%s task=%s error=%s",
                               name, task, error)
                attempts.append(_attempt(name, "failed", latency, error))
                # 失败调用仍会消耗输入 tokens，按输入单价计入成本
                await self._record(
                    tenant_id=tenant_id, provider=name, model=provider.model,  # type: ignore[attr-defined]
                    task_type=task, trace_id=trace_id, tokens=prompt_tokens,
                    latency_ms=latency, first_token_ms=0,
                    cost=_calc_cost(name, prompt_tokens, 0),
                    status="failed", error=error,
                )
                continue

            latency = _elapsed_ms(started)
            completion_tokens = estimate_tokens(text)
            cost = _calc_cost(name, prompt_tokens, completion_tokens)
            fallback_from = attempts[-1]["provider"] if attempts else None
            attempts.append(_attempt(name, "success", _elapsed_ms(attempt_started), None))
            result = LLMResult(
                text=text, provider=name, model=provider.model,  # type: ignore[attr-defined]
                latency_ms=latency, prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens, cost=cost,
                degraded=bool(fallback_from), fallback_from=fallback_from,
                attempts=attempts,
            )
            await self._record(
                tenant_id=tenant_id, provider=name, model=result.model,
                task_type=task, trace_id=trace_id,
                tokens=result.prompt_tokens + result.completion_tokens,
                latency_ms=latency, first_token_ms=0, cost=cost,
                status="degraded" if result.degraded else "success",
                error=_last_error(attempts[:-1]),
                fallback_from=fallback_from,
            )
            self._remember_trace(trace_id, result)
            return result

        # 全部失败或未配置：mock 兜底
        text = self._mock_text(messages, context="")
        fallback_from = attempts[-1]["provider"] if attempts else None
        result = LLMResult(
            text=text, provider=MOCK_PROVIDER, model="mock",
            latency_ms=_elapsed_ms(started), degraded=bool(attempts),
            fallback_from=fallback_from, attempts=attempts,
        )
        await self._record(
            tenant_id=tenant_id, provider=MOCK_PROVIDER, model="mock",
            task_type=task, trace_id=trace_id, tokens=estimate_tokens(text),
            latency_ms=result.latency_ms, first_token_ms=0, cost=0.0,
            status="degraded" if attempts else "mock",
            error=_last_error(attempts), fallback_from=fallback_from,
        )
        self._remember_trace(trace_id, result)
        return result

    async def chat_stream(
        self,
        messages: list[dict],
        context: str = "",
        task: str = "chat",
        tenant_id: str = "",
        trace_id: str = "",
    ) -> AsyncGenerator[str, None]:
        """流式调用；首个 token 前失败可降级，已输出后中断则提示重试。"""
        trace_id = trace_id or uuid.uuid4().hex
        attempts: list[dict] = []
        started = time.perf_counter()
        prompt_tokens = _prompt_tokens(messages)

        for name in self.route_for(task):
            if name == MOCK_PROVIDER:
                break
            provider = self._providers.get(name)
            if provider is None or not provider.configured:
                continue

            attempt_started = time.perf_counter()
            emitted = 0
            first_token_ms = 0
            full_text = ""
            stream = None
            try:
                stream = provider.chat_stream(  # type: ignore[attr-defined]
                    _with_context(messages, context), temperature=0.0
                )
                while True:
                    chunk = await asyncio.wait_for(
                        anext(stream), timeout=self._stream_idle_timeout
                    )
                    if emitted == 0:
                        first_token_ms = _elapsed_ms(attempt_started)
                    emitted += 1
                    full_text += chunk
                    yield chunk
            except StopAsyncIteration:
                pass
            except Exception as exc:
                latency = _elapsed_ms(attempt_started)
                error = _describe_error(exc, self._stream_idle_timeout)
                completion_tokens = estimate_tokens(full_text)
                logger.warning("流式模型失败: provider=%s task=%s emitted=%d error=%s",
                               name, task, emitted, error)
                attempts.append(_attempt(name, "truncated" if emitted else "failed",
                                         latency, error))
                await self._record(
                    tenant_id=tenant_id, provider=name, model=provider.model,  # type: ignore[attr-defined]
                    task_type=task, trace_id=trace_id,
                    tokens=prompt_tokens + completion_tokens, latency_ms=latency,
                    first_token_ms=first_token_ms,
                    cost=_calc_cost(name, prompt_tokens, completion_tokens),
                    status="truncated" if emitted else "failed", error=error,
                )
                if stream is not None:
                    await stream.aclose()  # type: ignore[attr-defined]
                if emitted:
                    yield "\n\n[模型连接中断，回答可能不完整，请重试]"
                    self._remember_trace(trace_id, LLMResult(
                        text=full_text, provider=name, model=provider.model,  # type: ignore[attr-defined]
                        latency_ms=latency, first_token_ms=first_token_ms,
                        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                        cost=_calc_cost(name, prompt_tokens, completion_tokens),
                        degraded=True, attempts=attempts,
                    ))
                    return
                continue

            latency = _elapsed_ms(started)
            completion_tokens = estimate_tokens(full_text)
            cost = _calc_cost(name, prompt_tokens, completion_tokens)
            fallback_from = attempts[-1]["provider"] if attempts else None
            attempts.append(_attempt(name, "success", _elapsed_ms(attempt_started), None))
            result = LLMResult(
                text=full_text, provider=name, model=provider.model,  # type: ignore[attr-defined]
                latency_ms=latency, first_token_ms=first_token_ms,
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                cost=cost, degraded=bool(fallback_from), fallback_from=fallback_from,
                attempts=attempts,
            )
            await self._record(
                tenant_id=tenant_id, provider=name, model=result.model,
                task_type=task, trace_id=trace_id,
                tokens=result.prompt_tokens + result.completion_tokens,
                latency_ms=latency, first_token_ms=first_token_ms, cost=cost,
                status="degraded" if result.degraded else "success",
                error=_last_error(attempts[:-1]), fallback_from=fallback_from,
            )
            self._remember_trace(trace_id, result)
            return

        text = self._mock_text(messages, context)
        fallback_from = attempts[-1]["provider"] if attempts else None
        result = LLMResult(
            text=text, provider=MOCK_PROVIDER, model="mock",
            latency_ms=_elapsed_ms(started), degraded=bool(attempts),
            fallback_from=fallback_from, attempts=attempts,
        )
        await self._record(
            tenant_id=tenant_id, provider=MOCK_PROVIDER, model="mock",
            task_type=task, trace_id=trace_id, tokens=estimate_tokens(text),
            latency_ms=result.latency_ms, first_token_ms=0, cost=0.0,
            status="degraded" if attempts else "mock", error=_last_error(attempts),
            fallback_from=fallback_from,
        )
        self._remember_trace(trace_id, result)
        for char in text:
            yield char

    # ---------- 视觉模型（保持原能力）----------
    @property
    def vision_available(self) -> bool:
        return bool(settings.openai_api_key)

    async def vision_describe(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        if not self.vision_available:
            return ""
        try:
            import base64

            from openai import AsyncOpenAI  # type: ignore

            client = AsyncOpenAI(api_key=settings.openai_api_key,
                                 timeout=self._timeout, max_retries=0)
            b64 = base64.b64encode(image_bytes).decode()
            resp = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text",
                         "text": "请提取图片中的全部文字（保持阅读顺序）；若没有文字，请简要描述图片内容。"},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                    ],
                }],
                temperature=0,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            logger.exception("视觉模型调用失败")
            return ""

    # ---------- 内部 ----------
    def _remember_trace(self, trace_id: str, result: LLMResult) -> None:
        self._traces[trace_id] = {
            "trace_id": trace_id,
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "first_token_ms": result.first_token_ms,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "cost": round(result.cost, 6),
            "degraded": result.degraded,
            "fallback_from": result.fallback_from,
            "attempts": result.attempts,
        }
        if trace_id not in self._trace_order:
            if len(self._trace_order) == self._trace_order.maxlen:
                oldest = self._trace_order[0]
                self._traces.pop(oldest, None)
            self._trace_order.append(trace_id)

    async def _record(self, **payload) -> None:
        """记录调用日志：优先落库，失败时保留在内存环形缓冲。"""
        entry = {**payload, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        self._memory_logs.append(entry)
        if not self._log_to_db:
            return
        try:
            await asyncio.to_thread(self._write_log_sync, payload)
        except Exception as exc:  # 数据库不可用时不影响主链路
            logger.debug("model_call_log 写入失败: %s", exc)

    @staticmethod
    def _write_log_sync(payload: dict) -> None:
        import psycopg

        with psycopg.connect(settings.postgres_dsn, connect_timeout=2) as conn:
            conn.execute(
                """
                INSERT INTO model_call_log
                    (tenant_id, provider, model, task_type, trace_id, tokens,
                     latency_ms, first_token_ms, cost, status, error, fallback_from)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.get("tenant_id") or "system",
                    payload.get("provider"),
                    payload.get("model"),
                    payload.get("task_type"),
                    payload.get("trace_id"),
                    int(payload.get("tokens") or 0),
                    int(payload.get("latency_ms") or 0),
                    int(payload.get("first_token_ms") or 0),
                    float(payload.get("cost") or 0),
                    payload.get("status") or "success",
                    payload.get("error"),
                    payload.get("fallback_from"),
                ),
            )
            conn.commit()

    @staticmethod
    def _mock_text(messages: list[dict], context: str) -> str:
        user_msg = messages[-1]["content"] if messages else ""
        if context:
            return (
                f"[Mock 降级模式] 基于以下文档片段回答：\n\n"
                f"{context[:500]}\n\n"
                f"用户问题：{user_msg}\n\n"
                f"（未配置可用模型 Key，或所有模型调用失败后自动降级）"
            )
        return (
            f"[Mock 降级模式] 未获取到模型回答。\n"
            f"用户问题：{user_msg}\n\n"
            f"（请上传文档或配置 LLM API Key；当前路由全部失败时自动降级）"
        )


def _split_names(value: str) -> list[str]:
    return [n.strip().lower() for n in value.split(",") if n.strip()]


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _prompt_tokens(messages: list[dict]) -> int:
    return estimate_tokens("".join(m.get("content", "") for m in messages))


def _calc_cost(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_cost, output_cost = _PROVIDER_COSTS.get(provider, (0.0, 0.0))
    return (prompt_tokens / 1000) * input_cost + (completion_tokens / 1000) * output_cost


def _describe_error(exc: BaseException, timeout: Optional[float] = None) -> str:
    """把异常转成可读错误：超时显式标注超时阈值，避免日志里出现空错误。"""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return f"超时（超过 {timeout:g}s）" if timeout else "超时"
    text = str(exc).strip()
    return text or exc.__class__.__name__


def _attempt(name: str, status: str, latency_ms: int, error: Optional[str]) -> dict:
    return {"provider": name, "status": status, "latency_ms": latency_ms, "error": error}


def _last_error(attempts: list[dict]) -> Optional[str]:
    for item in reversed(attempts):
        if item.get("error"):
            return f"{item['provider']}: {item['error']}"
    return None


llm = ModelRouter()
