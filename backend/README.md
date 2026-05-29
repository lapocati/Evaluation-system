# DialogEval Backend

FastAPI + DeepSeek 官方 API。

## 启动

```powershell
cd backend
copy .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-你的真实密钥
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

本地前端 Vite 默认将 `/api` 代理到 `http://localhost:8010`（避免 8000 端口残留进程干扰）。

健康检查：`GET http://localhost:8000/api/health` → `{"status":"ok"}`

## 路由

| 路由 | 状态 |
|---|---|
| `POST /api/parse_instruction` | Phase 1 已实现 |
| `POST /api/simulate/stream`   | Phase 2 待实现 |
| `POST /api/evaluate`          | Phase 3 待实现 |
