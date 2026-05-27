"""解析后 scoring_criteria 归一化：修正 LLM 误分类的条件性子项。"""
from __future__ import annotations

import re

from app.schemas import Branch, ParseResponse, ScoringCriteria, ScoringItem

CONDITIONAL_PATTERN = re.compile(r"如|若|当|一旦|被问及|若拒绝|若坚持|超出职责")
TRIGGER_BRANCH_PATTERN = re.compile(r"质疑|刁难|拒绝")
COOPERATIVE_PATTERN = re.compile(r"配合")


def is_conditional_item(item: ScoringItem) -> bool:
    text = f"{item.description} {item.source}"
    return bool(CONDITIONAL_PATTERN.search(text))


def _trigger_branch_ids(branches: list[Branch]) -> list[str]:
    matched = [
        b.id
        for b in branches
        if TRIGGER_BRANCH_PATTERN.search(f"{b.name} {b.description}")
    ]
    if matched:
        return matched
    non_cooperative = [
        b.id for b in branches if not COOPERATIVE_PATTERN.search(f"{b.name} {b.description}")
    ]
    if non_cooperative:
        return non_cooperative
    return [b.id for b in branches if b.id != "A"] or [b.id for b in branches]


def _fix_conditional_item(item: ScoringItem, branches: list[Branch]) -> ScoringItem:
    applicable = item.applicable_branches or _trigger_branch_ids(branches)
    return item.model_copy(
        update={
            "eval_type": "llm",
            "keywords": None,
            "rule": None,
            "rule_param": None,
            "applicable_branches": applicable,
        }
    )


def normalize_scoring_criteria(response: ParseResponse) -> ParseResponse:
    criteria = response.scoring_criteria
    branches = response.branches

    conditional_by_id: dict[str, ScoringItem] = {}
    for dim in (
        "task_completion",
        "instruction_following",
        "naturalness",
        "branch_handling",
    ):
        for item in getattr(criteria, dim).items:
            if is_conditional_item(item):
                conditional_by_id[item.id] = _fix_conditional_item(item, branches)

    def _non_conditional(dim: str) -> list[ScoringItem]:
        return [i for i in getattr(criteria, dim).items if not is_conditional_item(i)]

    new_criteria = ScoringCriteria(
        task_completion=criteria.task_completion.model_copy(update={"items": _non_conditional("task_completion")}),
        instruction_following=criteria.instruction_following.model_copy(
            update={"items": _non_conditional("instruction_following")}
        ),
        naturalness=criteria.naturalness.model_copy(update={"items": _non_conditional("naturalness")}),
        branch_handling=criteria.branch_handling.model_copy(
            update={"items": _non_conditional("branch_handling") + list(conditional_by_id.values())}
        ),
        efficiency=criteria.efficiency,
    )
    return response.model_copy(update={"scoring_criteria": new_criteria})
