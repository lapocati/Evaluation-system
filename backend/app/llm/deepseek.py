"""DeepSeek 官方 API 客户端封装。endpoint 与模型名固定，仅暴露 api_key。"""
import json
from typing import AsyncGenerator

import httpx

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekError(Exception):
    """DeepSeek 调用统一异常。"""


async def chat(
    messages: list[dict],
    api_key: str,
    *,
    response_format_json: bool = False,
    temperature: float = 0.7,
    timeout: float = 120.0,
) -> str:
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

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.post(DEEPSEEK_API_URL, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise DeepSeekError(f"网络异常：{e}") from e
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
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", DEEPSEEK_API_URL, json=payload, headers=headers
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise DeepSeekError(f"HTTP {resp.status_code}: {body.decode(errors='replace')}")
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
