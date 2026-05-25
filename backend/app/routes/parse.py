import json
import logging

from fastapi import APIRouter, HTTPException

from app.llm.deepseek import DeepSeekError, chat
from app.prompts.parser import build_parser_messages
from app.schemas import ParseRequest, ParseResponse

logger = logging.getLogger("dialogeval.parse")
logger.setLevel(logging.INFO)
router = APIRouter()


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
        return ParseResponse(**data)
    except Exception as e:
        logger.error("schema_invalid: %s\nraw=%s", e, raw)
        raise HTTPException(
            status_code=422,
            detail={"error": "schema_invalid", "msg": str(e), "raw": raw},
        ) from e
