"""POST /api/evaluate —— Rule + Keyword + LLM 子项并发 → 五维度汇总 → summary。"""
import logging

from fastapi import APIRouter, HTTPException

from app.schemas import EvaluateRequest, Report
from app.scoring.aggregator import build_report

logger = logging.getLogger("dialogeval.evaluate")
logger.setLevel(logging.INFO)
router = APIRouter()


@router.post("/evaluate", response_model=Report)
async def evaluate(req: EvaluateRequest) -> Report:
    if not req.conversation.turns:
        raise HTTPException(status_code=400, detail="对话为空，无法评测")
    try:
        report = await build_report(
            branch=req.branch,
            conversation=req.conversation,
            scoring_criteria=req.scoring_criteria,
            evaluator_key=req.evaluator_key,
        )
    except Exception as e:
        logger.exception("evaluate failed")
        raise HTTPException(status_code=500, detail=f"评测异常：{e}") from e
    return report
