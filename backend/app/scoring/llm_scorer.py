"""LLM 子项评分：单次调用 → JSON {"score": 0~1, "reason": "..."}。

由 aggregator 用 asyncio.gather + Semaphore 限并发驱动。
"""
from __future__ import annotations

import json

from app.llm.deepseek import DeepSeekError, chat
from app.prompts.scorer import build_scorer_messages
from app.schemas import ConversationTurn, ScoringItem


def _format_transcript(turns: list[ConversationTurn]) -> str:
    if not turns:
        return "（无对话）"
    return "\n".join(
        f"第{t.turn}轮 数字人：{t.text}" if t.role == "agent" else f"用户：{t.text}"
        for t in turns
    )


async def evaluate_llm_item(
    *,
    item: ScoringItem,
    turns: list[ConversationTurn],
    branch_name: str,
    api_key: str,
    item_kind: str | None = None,
    tone_constraints: str = "",
) -> tuple[float, str]:
    transcript = _format_transcript(turns)
    messages = build_scorer_messages(
        item_description=item.description,
        item_source=item.source,
        branch_name=branch_name,
        transcript=transcript,
        item_kind=item_kind or item.item_kind,
        tone_constraints=tone_constraints,
    )
    try:
        raw = await chat(
            messages,
            api_key,
            response_format_json=True,
            temperature=0.0,
            timeout=60.0,
        )
    except DeepSeekError as e:
        return 0.0, f"LLM 评分失败：{e}"

    try:
        data = json.loads(raw)
        score = float(data.get("score", 0))
        reason = str(data.get("reason", "")).strip() or "（无理由）"
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0.0, f"评分响应非法 JSON：{raw[:80]}"

    score = max(0.0, min(1.0, score))
    return score, reason
