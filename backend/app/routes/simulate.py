"""POST /api/simulate/stream —— 双 NPC 交替的多轮对话 SSE 引擎。

事件协议（与前端约定）：
- event: turn_start  data: {turn, role}
- event: delta       data: {turn, role, text}        # 流式 token，多次
- event: turn_end    data: {turn, role, text}        # 完整文本
- event: error       data: {turn, role, message}     # LLM 异常
- event: done        data: {reason, total_turns}     # ended / max_turns / user_aborted / llm_error
"""
from __future__ import annotations

import asyncio
import json
import math

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.llm.deepseek import DeepSeekError, chat_stream
from app.prompts.agent import build_agent_system
from app.prompts.npc import build_npc_system
from app.schemas import Branch, ScoringCriteria
from app.termination import keyword_pre_screen, llm_confirm_end

router = APIRouter()


class SimulateRequest(BaseModel):
    instruction: str
    branch: Branch
    scoring_criteria: ScoringCriteria
    agent_key: str
    evaluator_key: str


def _similarity(a: str, b: str) -> float:
    """Levenshtein 相似度（短文本足够）：1 - dist/max(len)。"""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return 1 - prev[lb] / max(la, lb)


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}


@router.post("/simulate/stream")
async def simulate_stream(req: SimulateRequest, request: Request):
    branch = req.branch
    hard_max = max(2, math.ceil(branch.estimated_max_turns * 1.5))

    agent_sys = build_agent_system(req.instruction)
    npc_sys = build_npc_system(branch.npc_persona, req.instruction)
    transcript: list[tuple[str, str]] = []  # [(role, text)]
    repeat_streak = 0

    async def event_gen():
        nonlocal repeat_streak
        reason = "ended"
        turn = 0
        try:
            while turn < hard_max:
                if await request.is_disconnected():
                    reason = "user_aborted"
                    break
                turn += 1
                role = "agent" if turn == 1 else ("user" if transcript[-1][0] == "agent" else "agent")

                if role == "agent":
                    messages: list[dict] = [{"role": "system", "content": agent_sys}]
                    if turn == 1:
                        messages.append(
                            {"role": "user", "content": "（电话已接通，请按指令开始开场白）"}
                        )
                    for r, t in transcript:
                        messages.append(
                            {"role": "assistant" if r == "agent" else "user", "content": t}
                        )
                    api_key = req.agent_key
                else:
                    messages = [{"role": "system", "content": npc_sys}]
                    if repeat_streak >= 3:
                        messages.append(
                            {
                                "role": "system",
                                "content": "请推进对话，换一个角度回应，不要再重复之前的话。",
                            }
                        )
                    for r, t in transcript:
                        messages.append(
                            {"role": "assistant" if r == "user" else "user", "content": t}
                        )
                    api_key = req.evaluator_key

                yield _sse("turn_start", {"turn": turn, "role": role})

                accumulated: list[str] = []
                aborted = False
                try:
                    async for delta in chat_stream(messages, api_key, temperature=0.7):
                        if await request.is_disconnected():
                            aborted = True
                            break
                        accumulated.append(delta)
                        yield _sse("delta", {"turn": turn, "role": role, "text": delta})
                except DeepSeekError as e:
                    yield _sse("error", {"turn": turn, "role": role, "message": str(e)})
                    reason = "llm_error"
                    break

                if aborted:
                    reason = "user_aborted"
                    break

                text = "".join(accumulated).strip()
                transcript.append((role, text))
                yield _sse("turn_end", {"turn": turn, "role": role, "text": text})

                if role == "user":
                    prev_user = next(
                        (t for r, t in reversed(transcript[:-1]) if r == "user"),
                        None,
                    )
                    if prev_user and _similarity(prev_user, text) >= 0.8:
                        repeat_streak += 1
                    else:
                        repeat_streak = 0

                if keyword_pre_screen(text):
                    tail = "\n".join(
                        f"{'数字人' if r == 'agent' else '用户'}: {t}"
                        for r, t in transcript[-3:]
                    )
                    if await llm_confirm_end(tail, req.evaluator_key):
                        reason = "ended"
                        break
            else:
                reason = "max_turns"

            yield _sse("done", {"reason": reason, "total_turns": len(transcript)})
        except asyncio.CancelledError:
            raise

    return EventSourceResponse(event_gen())
