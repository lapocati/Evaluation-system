"""服务端 DeepSeek API Key（环境变量，不来自请求体）。"""
import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_PATH = _BACKEND_DIR / ".env"

load_dotenv(_ENV_PATH)


def get_deepseek_key() -> str:
    load_dotenv(_ENV_PATH)
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("服务端未配置 API Key")
    return key
