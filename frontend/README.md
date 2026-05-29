# DialogEval Frontend

Vite + React + TypeScript + Tailwind + React Router + Zustand。

## 启动

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`。Vite 已将 `/api/*` 代理到 `http://127.0.0.1:8010`，须先在 `backend` 配置 `.env` 并启动后端。

## 当前状态（Phase 1）

| 路由 | 页面 | 状态 |
|---|---|---|
| `/config`   | 任务配置页（预置卡片 + 4 输入框 + 字段校验） | Phase 1 完成 |
| `/branches` | 临时调试页（展示 parser JSON 结构）          | Phase 1 占位 |
| `/simulate/:id` | 对话模拟页 | Phase 2 待实现 |
| `/report/:id`   | 报告页     | Phase 3 待实现 |
