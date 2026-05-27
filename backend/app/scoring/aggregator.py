"""聚合：把 4 个非效率维度的子项分数 + 效率维度组合成 Report。

- Rule / Keyword 子项同步算（毫秒级）
- LLM 子项 asyncio.gather 并发（Semaphore 限 8）
- applicable_branches 过滤（不含本分支 → 不计入分母）
- 维度内若无任何 applicable item → score = None，weight 不计入 overall
- 效率：max_turns × 1.5 时置 0；正常完成 ≤ estimated → 1.0；超出按线性下降
- summary 单独再调一次 LLM
"""
from __future__ import annotations

import asyncio
import json

from app.llm.deepseek import DeepSeekError, chat
from app.prompts.summary import build_summary_messages
from app.schemas import (
    Branch,
    ConversationData,
    DimensionScoreResult,
    EfficiencyResult,
    Report,
    ScoreItemResult,
    ScoringCriteria,
    ScoringItem,
)
from app.scoring.criteria_normalize import is_conditional_item
from app.scoring.keyword import evaluate_keyword
from app.scoring.llm_scorer import evaluate_llm_item
from app.scoring.rules import evaluate_rule

NON_EFFICIENCY_DIMS: tuple[str, ...] = (
    "task_completion",
    "instruction_following",
    "naturalness",
    "branch_handling",
)

LLM_CONCURRENCY = 8


def _is_applicable(item: ScoringItem, branch_id: str) -> bool:
    if not item.applicable_branches:
        return True
    return branch_id in item.applicable_branches


def _efficiency(
    *, criteria_weight: float, conv: ConversationData, branch: Branch
) -> EfficiencyResult:
    estimated = max(1, branch.estimated_max_turns)
    actual = max(0, conv.total_turns)
    if conv.status == "max_turns":
        return EfficiencyResult(
            weight=criteria_weight,
            score=0.0,
            actual_turns=actual,
            estimated_max_turns=estimated,
            reason=f"达到硬上限（estimated×1.5），效率分置 0",
        )
    if conv.status in ("user_aborted", "llm_error"):
        return EfficiencyResult(
            weight=criteria_weight,
            score=0.0,
            actual_turns=actual,
            estimated_max_turns=estimated,
            reason=f"对话异常结束（{conv.status}），效率不计分",
        )
    if actual <= estimated:
        return EfficiencyResult(
            weight=criteria_weight,
            score=1.0,
            actual_turns=actual,
            estimated_max_turns=estimated,
            reason=f"{actual} 轮内完成（≤ 预估 {estimated}）",
        )
    over = actual - estimated
    cap = 0.5 * estimated
    score = max(0.0, 1.0 - over / cap)
    return EfficiencyResult(
        weight=criteria_weight,
        score=score,
        actual_turns=actual,
        estimated_max_turns=estimated,
        reason=f"超出预估 {over} 轮（预估 {estimated}），线性折扣",
    )


async def _score_one_item(
    *,
    item: ScoringItem,
    conv: ConversationData,
    branch: Branch,
    evaluator_key: str,
    semaphore: asyncio.Semaphore,
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

    eval_type = item.eval_type
    if item.eval_type == "rule":
        score, reason = evaluate_rule(item, conv.turns)
    elif item.eval_type == "keyword" and is_conditional_item(item):
        eval_type = "llm"
        async with semaphore:
            score, reason = await evaluate_llm_item(
                item=item,
                turns=conv.turns,
                branch_name=branch.name,
                api_key=evaluator_key,
            )
    elif item.eval_type == "keyword":
        score, reason = evaluate_keyword(item, conv.turns)
    else:
        async with semaphore:
            score, reason = await evaluate_llm_item(
                item=item,
                turns=conv.turns,
                branch_name=branch.name,
                api_key=evaluator_key,
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
) -> tuple[list[str], list[str]]:
    payload_dims = {
        name: {
            "weight": d.weight,
            "score": d.score,
            "items": [
                {"description": i.description, "score": i.score, "reason": i.reason}
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
        "estimated_max_turns": eff.estimated_max_turns,
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
) -> Report:
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)

    dim_to_items: dict[str, list[ScoringItem]] = {
        name: list(getattr(scoring_criteria, name).items)
        for name in NON_EFFICIENCY_DIMS
    }

    flat: list[tuple[str, ScoringItem]] = [
        (dim, item) for dim, items in dim_to_items.items() for item in items
    ]
    tasks = [
        _score_one_item(
            item=item,
            conv=conversation,
            branch=branch,
            evaluator_key=evaluator_key,
            semaphore=semaphore,
        )
        for _, item in flat
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

    efficiency = _efficiency(
        criteria_weight=scoring_criteria.efficiency.weight,
        conv=conversation,
        branch=branch,
    )

    weighted_sum = 0.0
    weight_sum = 0.0
    for d in dims.values():
        if d.score is not None:
            weighted_sum += d.score * d.weight
            weight_sum += d.weight
    weighted_sum += efficiency.score * efficiency.weight
    weight_sum += efficiency.weight
    overall = weighted_sum / weight_sum if weight_sum > 0 else 0.0

    advantages, improvements = await _summarize(
        branch=branch, dims=dims, eff=efficiency, api_key=evaluator_key
    )

    return Report(
        branch_id=branch.id,
        overall=overall,
        dimensions=dims,
        efficiency=efficiency,
        advantages=advantages,
        improvements=improvements,
    )
