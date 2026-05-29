"""聚合：把 4 个非效率维度的子项分数 + 效率维度组合成 Report。

- Rule / Keyword 子项同步算（毫秒级）
- LLM 子项 asyncio.gather 并发（Semaphore 限 8）
- applicable_branches 过滤（不含本分支 → 不计入分母）
- 维度内若无任何 applicable item → score = None，weight 不计入 overall
- 效率：无效轮次占比扣分（空话/重复/兜圈）；task 未完成时效率不适用
- summary 单独再调一次 LLM
"""
from __future__ import annotations

import asyncio
import json
import re

from app.llm.deepseek import DeepSeekError, chat
from app.prompts.summary import build_summary_messages
from app.schemas import (
    Branch,
    ConversationData,
    ConversationTurn,
    DimensionScoreResult,
    EfficiencyResult,
    Report,
    ScoreItemResult,
    ScoringCriteria,
    ScoringItem,
)
from app.scoring.config import (
    CIRCULAR_THRESHOLD,
    EFFICIENCY_REPEAT_THRESHOLD,
    EFFICIENCY_TASK_FLOOR,
)
from app.scoring.criteria_normalize import is_conditional_item
from app.scoring.keyword import evaluate_keyword
from app.scoring.llm_scorer import evaluate_llm_item
from app.scoring.rules import (
    _agent_turns,
    evaluate_rule,
    is_adjacent_repeat,
    is_circular_turn,
    is_filler_turn,
)

NON_EFFICIENCY_DIMS: tuple[str, ...] = (
    "task_completion",
    "instruction_following",
    "naturalness",
    "branch_handling",
)

LLM_CONCURRENCY = 8

FAQ_SOURCE_PATTERN = re.compile(r"FAQ|Knowledge Points|知识库|知识点", re.I)
NA_REASON_MARKERS = ("不适用", "未询问", "未触发", "未被触发", "用户未问")


def _is_applicable(item: ScoringItem, branch_id: str) -> bool:
    if not item.applicable_branches:
        return True
    return branch_id in item.applicable_branches


def _is_faq_item(item: ScoringItem) -> bool:
    return item.item_kind == "faq_entry" or bool(FAQ_SOURCE_PATTERN.search(item.source))


def _user_text(turns: list[ConversationTurn]) -> str:
    return "\n".join(t.text for t in turns if t.role == "user")


def _is_faq_triggered(item: ScoringItem, turns: list[ConversationTurn]) -> bool:
    user_text = _user_text(turns)
    if not user_text.strip():
        return False
    keywords = item.keywords or []
    if keywords:
        return any(k in user_text for k in keywords if len(k.strip()) >= 2)
    desc = re.sub(r"[^\u4e00-\u9fff]", " ", item.description)
    tokens = [t for t in desc.split() if len(t) >= 2]
    return any(t in user_text for t in tokens[:6])


def _reason_indicates_na(reason: str) -> bool:
    return any(m in reason for m in NA_REASON_MARKERS)


def _na_reason_for_item(item: ScoringItem, reason: str) -> str:
    if _reason_indicates_na(reason):
        return reason
    if _is_faq_item(item):
        return "用户未询问，不适用"
    return "场景未触发，不适用"


def _should_mark_na(item: ScoringItem, reason: str, turns: list[ConversationTurn]) -> bool:
    if item.item_kind == "mandatory_step":
        return False
    if item.item_kind == "opening" or item.rule == "required_opening":
        return False
    if _is_faq_item(item) or item.item_kind == "faq_entry":
        return not _is_faq_triggered(item, turns)
    if item.item_kind == "conditional_response":
        return _reason_indicates_na(reason)
    if item.eval_type == "llm" and is_conditional_item(item):
        return _reason_indicates_na(reason)
    return False


def _efficiency(
    *,
    criteria_weight: float,
    conv: ConversationData,
    task_score: float | None,
) -> EfficiencyResult:
    actual = max(0, conv.total_turns)
    empty_breakdown = {"filler": 0, "repeat": 0, "circular": 0}

    if task_score is None or task_score < EFFICIENCY_TASK_FLOOR:
        if task_score is None:
            reason = "任务完成度不可用，效率不适用"
        else:
            reason = (
                f"任务完成度 {task_score:.2f} < {EFFICIENCY_TASK_FLOOR}，效率不适用"
            )
        return EfficiencyResult(
            weight=criteria_weight,
            score=None,
            actual_turns=actual,
            agent_turns=0,
            invalid_turns=0,
            invalid_breakdown=empty_breakdown,
            reason=reason,
        )

    agents = _agent_turns(conv.turns)
    total = len(agents)

    if total <= 1:
        return EfficiencyResult(
            weight=criteria_weight,
            score=1.0,
            actual_turns=actual,
            agent_turns=total,
            invalid_turns=0,
            invalid_breakdown=empty_breakdown,
            reason="agent 轮次 ≤ 1，样本不足，默认满分",
        )

    breakdown = {"filler": 0, "repeat": 0, "circular": 0}
    invalid = 0

    for i, agent in enumerate(agents):
        text = agent.text
        if is_filler_turn(text):
            invalid += 1
            breakdown["filler"] += 1
            continue
        if i > 0 and is_adjacent_repeat(
            agents, conv.turns, i, EFFICIENCY_REPEAT_THRESHOLD
        ):
            invalid += 1
            breakdown["repeat"] += 1
            continue
        prior_texts = [agents[j].text for j in range(i - 1)]
        if prior_texts and is_circular_turn(text, prior_texts, CIRCULAR_THRESHOLD):
            invalid += 1
            breakdown["circular"] += 1

    penalty = min(invalid / total, 1.0)
    score = round(1.0 - penalty, 4)
    reason = (
        f"空话 {breakdown['filler']}、重复 {breakdown['repeat']}、"
        f"兜圈 {breakdown['circular']}，占比 {round(penalty * 100)}%，"
        f"得分 {round(score * 100)}%"
    )
    return EfficiencyResult(
        weight=criteria_weight,
        score=score,
        actual_turns=actual,
        agent_turns=total,
        invalid_turns=invalid,
        invalid_breakdown=breakdown,
        reason=reason,
    )


async def _score_one_item(
    *,
    item: ScoringItem,
    conv: ConversationData,
    branch: Branch,
    evaluator_key: str,
    semaphore: asyncio.Semaphore,
    dim_name: str,
    tone_summary: str | None,
) -> ScoreItemResult:
    if not _is_applicable(item, branch.id):
        return ScoreItemResult(
            id=item.id,
            description=item.description,
            source=item.source,
            eval_type=item.eval_type,
            applicable=False,
            score=None,
            reason=f"不适用于分支 {branch.id}",
        )

    tone_constraints = tone_summary or "" if dim_name == "naturalness" else ""
    eval_type = item.eval_type
    llm_kwargs = {
        "item": item,
        "turns": conv.turns,
        "branch_name": branch.name,
        "api_key": evaluator_key,
        "item_kind": item.item_kind,
        "tone_constraints": tone_constraints,
    }

    if item.eval_type == "rule":
        score, reason = evaluate_rule(item, conv.turns)
    elif item.eval_type == "keyword" and _is_faq_item(item):
        if not _is_faq_triggered(item, conv.turns):
            return ScoreItemResult(
                id=item.id,
                description=item.description,
                source=item.source,
                eval_type=eval_type,
                applicable=False,
                score=None,
                reason="用户未询问，不适用",
            )
        score, reason = evaluate_keyword(item, conv.turns)
    elif item.eval_type == "keyword" and is_conditional_item(item):
        eval_type = "llm"
        async with semaphore:
            score, reason = await evaluate_llm_item(**llm_kwargs)
    elif item.eval_type == "keyword":
        score, reason = evaluate_keyword(item, conv.turns)
    else:
        async with semaphore:
            score, reason = await evaluate_llm_item(**llm_kwargs)

    if _should_mark_na(item, reason, conv.turns):
        return ScoreItemResult(
            id=item.id,
            description=item.description,
            source=item.source,
            eval_type=eval_type,
            applicable=False,
            score=None,
            reason=_na_reason_for_item(item, reason),
        )

    return ScoreItemResult(
        id=item.id,
        description=item.description,
        source=item.source,
        eval_type=eval_type,
        applicable=True,
        score=score,
        reason=reason,
    )


async def _summarize(
    *,
    branch: Branch,
    dims: dict[str, DimensionScoreResult],
    eff: EfficiencyResult,
    api_key: str,
    item_kinds: dict[str, str | None],
) -> tuple[list[str], list[str]]:
    payload_dims = {
        name: {
            "weight": d.weight,
            "score": d.score,
            "items": [
                {
                    "description": i.description,
                    "score": i.score,
                    "reason": i.reason,
                    "item_kind": item_kinds.get(i.id),
                }
                for i in d.items
                if i.applicable
            ],
        }
        for name, d in dims.items()
    }
    payload_eff = {
        "weight": eff.weight,
        "score": eff.score,
        "actual_turns": eff.actual_turns,
        "invalid_turns": eff.invalid_turns,
        "invalid_breakdown": eff.invalid_breakdown,
        "reason": eff.reason,
    }
    messages = build_summary_messages(
        branch_name=branch.name,
        dimensions_payload=payload_dims,
        efficiency_payload=payload_eff,
    )
    try:
        raw = await chat(
            messages,
            api_key,
            response_format_json=True,
            temperature=0.3,
            timeout=60.0,
        )
        data = json.loads(raw)
        adv = [str(x).strip() for x in data.get("advantages", []) if str(x).strip()]
        imp = [str(x).strip() for x in data.get("improvements", []) if str(x).strip()]
        return adv[:4], imp[:4]
    except (DeepSeekError, json.JSONDecodeError, TypeError):
        return [], []


async def build_report(
    *,
    branch: Branch,
    conversation: ConversationData,
    scoring_criteria: ScoringCriteria,
    evaluator_key: str,
    tone_summary: str | None = None,
) -> Report:
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

    dim_to_items: dict[str, list[ScoringItem]] = {
        name: list(getattr(scoring_criteria, name).items)
        for name in NON_EFFICIENCY_DIMS
    }

    flat: list[tuple[str, ScoringItem]] = [
        (dim, item) for dim, items in dim_to_items.items() for item in items
    ]
    item_kinds = {item.id: item.item_kind for _, item in flat}

    tasks = [
        _score_one_item(
            item=item,
            conv=conversation,
            branch=branch,
            evaluator_key=evaluator_key,
            semaphore=semaphore,
            dim_name=dim,
            tone_summary=tone_summary,
        )
        for dim, item in flat
    ]
    results: list[ScoreItemResult] = await asyncio.gather(*tasks)

    dims: dict[str, DimensionScoreResult] = {}
    cursor = 0
    for name in NON_EFFICIENCY_DIMS:
        weight = getattr(scoring_criteria, name).weight
        items_count = len(dim_to_items[name])
        dim_items = results[cursor : cursor + items_count]
        cursor += items_count
        applicable = [r for r in dim_items if r.applicable and r.score is not None]
        dim_score = (
            sum(r.score for r in applicable) / len(applicable) if applicable else None
        )
        dims[name] = DimensionScoreResult(
            dimension=name,
            weight=weight,
            score=dim_score,
            items=dim_items,
        )

    task_score = dims["task_completion"].score
    efficiency = _efficiency(
        criteria_weight=scoring_criteria.efficiency.weight,
        conv=conversation,
        task_score=task_score,
    )

    weighted_sum = 0.0
    weight_sum = 0.0
    for d in dims.values():
        if d.score is not None:
            weighted_sum += d.score * d.weight
            weight_sum += d.weight
    if efficiency.score is not None:
        weighted_sum += efficiency.score * efficiency.weight
        weight_sum += efficiency.weight
    overall = weighted_sum / weight_sum if weight_sum > 0 else 0.0

    advantages, improvements = await _summarize(
        branch=branch,
        dims=dims,
        eff=efficiency,
        api_key=evaluator_key,
        item_kinds=item_kinds,
    )

    return Report(
        branch_id=branch.id,
        overall=overall,
        dimensions=dims,
        efficiency=efficiency,
        advantages=advantages,
        improvements=improvements,
    )
