"""服务端 DeepSeek API Key（环境变量，不来自请求体）。"""
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_PATH = _BACKEND_DIR / ".env"
_DEBUG_LOG_BDD1EC = Path(__file__).resolve().parents[2] / "debug-bdd1ec.log"

load_dotenv(_ENV_PATH)


def _dbg_bdd1ec(hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    # #region agent log
    payload = {
        "sessionId": "bdd1ec",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with _DEBUG_LOG_BDD1EC.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


def get_deepseek_key() -> str:
    load_dotenv(_ENV_PATH, override=True)
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip().strip('"').strip("'")
    suffix = key[-4:] if len(key) >= 4 else ""
    _dbg_bdd1ec(
        "H1",
        "config.py:get_deepseek_key",
        "key_resolved",
        {
            "envFileExists": _ENV_PATH.is_file(),
            "envPath": str(_ENV_PATH),
            "keyLen": len(key),
            "keySuffix": suffix,
            "looksPlaceholder": bool(
                key
                and (
                    "your-key" in key
                    or key.endswith("xxxxxxxx")
                    or key.count("x") > 12
                )
            ),
            "fromOsEnv": bool(os.environ.get("DEEPSEEK_API_KEY")),
        },
    )
    if not key:
        raise RuntimeError(
            "服务端未配置 DeepSeek API Key。请在 backend 目录复制 .env.example 为 .env，"
            "并填入有效的 DEEPSEEK_API_KEY，然后重启后端。"
        )
    return key
