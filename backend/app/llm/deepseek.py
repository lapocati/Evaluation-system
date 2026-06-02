"""DeepSeek 官方 API 客户端封装。endpoint 与模型名固定，仅暴露 api_key。"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

import httpx

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"

_RETRYABLE_HTTP = (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)

_http_client: httpx.AsyncClient | None = None


def init_http_client() -> None:
    """创建共享 HTTP 客户端（由 FastAPI lifespan 在启动时调用）。"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
            timeout=httpx.Timeout(120.0, connect=60.0),
        )


async def close_http_client() -> None:
    """关闭共享 HTTP 客户端（由 FastAPI lifespan 在关闭时调用）。"""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


def get_http_client() -> httpx.AsyncClient:
    if _http_client is None:
        init_http_client()
    return _http_client


def _request_timeout(timeout: float) -> httpx.Timeout:
    return httpx.Timeout(timeout, connect=min(60.0, timeout))


def _format_http_error(e: httpx.HTTPError) -> str:
    detail = str(e).strip()
    if detail:
        return f"网络异常：{detail}"
    return f"网络异常：{type(e).__name__}"


class DeepSeekError(Exception):
    """DeepSeek 调用统一异常。"""


def _ensure_api_key(api_key: str) -> str:
    key = (api_key or "").strip().strip('"').strip("'")
    if not key:
        raise DeepSeekError("API Key 为空，无法构造 Authorization 头")
    return key


async def chat(
    messages: list[dict],
    api_key: str,
    *,
    response_format_json: bool = False,
    temperature: float = 0.7,
    timeout: float = 120.0,
) -> str:
    api_key = _ensure_api_key(api_key)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}

    client = get_http_client()
    last_err: httpx.HTTPError | None = None
    resp = None
    for attempt in range(3):
        try:
            resp = await client.post(
                DEEPSEEK_API_URL,
                json=payload,
                headers=headers,
                timeout=_request_timeout(timeout),
            )
            break
        except httpx.HTTPError as e:
            last_err = e
            if attempt < 2 and isinstance(e, _RETRYABLE_HTTP):
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise DeepSeekError(_format_http_error(e)) from e
    if resp is None:
        assert last_err is not None
        raise DeepSeekError(_format_http_error(last_err)) from last_err
    if resp.status_code != 200:
        raise DeepSeekError(f"HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise DeepSeekError(f"响应结构异常：{data}") from e


async def chat_stream(
    messages: list[dict],
    api_key: str,
    *,
    temperature: float = 0.7,
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """SSE 模式逐字符流式返回 content delta（Phase 2 会用到）。"""
    api_key = _ensure_api_key(api_key)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    client = get_http_client()
    req_timeout = _request_timeout(timeout)
    last_err: httpx.HTTPError | None = None
    for attempt in range(3):
        try:
            async with client.stream(
                "POST",
                DEEPSEEK_API_URL,
                json=payload,
                headers=headers,
                timeout=req_timeout,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    body_text = body.decode(errors="replace")
                    raise DeepSeekError(f"HTTP {resp.status_code}: {body_text}")
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
            return
        except httpx.HTTPError as e:
            last_err = e
            if attempt < 2 and isinstance(e, _RETRYABLE_HTTP):
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise DeepSeekError(_format_http_error(e)) from e
    if last_err is not None:
        raise DeepSeekError(_format_http_error(last_err)) from last_err
