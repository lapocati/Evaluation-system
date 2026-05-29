"""DeepSeek 官方 API 客户端封装。endpoint 与模型名固定，仅暴露 api_key。"""
import asyncio
import json
import time
from pathlib import Path
from typing import AsyncGenerator

import httpx

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
_DEBUG_LOG = Path(__file__).resolve().parents[3] / "debug-1793b4.log"
_DEBUG_LOG_B3 = Path(__file__).resolve().parents[3] / "debug-b3a46e.log"
_DEBUG_LOG_7BE968 = Path(__file__).resolve().parents[3] / "debug-7be968.log"
_DEBUG_LOG_FB3D39 = Path(__file__).resolve().parents[3] / "debug-fb3d39.log"
_DEBUG_LOG_BDD1EC = Path(__file__).resolve().parents[3] / "debug-bdd1ec.log"

_RETRYABLE_HTTP = (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError)


def _format_http_error(e: httpx.HTTPError) -> str:
    detail = str(e).strip()
    if detail:
        return f"网络异常：{detail}"
    return f"网络异常：{type(e).__name__}"


def _dbg_fb3d39(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    # #region agent log
    payload = {
        "sessionId": "fb3d39",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG_FB3D39.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


def _dbg7(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    # #region agent log
    payload = {
        "sessionId": "7be968",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG_7BE968.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


def _dbg_b3(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    # #region agent log
    payload = {
        "sessionId": "b3a46e",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG_B3.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


def _dbg(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    # #region agent log
    payload = {
        "sessionId": "1793b4",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


class DeepSeekError(Exception):
    """DeepSeek 调用统一异常。"""


def _dbg_bdd1ec(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    # #region agent log
    payload = {
        "sessionId": "bdd1ec",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG_BDD1EC.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


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
    # #region agent log
    _dbg_bdd1ec(
        "H2",
        "deepseek.py:chat",
        "auth_header",
        {"keyLen": len(api_key), "keySuffix": api_key[-4:] if len(api_key) >= 4 else ""},
    )
    # #endregion
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

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=min(60.0, timeout))) as client:
        msg_chars = sum(len(str(m.get("content", ""))) for m in messages)
        _dbg7(
            "H4",
            "deepseek.py:chat",
            "request_start",
            {
                "msgCount": len(messages),
                "msgChars": msg_chars,
                "keyLen": len(api_key or ""),
                "timeout": timeout,
                "jsonMode": response_format_json,
            },
        )
        last_err: httpx.HTTPError | None = None
        resp = None
        for attempt in range(3):
            try:
                resp = await client.post(DEEPSEEK_API_URL, json=payload, headers=headers)
                break
            except httpx.HTTPError as e:
                last_err = e
                _dbg_fb3d39(
                    "H1",
                    "deepseek.py:chat",
                    "http_error",
                    {"type": type(e).__name__, "message": str(e)[:300], "attempt": attempt + 1},
                )
                _dbg7(
                    "H2",
                    "deepseek.py:chat",
                    "http_error",
                    {
                        "type": type(e).__name__,
                        "message": str(e)[:300],
                        "msgCount": len(messages),
                        "msgChars": msg_chars,
                    },
                )
                if attempt < 2 and isinstance(e, _RETRYABLE_HTTP):
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                raise DeepSeekError(_format_http_error(e)) from e
        if resp is None:
            assert last_err is not None
            raise DeepSeekError(_format_http_error(last_err)) from last_err
        if resp.status_code != 200:
            _dbg7(
                "H1",
                "deepseek.py:chat",
                "http_non_200",
                {
                    "status": resp.status_code,
                    "bodyPreview": resp.text[:300],
                    "msgCount": len(messages),
                    "msgChars": msg_chars,
                },
            )
            raise DeepSeekError(f"HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
            _dbg7(
                "H5",
                "deepseek.py:chat",
                "request_ok",
                {"contentLen": len(content or "")},
            )
            return content
        except (KeyError, IndexError) as e:
            _dbg7(
                "H5",
                "deepseek.py:chat",
                "response_structure_error",
                {"keys": list(data.keys()) if isinstance(data, dict) else str(type(data))},
            )
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
    msg_chars = sum(len(str(m.get("content", ""))) for m in messages)
    _dbg_b3(
        "H4",
        "deepseek.py:chat_stream",
        "request_start",
        {
            "msgCount": len(messages),
            "msgChars": msg_chars,
            "keyLen": len(api_key or ""),
            "timeout": timeout,
        },
    )
    _dbg7(
        "H4",
        "deepseek.py:chat_stream",
        "request_start",
        {
            "msgCount": len(messages),
            "msgChars": msg_chars,
            "keyLen": len(api_key or ""),
            "keyEmpty": not bool(api_key and api_key.strip()),
            "timeout": timeout,
        },
    )
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
    last_err: httpx.HTTPError | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=min(60.0, timeout))
            ) as client:
                async with client.stream(
                    "POST", DEEPSEEK_API_URL, json=payload, headers=headers
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        body_text = body.decode(errors="replace")
                        _dbg_b3(
                            "H1",
                            "deepseek.py:chat_stream",
                            "http_non_200",
                            {
                                "status": resp.status_code,
                                "bodyPreview": body_text[:300],
                                "msgCount": len(messages),
                                "msgChars": msg_chars,
                            },
                        )
                        _dbg7(
                            "H1",
                            "deepseek.py:chat_stream",
                            "http_non_200",
                            {
                                "status": resp.status_code,
                                "bodyPreview": body_text[:300],
                                "msgCount": len(messages),
                                "msgChars": msg_chars,
                            },
                        )
                        raise DeepSeekError(f"HTTP {resp.status_code}: {body_text}")
                    _dbg("H1", "deepseek.py:chat_stream", "stream_open", {"status": resp.status_code})
                    line_count = 0
                    yielded = 0
                    async for line in resp.aiter_lines():
                        line_count += 1
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            _dbg(
                                "H1",
                                "deepseek.py:chat_stream",
                                "stream_done",
                                {"lineCount": line_count, "yielded": yielded},
                            )
                            return
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yielded += 1
                                if yielded == 1:
                                    _dbg(
                                        "H1",
                                        "deepseek.py:chat_stream",
                                        "first_yield",
                                        {"deltaLen": len(delta)},
                                    )
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                    _dbg(
                        "H1",
                        "deepseek.py:chat_stream",
                        "stream_exhausted",
                        {"lineCount": line_count, "yielded": yielded},
                    )
            return
        except httpx.HTTPError as e:
            last_err = e
            _dbg_fb3d39(
                "H1",
                "deepseek.py:chat_stream",
                "http_error",
                {
                    "type": type(e).__name__,
                    "message": str(e)[:300],
                    "attempt": attempt + 1,
                    "msgChars": msg_chars,
                },
            )
            _dbg_b3(
                "H2",
                "deepseek.py:chat_stream",
                "http_error",
                {
                    "type": type(e).__name__,
                    "message": str(e)[:300],
                    "msgCount": len(messages),
                    "msgChars": msg_chars,
                },
            )
            _dbg7(
                "H2",
                "deepseek.py:chat_stream",
                "http_error",
                {
                    "type": type(e).__name__,
                    "message": str(e)[:300],
                    "msgCount": len(messages),
                    "msgChars": msg_chars,
                },
            )
            _dbg(
                "H1",
                "deepseek.py:chat_stream",
                "http_error",
                {"type": type(e).__name__, "message": str(e)[:200]},
            )
            if attempt < 2 and isinstance(e, _RETRYABLE_HTTP):
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            raise DeepSeekError(_format_http_error(e)) from e
    if last_err is not None:
        raise DeepSeekError(_format_http_error(last_err)) from last_err
