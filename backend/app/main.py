from contextlib import asynccontextmanager
import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.llm.deepseek import close_http_client, init_http_client
from app.routes import evaluate, parse, simulate

_LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]


def _cors_settings() -> tuple[list[str], str | None]:
    extras = [
        item.strip().rstrip("/")
        for item in os.environ.get("CORS_ORIGINS", "").split(",")
        if item.strip()
    ]
    exact: list[str] = []
    regex_parts: list[str] = []
    for origin in extras:
        if "*" in origin:
            regex_parts.append("^" + re.escape(origin).replace(r"\*", r".*") + "$")
        else:
            exact.append(origin)
    origins = list(dict.fromkeys(_LOCAL_ORIGINS + exact))
    return origins, "|".join(regex_parts) if regex_parts else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_http_client()
    yield
    await close_http_client()


app = FastAPI(title="DialogEval Backend", version="0.1.0", lifespan=lifespan)

_cors_origins, _cors_origin_regex = _cors_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(evaluate.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    configured = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    return {
        "status": "ok",
        "project": "evaluation-system",
        "online_configured": configured,
    }
