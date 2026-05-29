from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import evaluate, parse, simulate

app = FastAPI(title="DialogEval Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(evaluate.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
