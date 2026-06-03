# ConvoMatrix · 复杂指令下的多轮对话评测系统

> **DialogEval** — 让 AI 从「会聊天」，走向「能办事」

将任意复杂、格式不统一的任务指令，自动解析为**统一五维评分标准**，通过多分支对话模拟与可解释报告，评测对话式 AI / 数字人「能不能把事办成」。

---

## 核心能力

- **指令无关的统一评测**：粘贴业务 SOP 即可生成 rubric，无需为每条指令单独写脚本
- **复杂语义可拆解**：主动步骤 / 条件响应 / FAQ / 占位符分类评分，避免误扣与漏评
- **多分支覆盖**：自动生成配合型、拒绝型、质疑型等用户路径并分别跑测
- **可解释报告**：五维雷达图 + 每个子项的中文评分理由

详细产品介绍见 [`docs/项目介绍.md`](docs/项目介绍.md)。

---

## 关于 API Key（重要）

本仓库**不会、也不应**包含任何真实的 API Key。`.env` 已在 `.gitignore` 中忽略。

| 说明 | 详情 |
|------|------|
| **谁提供 Key？** | 每位使用者需自行注册 [DeepSeek 开放平台](https://platform.deepseek.com/) 并创建 API Key |
| **Key 存哪里？** | 仅写在本地 `backend/.env` 中，由**服务端**读取，不会提交到 Git |
| **前端页面的 Key 输入框？** | 仅为 UI 占位与格式校验，**后端会忽略**请求体中的 key，真实调用一律使用 `backend/.env` |
| **费用** | 解析、对话模拟、评分均会调用 DeepSeek API，消耗的是你账号下的额度 |

克隆仓库后，**必须先配置自己的 Key 才能完整运行**（解析 / 模拟 / 评分三步都依赖 LLM）。

---

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | ≥ 3.10 |
| Node.js | ≥ 18 |
| DeepSeek API Key | 自行申请 |

---

## 快速开始（本地开发）

### 1. 克隆仓库

```bash
git clone https://github.com/lapocati/Evaluation-system.git
cd Evaluation-system
```

### 2. 配置 API Key

```bash
cd backend
cp .env.example .env
```

编辑 `backend/.env`，填入你的 Key（等号后不要加引号）：

```env
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
```

Key 申请地址：<https://platform.deepseek.com/api_keys>

### 3. 启动后端

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8010
```

健康检查：<http://127.0.0.1:8010/api/health> → `{"status":"ok"}`

### 4. 启动前端

新开一个终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问：<http://localhost:5173>

开发模式下前端直连 `http://127.0.0.1:8010`（见 `frontend/src/lib/apiBase.ts`）。

### 5. 体验 Demo

1. 打开配置页，选择预置指令（如「美团外卖·飞毛腿骑手通知」）
2. 点击 **解析指令** → 查看自动生成的分支与评分维度
3. 选择分支 **运行** → 观看流式对话
4. 对话结束后查看 **评测报告**（五维雷达 + 子项理由）

---

## Docker 部署（生产 / 演示）

适用于在一台机器上通过 Nginx 统一对外提供前端与 API。

### 1. 配置 Key 并构建前端

```bash
# 配置服务端 Key
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 DEEPSEEK_API_KEY

# 构建前端静态资源
cd frontend
npm install
npm run build
cd ..
```

### 2. 启动容器

```bash
docker compose up --build -d
```

访问：<http://localhost>（80 端口）

- 前端：`/` → `frontend/dist`
- API：`/api/*` → 反向代理到 FastAPI `:8010`

停止服务：

```bash
docker compose down
```

---

## 项目结构

```
.
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── prompts/         # Parser / Scorer 等 Prompt
│   │   ├── routes/          # parse / simulate / evaluate API
│   │   └── scoring/         # 规则评分、聚合、归一化
│   ├── .env.example         # Key 配置模板（复制为 .env）
│   └── requirements.txt
├── frontend/                # Vite + React + TypeScript
│   └── src/
│       ├── pages/           # 配置 / 分支 / 模拟 / 报告
│       └── data/presets.ts  # 预置 Demo 指令
├── docs/
│   ├── 项目介绍.md          # 产品介绍（评委 / 文档用）
│   └── SCORING_MECHANISM.md # 评分机制说明
├── docker-compose.yml
└── nginx.conf
```

---

## API 概览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/parse_instruction` | POST | 解析任务指令 → 分支 + 评分标准 |
| `/api/simulate/stream` | POST | SSE 流式双 LLM 对话模拟 |
| `/api/evaluate` | POST | 对话结束后多维评分 + 报告 |

---

## 常见问题

**Q：没有 Key 能打开页面吗？**  
可以打开前端，但点击「解析指令」时后端会报错：`服务端未配置 DeepSeek API Key`。必须配置 `backend/.env`。

**Q：可以用 OpenAI / 其他模型吗？**  
当前版本固定使用 DeepSeek `deepseek-chat`，更换模型需改后端 `app/llm/deepseek.py` 及相关配置。

**Q：Docker 启动后 502？**  
确认 `backend/.env` 中 Key 有效，且已执行 `frontend/npm run build` 生成 `frontend/dist`。

**Q：评分很慢？**  
单次评测会对多个子项并发调用 LLM，通常需 10–30 秒，属正常现象。

---

## 技术栈

- **后端**：FastAPI · httpx · pydantic · sse-starlette · DeepSeek API
- **前端**：React 18 · TypeScript · Vite · Tailwind CSS · Zustand · Recharts
- **部署**：Docker · Nginx

---

## License

本项目为黑客松作品。如需商用或二次发布，请联系作者确认。
