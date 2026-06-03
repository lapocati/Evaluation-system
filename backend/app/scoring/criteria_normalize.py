"""解析后 scoring_criteria 归一化：修正 LLM 误分类的条件性子项。"""
from __future__ import annotations

import re

from app.schemas import Branch, ParseResponse, ScoringCriteria, ScoringItem

CONDITIONAL_PATTERN = re.compile(
    r"如|若|当|一旦|被问及|若拒绝|若坚持|超出职责|"
    r"不想|不愿|不能配送|拒绝配送|无法配送|不方便配送"
)
TRIGGER_BRANCH_PATTERN = re.compile(r"质疑|刁难|拒绝")
COOPERATIVE_PATTERN = re.compile(r"配合|愿意|能配送|可以配送")
COMPOUND_OPPOSE_PATTERN = re.compile(
    r"(不想|不愿|不能|无法|拒绝).{0,12}(配送|送)|"
    r"挽留.{0,20}(不想|不愿|不能)|"
    r"(挽留|不想).{0,40}(鼓励|能配送|愿意配送)"
)
COMPOUND_ACTION_PATTERN = re.compile(r"挽留|鼓励|提醒|告知|说明|询问|确认")
SPLIT_SUFFIX_PATTERN = re.compile(r"_(retain|encourage|safety)$")
TERMINAL_BRANCH_PATTERN = re.compile(r"开车|挂断|稍后再打|终止|早退")
PLACEHOLDER_PATTERN = re.compile(r"\b[A-Z]\s*[单天点元]|\$")
PLACEHOLDER_HINT = "（含占位符变量，agent 说出语义等价的具体数值即视为达标）"
CHAR_LIMIT_PATTERN = re.compile(r"(\d+)\s*字")
BUNDLING_PATTERN = re.compile(r"遵循.*(对话流程|FAQ|常见问题|流程和)", re.I)
FAQ_SOURCE_PATTERN = re.compile(r"FAQ|Knowledge Points|知识库|知识点", re.I)

_NO_MOVE_KINDS = frozenset({"mandatory_step", "faq_entry", "opening"})

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


def _cooperative_branch_ids(branches: list[Branch]) -> list[str]:
    matched = [
        b.id
        for b in branches
        if COOPERATIVE_PATTERN.search(f"{b.name} {b.description} {b.npc_persona}")
    ]
    if matched:
        return matched
    if branches:
        return [branches[0].id]
    return ["A"]


def _should_split_compound_item(item: ScoringItem) -> bool:
    if SPLIT_SUFFIX_PATTERN.search(item.id):
        return False
    text = f"{item.description} {item.source}"
    if COMPOUND_OPPOSE_PATTERN.search(text):
        return True
    if item.item_kind != "mandatory_step" and "触发条件" not in item.description:
        return False
    parts = re.split(r"[,，、；]", text)
    if len(parts) < 2:
        return False
    action_hits = sum(1 for p in parts if COMPOUND_ACTION_PATTERN.search(p))
    return action_hits >= 2 and COMPOUND_OPPOSE_PATTERN.search(text)


def _split_compound_step_items(
    item: ScoringItem, branches: list[Branch]
) -> list[ScoringItem] | None:
    if not _should_split_compound_item(item):
        return None

    trigger_ids = _trigger_branch_ids(branches)
    cooperative_ids = _cooperative_branch_ids(branches)
    base = item.id

    retain = ScoringItem(
        id=f"{base}_retain",
        description="触发条件：骑手表示不愿或不能配送；期望行为：尽量挽留",
        source=item.source,
        eval_type="llm",
        item_kind="conditional_response",
        applicable_branches=trigger_ids,
    )
    encourage = ScoringItem(
        id=f"{base}_encourage",
        description="触发条件：骑手表示愿意或能配送；期望行为：鼓励完成配送",
        source=item.source,
        eval_type="llm",
        item_kind="conditional_response",
        applicable_branches=cooperative_ids,
    )
    safety = ScoringItem(
        id=f"{base}_safety",
        description="提醒骑手注意安全",
        source=item.source,
        eval_type="llm",
        item_kind="mandatory_step",
    )
    return [retain, encourage, safety]


def _process_one_item(
    item: ScoringItem,
    branches: list[Branch],
    dim: str,
    *,
    conditional_by_id: dict[str, ScoringItem],
    kept: list[ScoringItem],
    char_limit_items: list[ScoringItem],
) -> None:
    if _is_redundant_bundling_item(item):
        return

    expanded = _split_compound_step_items(item, branches)
    candidates = expanded if expanded else [item]

    for candidate in candidates:
        normalized = _normalize_item_kind_and_eval_type(candidate)
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
            _process_one_item(
                item,
                branches,
                dim,
                conditional_by_id=conditional_by_id,
                kept=kept,
                char_limit_items=char_limit_items,
            )
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
    return result

