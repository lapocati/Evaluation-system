"""POST /api/simulate/stream —— 双 NPC 交替的多轮对话 SSE 引擎。

事件协议（与前端约定）：
- event: turn_start  data: {turn, role}   # turn = 轮数（agent 发言时 +1；user 继承所属轮数）
- event: delta       data: {turn, role, text}
- event: turn_end    data: {turn, role, text}
- event: error       data: {turn, role, message}
- event: done        data: {reason, total_turns}     # total_turns = agent 发言次数
"""
from __future__ import annotations

import asyncio
import json
import math
import time
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.llm.deepseek import DeepSeekError, chat_stream
from app.prompts.agent import build_agent_system
from app.prompts.npc import build_npc_system
from app.schemas import Branch, ScoringCriteria
from app.termination import keyword_pre_screen, llm_confirm_end

router = APIRouter()

_DEBUG_LOG = Path(__file__).resolve().parents[3] / "debug-1793b4.log"
_DEBUG_LOG_B3 = Path(__file__).resolve().parents[3] / "debug-b3a46e.log"
_DEBUG_LOG_7BE968 = Path(__file__).resolve().parents[3] / "debug-7be968.log"


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


def _dbg_b3_sim(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
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


def _agent_turn_count(transcript: list[tuple[str, str]]) -> int:
    return sum(1 for role, _ in transcript if role == "agent")


@router.post("/simulate/stream")
async def simulate_stream(req: SimulateRequest, request: Request):
    branch = req.branch
    hard_max = max(2, math.ceil(branch.estimated_max_turns * 1.5))
    _dbg_b3_sim(
        "H4",
        "simulate.py:simulate_stream",
        "session_start",
        {
            "branchId": branch.id,
            "estimatedMaxTurns": branch.estimated_max_turns,
            "hardMax": hard_max,
            "agentKeyLen": len(req.agent_key or ""),
            "evaluatorKeyLen": len(req.evaluator_key or ""),
            "instructionLen": len(req.instruction or ""),
        },
    )

    agent_sys = build_agent_system(req.instruction)
    npc_sys = build_npc_system(branch.npc_persona, req.instruction)
    transcript: list[tuple[str, str]] = []
    repeat_streak = 0

    async def event_gen():
        nonlocal repeat_streak
        reason = "ended"
        agent_round = 0
        halt = False

        async def stream_message(role: str, round_num: int):
            nonlocal repeat_streak, reason, halt

            if role == "agent":
                messages: list[dict] = [{"role": "system", "content": agent_sys}]
                if round_num == 1:
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

            yield _sse("turn_start", {"turn": round_num, "role": role})
            msg_chars = sum(len(str(m.get("content", ""))) for m in messages)
            _dbg_b3_sim(
                "H4",
                "simulate.py:stream_message",
                "before_llm",
                {
                    "turn": round_num,
                    "role": role,
                    "msgCount": len(messages),
                    "msgChars": msg_chars,
                    "transcriptTurns": len(transcript),
                    "keyLen": len(api_key or ""),
                },
            )

            accumulated: list[str] = []
            delta_count = 0
            try:
                async for delta in chat_stream(messages, api_key, temperature=0.7):
                    if await request.is_disconnected():
                        reason = "user_aborted"
                        halt = True
                        return
                    accumulated.append(delta)
                    delta_count += 1
                    yield _sse("delta", {"turn": round_num, "role": role, "text": delta})
            except DeepSeekError as e:
                _dbg_b3_sim(
                    "H1",
                    "simulate.py:stream_message",
                    "deepseek_error",
                    {
                        "turn": round_num,
                        "role": role,
                        "error": str(e)[:400],
                        "msgCount": len(messages),
                        "msgChars": msg_chars,
                    },
                )
                _dbg7(
                    "H1" if "HTTP" in str(e) else "H2",
                    "simulate.py:stream_message",
                    "deepseek_error",
                    {
                        "turn": round_num,
                        "role": role,
                        "error": str(e)[:400],
                        "msgCount": len(messages),
                        "msgChars": msg_chars,
                        "keyLen": len(api_key or ""),
                        "keyEmpty": not bool(api_key and api_key.strip()),
                    },
                )
                yield _sse("error", {"turn": round_num, "role": role, "message": str(e)})
                reason = "llm_error"
                halt = True
                return

            text = "".join(accumulated).strip()
            _dbg(
                "H5",
                "simulate.py:stream_message",
                "turn_end",
                {"turn": round_num, "role": role, "deltaCount": delta_count, "textLen": len(text)},
            )
            transcript.append((role, text))
            yield _sse("turn_end", {"turn": round_num, "role": role, "text": text})

            if role == "user":
                prev_user = next(
                    (t for r, t in reversed(transcript[:-1]) if r == "user"),
                    None,
                )
                if prev_user and _similarity(prev_user, text) >= 0.8:
                    repeat_streak += 1
                else:
                    repeat_streak = 0

        async def check_termination() -> bool:
            nonlocal reason, halt
            if not transcript:
                return False
            text = transcript[-1][1]
            if not keyword_pre_screen(text):
                return False
            tail = "\n".join(
                f"{'数字人' if r == 'agent' else '用户'}: {t}"
                for r, t in transcript[-3:]
            )
            _dbg("H4", "simulate.py:check_termination", "llm_confirm_start", {"tailLen": len(tail)})
            confirmed = await llm_confirm_end(tail, req.evaluator_key)
            _dbg(
                "H4",
                "simulate.py:check_termination",
                "llm_confirm_end",
                {"confirmed": confirmed},
            )
            if confirmed:
                reason = "ended"
                halt = True
                return True
            return False

        try:
            while not halt:
                if await request.is_disconnected():
                    reason = "user_aborted"
                    break

                agent_round += 1
                if agent_round > hard_max:
                    reason = "max_turns"
                    break

                async for evt in stream_message("agent", agent_round):
                    yield evt
                if halt:
                    break

                if await check_termination():
                    break

                if agent_round >= hard_max:
                    async for evt in stream_message("user", agent_round):
                        yield evt
                    if not halt:
                        reason = "max_turns"
                    break

                async for evt in stream_message("user", agent_round):
                    yield evt
                if halt:
                    break

                if await check_termination():
                    break

            yield _sse(
                "done",
                {"reason": reason, "total_turns": _agent_turn_count(transcript)},
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            _dbg_b3_sim(
                "H7",
                "simulate.py:event_gen",
                "unhandled_exception",
                {"type": type(e).__name__, "message": str(e)[:300]},
            )
            yield _sse("error", {"turn": agent_round, "role": "agent", "message": str(e)})
            reason = "llm_error"
            yield _sse(
                "done",
                {"reason": reason, "total_turns": _agent_turn_count(transcript)},
            )

    return EventSourceResponse(event_gen(), ping=15)
