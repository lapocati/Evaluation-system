"""关键词比例打分：agent 全部回复中命中 keywords 的比例。"""
from __future__ import annotations

from app.schemas import ConversationTurn, ScoringItem


def evaluate_keyword(item: ScoringItem, turns: list[ConversationTurn]) -> tuple[float, str]:
    keywords = item.keywords or []
    if not keywords:
        return 1.0, "未配置关键词"
    agent_text = "\n".join(t.text for t in turns if t.role == "agent")
    if not agent_text:
        return 0.0, "无 agent 回复"
    hits = [k for k in keywords if k in agent_text]
    score = len(hits) / len(keywords)
    if score == 1.0:
        return 1.0, f"命中全部 {len(keywords)} 个关键词"
    missed = [k for k in keywords if k not in hits]
    return score, f"命中 {len(hits)}/{len(keywords)}（缺：{ '、'.join(missed[:5]) }）"
