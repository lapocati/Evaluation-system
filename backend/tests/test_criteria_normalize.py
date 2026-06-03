"""criteria_normalize 单元测试（不依赖 LLM）。"""
from app.schemas import (
    Branch,
    DimensionCriteria,
    EfficiencyCriteria,
    ParseResponse,
    ScoringCriteria,
    ScoringItem,
)
from app.scoring.criteria_normalize import normalize_scoring_criteria


def _meituan_branches() -> list[Branch]:
    return [
        Branch(
            id="A",
            name="配合型",
            description="用户愿意配送",
            npc_persona="你是配合的骑手，愿意今天配送。",
        ),
        Branch(
            id="B",
            name="拒绝型",
            description="用户不想配送",
            npc_persona="你是拒绝配送的骑手，会表示今天无法配送。",
        ),
    ]


def _compound_step3_item() -> ScoringItem:
    return ScoringItem(
        id="tc_3",
        description="尽量挽留不想配送的骑手，鼓励能配送的骑手，并提醒他们注意安全",
        source="Call Flow Step 3",
        eval_type="llm",
        item_kind="mandatory_step",
    )


def test_split_compound_step3_into_three_items():
    criteria = ScoringCriteria(
        task_completion=DimensionCriteria(weight=0.35, items=[_compound_step3_item()]),
        instruction_following=DimensionCriteria(weight=0.25, items=[]),
        naturalness=DimensionCriteria(weight=0.15, items=[]),
        branch_handling=DimensionCriteria(weight=0.15, items=[]),
        efficiency=EfficiencyCriteria(weight=0.10),
    )
    response = ParseResponse(
        branches=_meituan_branches(),
        scoring_criteria=criteria,
        tone_summary="口语化",
    )
    result = normalize_scoring_criteria(response)
    bh = result.scoring_criteria.branch_handling.items
    tc = result.scoring_criteria.task_completion.items

    retain = next(i for i in bh if i.id.endswith("_retain"))
    encourage = next(i for i in bh if i.id.endswith("_encourage"))
    safety = next(i for i in tc if i.id.endswith("_safety"))

    assert retain.item_kind == "conditional_response"
    assert "B" in (retain.applicable_branches or [])
    assert "A" not in (retain.applicable_branches or [])

    assert encourage.item_kind == "conditional_response"
    assert "A" in (encourage.applicable_branches or [])

    assert safety.item_kind == "mandatory_step"
    assert not any(i.id == "tc_3" for i in tc + bh)


def test_retain_not_applicable_on_cooperative_branch():
    from app.scoring.aggregator import _is_applicable

    criteria = ScoringCriteria(
        task_completion=DimensionCriteria(weight=0.35, items=[_compound_step3_item()]),
        instruction_following=DimensionCriteria(weight=0.25, items=[]),
        naturalness=DimensionCriteria(weight=0.15, items=[]),
        branch_handling=DimensionCriteria(weight=0.15, items=[]),
        efficiency=EfficiencyCriteria(weight=0.10),
    )
    result = normalize_scoring_criteria(
        ParseResponse(
            branches=_meituan_branches(),
            scoring_criteria=criteria,
            tone_summary="口语化",
        )
    )
    retain = next(
        i
        for i in result.scoring_criteria.branch_handling.items
        if i.id.endswith("_retain")
    )
    assert _is_applicable(retain, "A") is False
    assert _is_applicable(retain, "B") is True


if __name__ == "__main__":
    test_split_compound_step3_into_three_items()
    test_retain_not_applicable_on_cooperative_branch()
    print("all passed")
