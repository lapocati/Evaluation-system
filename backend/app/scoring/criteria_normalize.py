"""解析后 scoring_criteria 归一化：修正 LLM 误分类的条件性子项。"""
from __future__ import annotations

import re

from app.schemas import Branch, ParseResponse, ScoringCriteria, ScoringItem

CONDITIONAL_PATTERN = re.compile(r"如|若|当|一旦|被问及|若拒绝|若坚持|超出职责")
TRIGGER_BRANCH_PATTERN = re.compile(r"质疑|刁难|拒绝")
COOPERATIVE_PATTERN = re.compile(r"配合")
TERMINAL_BRANCH_PATTERN = re.compile(r"开车|挂断|稍后再打|终止|早退")
PLACEHOLDER_PATTERN = re.compile(r"\b[A-Z]\s*[单天点元]|\$")
PLACEHOLDER_HINT = "（含占位符变量，agent 说出语义等价的具体数值即视为达标）"
CHAR_LIMIT_PATTERN = re.compile(r"(\d+)\s*字")
BUNDLING_PATTERN = re.compile(r"遵循.*(对话流程|FAQ|常见问题|流程和)", re.I)
FAQ_SOURCE_PATTERN = re.compile(r"FAQ|Knowledge Points|知识库|知识点", re.I)

_NO_MOVE_KINDS = frozenset({"mandatory_step", "faq_entry", "opening"})
_TURN_RELEVANT_KINDS = frozenset({"mandatory_step", "opening", "conditional_response"})


def is_conditional_item(item: ScoringItem) -> bool:
    text = f"{item.description} {item.source}"
    return bool(CONDITIONAL_PATTERN.search(text))


def _has_placeholder_keywords(keywords: list[str] | None) -> bool:
    if not keywords:
        return False
    return any(PLACEHOLDER_PATTERN.search(k) for k in keywords)


def _append_placeholder_hint(description: str) -> str:
    if PLACEHOLDER_HINT in description:
        return description
    return f"{description}{PLACEHOLDER_HINT}"


def _is_redundant_bundling_item(item: ScoringItem) -> bool:
    text = f"{item.description} {item.source}"
    return item.eval_type == "llm" and bool(BUNDLING_PATTERN.search(text))


def _extract_char_limit(item: ScoringItem) -> int | None:
    text = f"{item.description} {item.source}"
    if not CHAR_LIMIT_PATTERN.search(text):
        return None
    if not any(k in text for k in ("以内", "最多", "≤", "控制在", "极简", "简短")):
        return None
    m = CHAR_LIMIT_PATTERN.search(text)
    return int(m.group(1)) if m else None


def _to_char_limit_rule(item: ScoringItem) -> ScoringItem:
    limit = _extract_char_limit(item)
    if limit is None:
        return item
    return item.model_copy(
        update={
            "eval_type": "rule",
            "rule": "max_chars_per_turn",
            "rule_param": limit,
            "item_kind": "constraint",
            "keywords": None,
        }
    )


def _normalize_item_kind_and_eval_type(item: ScoringItem) -> ScoringItem:
    updates: dict = {}

    if FAQ_SOURCE_PATTERN.search(item.source) or item.item_kind == "faq_entry":
        if item.eval_type == "keyword" or item.item_kind != "faq_entry":
            updates["eval_type"] = "llm"
            updates["item_kind"] = "faq_entry"

    if item.item_kind == "faq_entry" and item.eval_type == "keyword":
        updates["eval_type"] = "llm"

    if item.eval_type == "keyword" and _has_placeholder_keywords(item.keywords):
        updates["eval_type"] = "llm"
        updates["description"] = _append_placeholder_hint(item.description)

    if item.rule == "required_opening" and _has_placeholder_keywords(item.keywords):
        updates["eval_type"] = "llm"
        updates["rule"] = None
        updates["rule_param"] = None
        if item.item_kind is None:
            updates["item_kind"] = "opening"
        updates["description"] = _append_placeholder_hint(item.description)

    if updates:
        return item.model_copy(update=updates)
    return item


def _should_move_to_branch_handling(item: ScoringItem) -> bool:
    if item.item_kind == "conditional_response":
        return True
    if item.item_kind == "constraint" and is_conditional_item(item):
        return True
    if item.item_kind in _NO_MOVE_KINDS:
        return False
    return is_conditional_item(item)


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


def _terminal_branch_ids(branches: list[Branch]) -> list[str]:
    return [
        b.id
        for b in branches
        if TERMINAL_BRANCH_PATTERN.search(f"{b.name} {b.description} {b.npc_persona}")
    ]


def _apply_mandatory_step_branch_filter(
    item: ScoringItem, branches: list[Branch]
) -> ScoringItem:
    if item.item_kind != "mandatory_step":
        return item
    terminal = set(_terminal_branch_ids(branches))
    if not terminal:
        return item
    if item.applicable_branches:
        filtered = [bid for bid in item.applicable_branches if bid not in terminal]
        if filtered:
            return item.model_copy(update={"applicable_branches": filtered})
        return item
    non_terminal = [b.id for b in branches if b.id not in terminal]
    if non_terminal:
        return item.model_copy(update={"applicable_branches": non_terminal})
    return item


def _fix_conditional_item(item: ScoringItem, branches: list[Branch]) -> ScoringItem:
    applicable = item.applicable_branches or _trigger_branch_ids(branches)
    return item.model_copy(
        update={
            "eval_type": "llm",
            "keywords": None,
            "rule": None,
            "rule_param": None,
            "applicable_branches": applicable,
            "item_kind": item.item_kind or "conditional_response",
        }
    )


def _item_applies_to_branch(item: ScoringItem, branch_id: str) -> bool:
    if not item.applicable_branches:
        return True
    return branch_id in item.applicable_branches


def _count_turn_relevant_items(criteria: ScoringCriteria, branch_id: str) -> int:
    count = 0
    for dim in ("task_completion", "instruction_following", "naturalness", "branch_handling"):
        for item in getattr(criteria, dim).items:
            if item.item_kind not in _TURN_RELEVANT_KINDS:
                continue
            if _item_applies_to_branch(item, branch_id):
                count += 1
    return count


def _bump_branch_turn_estimates(response: ParseResponse) -> ParseResponse:
    criteria = response.scoring_criteria
    branches = response.branches
    terminal_ids = set(_terminal_branch_ids(branches))
    step_count = sum(
        1
        for item in criteria.task_completion.items
        if item.item_kind == "mandatory_step"
    )
    min_turns = max(step_count * 2, 12) if step_count > 0 else 12
    new_branches = []
    for b in branches:
        if b.id in terminal_ids:
            estimated = max(_count_turn_relevant_items(criteria, b.id) * 2, 2)
        else:
            estimated = max(b.estimated_max_turns, min_turns)
        new_branches.append(b.model_copy(update={"estimated_max_turns": estimated}))
    per_branch = {b.id: b.estimated_max_turns for b in new_branches}
    new_efficiency = response.scoring_criteria.efficiency.model_copy(
        update={"per_branch_max_turns": per_branch}
    )
    return response.model_copy(
        update={
            "branches": new_branches,
            "scoring_criteria": response.scoring_criteria.model_copy(
                update={"efficiency": new_efficiency}
            ),
        }
    )


def normalize_scoring_criteria(response: ParseResponse) -> ParseResponse:
    criteria = response.scoring_criteria
    branches = response.branches

    conditional_by_id: dict[str, ScoringItem] = {}
    dim_items: dict[str, list[ScoringItem]] = {}
    char_limit_items: list[ScoringItem] = []

    for dim in (
        "task_completion",
        "instruction_following",
        "naturalness",
        "branch_handling",
    ):
        kept: list[ScoringItem] = []
        for item in getattr(criteria, dim).items:
            if _is_redundant_bundling_item(item):
                continue
            normalized = _normalize_item_kind_and_eval_type(item)
            char_converted = _to_char_limit_rule(normalized)
            if (
                char_converted.rule == "max_chars_per_turn"
                and char_converted.eval_type == "rule"
                and dim != "instruction_following"
            ):
                char_limit_items.append(char_converted)
                continue
            normalized = char_converted
            normalized = _apply_mandatory_step_branch_filter(normalized, branches)
            if _should_move_to_branch_handling(normalized):
                conditional_by_id[normalized.id] = _fix_conditional_item(normalized, branches)
            else:
                kept.append(normalized)
        dim_items[dim] = kept

    existing_char_ids = {
        i.id for i in dim_items["instruction_following"] if i.rule == "max_chars_per_turn"
    }
    for cli in char_limit_items:
        if cli.id not in existing_char_ids:
            dim_items["instruction_following"].append(cli)

    dim_items["branch_handling"] = dim_items["branch_handling"] + list(conditional_by_id.values())

    new_criteria = ScoringCriteria(
        task_completion=criteria.task_completion.model_copy(update={"items": dim_items["task_completion"]}),
        instruction_following=criteria.instruction_following.model_copy(
            update={"items": dim_items["instruction_following"]}
        ),
        naturalness=criteria.naturalness.model_copy(update={"items": dim_items["naturalness"]}),
        branch_handling=criteria.branch_handling.model_copy(
            update={"items": dim_items["branch_handling"]}
        ),
        efficiency=criteria.efficiency,
    )
    result = response.model_copy(update={"scoring_criteria": new_criteria})
    return _bump_branch_turn_estimates(result)

