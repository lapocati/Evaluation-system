# DialogEval Backend

FastAPI + DeepSeek 官方 API。

## 启动

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

健康检查：`GET http://localhost:8000/api/health` → `{"status":"ok"}`

## 路由

| 路由 | 状态 |
|---|---|
| `POST /api/parse_instruction` | Phase 1 已实现 |
| `POST /api/simulate/stream`   | Phase 2 待实现 |
| `POST /api/evaluate`          | Phase 3 待实现 |
