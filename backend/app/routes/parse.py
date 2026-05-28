import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.llm.deepseek import DeepSeekError, chat
from app.prompts.parser import build_parser_messages
from app.schemas import ParseRequest, ParseResponse
from app.scoring.criteria_normalize import normalize_scoring_criteria

logger = logging.getLogger("dialogeval.parse")
logger.setLevel(logging.INFO)
router = APIRouter()
_DEBUG_LOG_7BE968 = Path(__file__).resolve().parents[3] / "debug-7be968.log"


def _dbg7(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    # #region agent log
    payload = {
        "sessionId": "7be968",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG_7BE968.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


@router.post("/parse_instruction", response_model=ParseResponse)
async def parse_instruction(req: ParseRequest) -> ParseResponse:
    messages = build_parser_messages(req.instruction)
    try:
        raw = await chat(
            messages,
            req.api_key,
            response_format_json=True,
            temperature=0.3,
        )
    except DeepSeekError as e:
        _dbg7(
            "H1",
            "parse.py:parse_instruction",
            "deepseek_error",
            {
                "error": str(e)[:400],
                "keyLen": len(req.api_key or ""),
                "keyEmpty": not bool(req.api_key and req.api_key.strip()),
                "instructionLen": len(req.instruction or ""),
            },
        )
        logger.error("DeepSeek error: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM 调用失败：{e}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("parse_failed, raw=%r", raw)
        raise HTTPException(
            status_code=422,
            detail={"error": "parse_failed", "msg": "LLM 返回非合法 JSON", "raw": raw},
        )

    try:
        result = ParseResponse(**data)
        return normalize_scoring_criteria(result)
    except Exception as e:
        logger.error("schema_invalid: %s\nraw=%s", e, raw)
        raise HTTPException(
            status_code=422,
            detail={"error": "schema_invalid", "msg": str(e), "raw": raw},
        ) from e
