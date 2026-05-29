"""POST /api/evaluate —— Rule + Keyword + LLM 子项并发 → 五维度汇总 → summary。"""
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.config import get_deepseek_key
from app.schemas import EvaluateRequest, Report
from app.scoring.aggregator import build_report

logger = logging.getLogger("dialogeval.evaluate")
logger.setLevel(logging.INFO)
router = APIRouter()


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload, ensure_ascii=False)}


async def _run_build_report(req: EvaluateRequest, evaluator_key: str, on_event=None) -> Report:
    return await build_report(
        branch=req.branch,
        conversation=req.conversation,
        scoring_criteria=req.scoring_criteria,
        evaluator_key=evaluator_key,
        tone_summary=req.tone_summary,
        on_event=on_event,
    )


@router.post("/evaluate", response_model=Report)
async def evaluate(req: EvaluateRequest) -> Report:
    if not req.conversation.turns:
        raise HTTPException(status_code=400, detail="对话为空，无法评测")
    try:
        evaluator_key = get_deepseek_key()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    try:
        report = await _run_build_report(req, evaluator_key)
    except Exception as e:
        logger.exception("evaluate failed")
        raise HTTPException(status_code=500, detail=f"评测异常：{e}") from e
    return report


@router.post("/evaluate/stream")
async def evaluate_stream(req: EvaluateRequest, request: Request):
    # #region agent log
    import time
    from pathlib import Path
    _log = Path(__file__).resolve().parents[3] / "debug-fb3d39.log"
    with _log.open("a", encoding="utf-8") as _f:
        _f.write(json.dumps({"sessionId": "fb3d39", "hypothesisId": "H1", "location": "evaluate.py:evaluate_stream", "message": "route_hit", "data": {"branch_id": req.branch.id}, "timestamp": int(time.time() * 1000)}, ensure_ascii=False) + "\n")
    # #endregion
    if not req.conversation.turns:
        raise HTTPException(status_code=400, detail="对话为空，无法评测")
    try:
        evaluator_key = get_deepseek_key()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    async def event_gen():
        queue: asyncio.Queue = asyncio.Queue()

        async def on_event(event: str, data: dict) -> None:
            await queue.put(_sse(event, data))

        async def runner() -> None:
            try:
                report = await _run_build_report(req, evaluator_key, on_event=on_event)
                await queue.put(_sse("done", report.model_dump()))
            except Exception as e:
                logger.exception("evaluate stream failed")
                await queue.put(_sse("error", {"message": f"评测异常：{e}"}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(runner())
        try:
            while True:
                msg = await queue.get()
                if msg is None:
                    break
                yield msg
                if await request.is_disconnected():
                    break
        finally:
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_gen())
