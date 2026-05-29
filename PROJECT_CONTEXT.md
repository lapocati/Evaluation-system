# DialogEval · PROJECT_CONTEXT

> 多轮对话评测系统：用户输入"任务指令" → LLM 解析为分支 + 评分标准 → 双 NPC 流式跑对话 → 多维度自动打分出报告。
>
> 本文档是 **AI 接手项目的唯一权威说明**。继续开发前请先通读，不得偏离结构/规范。

---

## 1. 项目结构说明

```
evaluation system/
├── backend/                       # FastAPI 后端（DeepSeek 调用 / 评分聚合）
│   ├── app/
│   │   ├── main.py                # FastAPI 入口、CORS、路由挂载
│   │   ├── config.py              # DEEPSEEK_API_KEY 环境变量（get_deepseek_key）
│   │   ├── schemas.py             # Pydantic 数据契约（前后端共享 schema）
│   │   ├── termination.py         # 对话结束检测（关键词 + LLM 二次确认）
│   │   ├── llm/
│   │   │   └── deepseek.py        # DeepSeek API 封装（chat / chat_stream）
│   │   ├── prompts/               # 所有 system prompt 集中在此（纯文本/字符串）
│   │   │   ├── parser.py          # 指令解析器 prompt
│   │   │   ├── agent.py           # 被测数字人 system 模板
│   │   │   ├── npc.py             # 用户模拟器 system 模板
│   │   │   ├── scorer.py          # 单子项 LLM 评分 prompt
│   │   │   └── summary.py         # 优势/改进总结 prompt
│   │   ├── routes/                # FastAPI 路由层（薄）
│   │   │   ├── parse.py           # POST /api/parse_instruction
│   │   │   ├── simulate.py        # POST /api/simulate/stream （SSE）
│   │   │   └── evaluate.py        # POST /api/evaluate
│   │   └── scoring/               # 评分纯计算层（无 IO 副作用，可单测）
│   │       ├── rules.py           # 4 种规则评分
│   │       ├── keyword.py         # 关键词命中比例
│   │       ├── llm_scorer.py      # 单 LLM 子项打分
│   │       └── aggregator.py      # 维度聚合 + 效率 + summary → Report
│   ├── requirements.txt
│   └── README.md
│
├── frontend/                      # Vite + React + TS + Tailwind
│   ├── index.html
│   ├── vite.config.ts             # /api → http://localhost:8000 代理
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── main.tsx               # Root 渲染 + BrowserRouter
│       ├── App.tsx                # 路由表（4 个页面）
│       ├── index.css              # Tailwind 注入 + body 字体
│       ├── types.ts               # 全部前端 TS 类型（与后端 schema 对齐）
│       ├── api/                   # 网络层（fetch 封装，不持业务状态）
│       │   ├── parse.ts           # 解析指令
│       │   ├── simulate.ts        # SSE 流式驱动 + abort
│       │   └── evaluate.ts        # 评测请求
│       ├── store/
│       │   └── useAppStore.ts     # 单一 zustand store（全局唯一）
│       ├── data/
│       │   └── presets.ts         # 预置指令样例（静态数据）
│       ├── components/            # 复用 UI（无路由、无业务副作用）
│       │   ├── PresetCard.tsx
│       │   ├── BranchCard.tsx
│       │   ├── ChatBubble.tsx
│       │   ├── StatusPanel.tsx
│       │   ├── ScoreRadar.tsx
│       │   └── DimensionAccordion.tsx
│       └── pages/                 # 页面级容器（路由直挂）
│           ├── ConfigPage.tsx
│           ├── BranchesPage.tsx
│           ├── SimulatePage.tsx
│           └── ReportPage.tsx
└── PROJECT_CONTEXT.md             # ← 本文档
```

**架构边界（重要）：**

- `routes/*` 只做参数校验 + 错误码映射，业务逻辑**不能**写在里面。
- `scoring/*` 是纯函数 / 纯 async，**不许**直接 `import fastapi`。
- `prompts/*` 只导出字符串模板和 `build_*_messages()` 函数，**不**调 LLM。
- 前端 `pages/*` 只负责"路由 + 拼装 components + 调 api/* + 读写 store"。
- 前端 `components/*` 必须是**纯展示** + 回调，**禁止**直接 `fetch`、**禁止**读写 store 中的业务流程字段（详见第 5 节）。

---

## 2. 技术栈

### 后端

| 项 | 选型 | 版本约束 |
|---|---|---|
| 语言 | Python | ≥ 3.10（用到 `list[dict]`、`X \| None`） |
| 框架 | FastAPI | ≥ 0.115 |
| ASGI | uvicorn[standard] | ≥ 0.32 |
| HTTP 客户端 | httpx (async) | ≥ 0.27 |
| 校验 | pydantic v2 | ≥ 2.9 |
| SSE | sse-starlette | ≥ 2.1.3 |
| LLM | DeepSeek `deepseek-chat`（固定，不允许换模型/换 endpoint） | — |

### 前端

| 项 | 选型 | 版本约束 |
|---|---|---|
| 构建 | Vite | ^5.4 |
| 框架 | React | ^18.3 |
| 语言 | TypeScript | ^5.6（strict 模式） |
| 路由 | react-router-dom | ^6.27 |
| 状态 | zustand | ^5.0 |
| 图表 | recharts | ^2.13 |
| 样式 | Tailwind CSS | ^3.4 |

### 运行端口约定

- 后端：`http://localhost:8000`
- 前端：`http://localhost:5173`
- Vite 代理：所有 `/api/*` → `http://localhost:8000`
- CORS：后端只允许 `http://localhost:5173`

---

## 3. 组件树

```
<BrowserRouter>
  <App>
    Routes:
      "/"               → <Navigate to="/config" />
      "/config"         → <ConfigPage>
                            <PresetCard /> × N
                            <ModelKeyBox /> × 2   (页面内本地子组件)
                          </ConfigPage>
      "/branches"       → <BranchesPage>
                            <BranchCard /> × N
                          </BranchesPage>
      "/simulate/:id"   → <SimulatePage>
                            <StatusPanel />
                            <ChatBubble /> × N        (流式增长)
                          </SimulatePage>
      "/report/:id"     → <ReportPage>
                            ↳ <LoadingPanel> | <ErrorPanel> | <ReportBody>
                                                                ├ <ScoreRadar />
                                                                └ <DimensionAccordion>
                                                                    └ <DimensionRow> × 5
</BrowserRouter>
```

**复用规则：**

- `BranchCard`：用于 `/branches` 列表的卡片，承载"运行/查看/报告"三个回调。
- `ChatBubble`：流式气泡；agent 显示「第 N 轮 · 数字人」，user 仅显示「用户」；根据 `turn.done` 决定是否渲染闪烁光标。
- `StatusPanel`：状态徽章 + **agent 轮次**进度（非消息条数），硬上限 = `Math.ceil(estimated × 1.5)`（作用于 agent 轮数）。
- `ScoreRadar`：5 维 recharts 雷达，固定颜色 `#4f46e5`（stroke）/ `#6366f1`（fill）。
- `DimensionAccordion`：4 维评分维度 + 效率，单 source-of-truth 用于报告详情展开。
- `LoadingPanel` / `ErrorPanel` / `ReportBody`：**仅** `ReportPage` 内部使用的私有子组件，**不要**抽到 `components/`。

---

## 4. 页面逻辑

### 4.1 `/config`（ConfigPage）

**职责：** 收集任务指令；模型与 Key 区域为**展示用**（只读占位），真实 DeepSeek Key 由后端环境变量 `DEEPSEEK_API_KEY` 提供。

| 阶段 | 行为 |
|---|---|
| 进入 | 读取 store 中已存在的 `instruction` / `agentKey` / `evaluatorKey`（页面间不丢；Key 为预置占位假值，不可编辑） |
| 校验 | 必需字段正则：`#Role` / `#Task` / `#Opening Line` / `#Constraints`；Key 正则：`^sk-[A-Za-z0-9]{20,}$`（占位假 Key 默认已通过） |
| 点击预置 | 用 PRESETS 的 content 覆写 instruction |
| 点击"解析指令 →" | `POST /api/parse_instruction` → `setParseResult` → `navigate('/branches')` |
| 错误 | 顶部红色错误条显示 detail（不弹 alert） |

### 4.2 `/branches`（BranchesPage）

**职责：** 展示 LLM 解析出的分支，启动每个分支的 SSE 模拟。

- 进入若 `parseResult === null` → 引导回 `/config`。
- 全局只允许**一个** `runningBranchId`；其他分支按钮 disabled。
- "运行" → `runBranchSimulation(...)` → 立即 `navigate('/simulate/:id')`。
- 已完成（`ended` / `max_turns`）的分支会出现"查看报告"按钮。

### 4.3 `/simulate/:branchId`（SimulatePage）

**职责：** 渲染 SSE 流式增长的对话气泡 + 状态。

- 不会主动发起请求；由 `/branches` 触发后，本页面只**读 store**。
- 滚动：每次 `lastTurnText` 或 `lastTurnIndex` 变化时自动 scrollTop。
- "■ 终止运行"：调用 `abortBranch()` → AbortController.abort + 写入 `user_aborted`。
- 状态 `ended` / `max_turns` 显示"查看评测报告 →"。

### 4.4 `/report/:branchId`（ReportPage）

**职责：** 触发 `/api/evaluate`，按"综合分 / 雷达 / 优势改进 / 维度详情"四块布局展示。

- 进入时若 `reportEntry` 不存在且对话已结束 → 自动 `runEvaluate(...)`。
- 顶部分支切换按钮（不重新解析，只切 url）。
- Loading 时 spinner + 文案"10–30 秒"。
- Error 时显示重试按钮，重试只重发 evaluate。

### 4.5 SSE 事件协议（前后端约定，禁止改事件名）

**轮数语义：** 一问一答为一轮，agent 每次发言时轮数 +1；SSE `turn` 字段即轮数（user 消息继承所属轮数，与当轮 agent 相同）。`done.total_turns` = agent 发言次数。

| event | data | 触发动作 |
|---|---|---|
| `turn_start` | `{turn, role}` | `beginTurn()` — 以 `(turn, role)` 去重 |
| `delta` | `{turn, role, text}` | `appendDelta()` — 以 `(turn, role)` 定位 |
| `turn_end` | `{turn, role, text}` | `endTurn()`（用完整 text 覆盖） |
| `error` | `{turn, role, message}` | `errorConversation()` |
| `done` | `{reason, total_turns}` | `finishConversation()`，reason ∈ `ended / max_turns / user_aborted / llm_error`；`total_turns` = agent 轮数 |

---

## 5. 状态管理方式

**单一 zustand store：`src/store/useAppStore.ts`，全局只有这一份。**

### 状态切片

```ts
{
  // —— 配置层 ——
  instruction:    string,
  agentKey:       string,   // 展示占位假 Key；请求体仍携带，后端忽略
  evaluatorKey:   string,   // 展示占位假 Key；请求体仍携带，后端忽略
  parseResult:    ParseResult | null,

  // —— 模拟层 ——
  conversations:  Record<branchId, Conversation>,
  runningBranchId: string | null,         // 全局互斥锁

  // —— 报告层 ——
  reports:        Record<branchId, ReportEntry>,
}
```

### 写入规则（必须用 action，不直接 setState）

| Action | 调用方 |
|---|---|
| `setInstruction / setAgentKey / setEvaluatorKey` | ConfigPage（Key 输入框已只读，setter 保留兼容） |
| `setParseResult` | ConfigPage 解析成功（**会**清空 conversations & reports） |
| `startConversation / beginTurn / appendDelta / endTurn / finishConversation / errorConversation` | **仅** `api/simulate.ts` |
| `startReport / setReport / errorReport` | **仅** `api/evaluate.ts` |

### 不变量（违反会破坏体验，必须保持）

1. **`runningBranchId` 全局唯一**：开始一条新对话前必须确认它为 `null`。
2. **`parseResult` 重置语义**：重新解析必须清掉旧的 `conversations` 和 `reports`。
3. **`turn` 不可逆**：`turn_end` 收到的 text 永远覆盖 delta 累计值（后端是真源）。
4. **`(turn, role)` 复合键**：同轮 user/agent 共享 `turn` 值，store 去重与 delta 定位必须用 `(turn, role)`，不能单用 `turn`。
5. **报告与对话绑定**：同 `branchId` 重新运行对话 → 立刻删除该 branch 的 report。
6. **store 不放派生数据**（如 overall%、颜色 class），派生在组件内 `useMemo` 计算。

### 组件订阅习惯

- 页面用 `useAppStore((s) => s.xxx)` **分片**订阅，**避免**整体解构导致全树重渲染。
- 在事件回调里读快照请用 `useAppStore.getState()`，**不**在事件中订阅。

---

## 6. UI 设计规范

### 6.1 调色板（Tailwind 默认色阶）

| 用途 | 颜色 |
|---|---|
| 全局背景 | `bg-slate-50` |
| 卡片背景 | `bg-white` |
| 卡片边框 | `border-slate-200` |
| 主文本 | `text-slate-800` |
| 次文本 | `text-slate-500` / `text-slate-600` |
| 微文本 / 标签 | `text-slate-400` |
| 主操作 / 链接 | `indigo-600`，hover `indigo-700` |
| 成功（已完成 / 优势 / 报告 CTA） | `emerald-*` |
| 警告（运行中 / 超出预估） | `amber-*` / `orange-*` |
| 危险（终止 / 错误 / 改进项） | `rose-*` / `red-*` |
| 不适用 / 中性禁用 | `slate-200 / slate-300 / slate-600` |

> ❗ **禁止**自定义 hex 色值（除 `ScoreRadar` 已固定的 `#4f46e5 / #6366f1 / #e2e8f0 / #cbd5e1 / #475569 / #94a3b8`）。新增色彩必须用 Tailwind 调色板里的对应色阶。

### 6.2 圆角 & 间距

| 元素 | 圆角 |
|---|---|
| 卡片 / 面板 | `rounded-xl` |
| 输入框 / 按钮 / 标签 | `rounded-md` 或 `rounded-lg` |
| 状态徽章 | `rounded-full` |
| 气泡 | `rounded-2xl` |

- 页面容器统一 `max-w-3xl / 4xl / 5xl mx-auto p-6 space-y-*`，**不**自创 margin 体系。
- 卡片内 padding：`p-4` / `p-5`；section 间距 `space-y-5` 或 `space-y-6`。

### 6.3 排版

- 字体：`-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif`（已在 `index.css`，**禁止**改）。
- 标题：`text-2xl font-bold text-slate-800`（页面 H1）/ `text-xl`（次级）。
- Body：`text-sm`；辅助说明：`text-xs`；代码：`font-mono text-sm`。
- 行高紧凑文本（气泡、reason）：`leading-relaxed`。

### 6.4 按钮

- 主按钮：`bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition`
- 报告 CTA：`bg-emerald-600 ... hover:bg-emerald-700`
- 危险（终止）：`bg-rose-600 ... hover:bg-rose-700`
- 次要：`border border-slate-300 text-slate-700 hover:bg-slate-50`
- 内边距：`px-3 py-1.5`（中）/ `px-5 py-2`（大）/ `px-2.5 py-1`（小标签按钮）
- 所有按钮**必须**带 `type="button"`（除非在 form 提交场景）。

### 6.5 分数色

`colorForOverall` / `colorForScore` 是全局色阶约定，新增展示分数处必须遵循：

| 分数区间 | 文本色 | 背景色 / bar |
|---|---|---|
| ≥ 0.8 | `text-emerald-700` | `bg-emerald-100` / `bg-emerald-500` |
| 0.5 – 0.8 | `text-amber-700` | `bg-amber-100` / `bg-amber-500` |
| < 0.5 | `text-rose-700` | `bg-rose-100` / `bg-rose-500` |
| null（不适用） | `text-slate-600` | `bg-slate-200` |

---

## 7. 动效规范

**原则：动效只用于"状态变化的可感知"，不做装饰性运动。**

| 场景 | 实现 |
|---|---|
| 按钮 hover / 选中态切换 | `transition`（Tailwind 默认 150ms） |
| 综合分进度条增长 | `transition-all duration-500`（独此一处用 500ms） |
| 评测 Loading spinner | `animate-spin`（Tailwind 默认） |
| 流式气泡光标闪烁 | `animate-pulse` 的 `▍` 字符 |
| 手风琴展开 | 无动画，直接条件渲染（保持轻量） |

❌ **禁止**：framer-motion / gsap / 自定义 keyframes / 大于 500ms 的过渡 / 入场抖动 / 视差。

---

## 8. 命名规范

### 8.1 文件 & 目录

| 类型 | 命名 | 例 |
|---|---|---|
| React 组件 | `PascalCase.tsx` | `BranchCard.tsx` |
| Hook | `useXxx.ts` | `useAppStore.ts` |
| 工具/网络 | `camelCase.ts` | `simulate.ts` |
| Python 模块 | `snake_case.py` | `llm_scorer.py` |
| 后端目录 | `snake_case` | `routes/`, `prompts/`, `scoring/` |

### 8.2 标识符

| 类型 | 风格 |
|---|---|
| TS 类型 / interface | `PascalCase`（`Branch`, `ReportEntry`） |
| TS 联合字面量 | `snake_case` 字符串（与后端一致：`'task_completion'` / `'max_turns'`） |
| TS 变量 / 函数 | `camelCase` |
| TS 常量集合 | `UPPER_SNAKE`（`PRESETS`, `REQUIRED_FIELDS`, `DIM_LABEL`） |
| Python class / Pydantic | `PascalCase` |
| Python 变量 / 函数 | `snake_case` |
| Python 常量 | `UPPER_SNAKE`（`NON_EFFICIENCY_DIMS`, `LLM_CONCURRENCY`） |
| API 路径 | `/api/<verb_noun>` 全小写下划线（`/api/parse_instruction`, `/api/simulate/stream`） |
| JSON 字段（前后端契约） | `snake_case`（`estimated_max_turns`, `total_turns`, `evaluator_key`） |
| Store action | 动词开头 camelCase（`startConversation`, `appendDelta`） |
| 分支 id | 大写单字母 `A / B / C / D` |
| 评分子项 id | `<dim 前缀>_<序号>`（`tc_1`, `if_2`） |

### 8.3 维度与状态枚举（不可改名）

```
DimensionKey: task_completion | instruction_following | naturalness | branch_handling
EvalType:     rule | keyword | llm
ConvStatus:   running | ended | max_turns | user_aborted | llm_error
Rules:        max_chars_per_turn | no_repetition | forbidden_words | required_opening
```

新增维度 / 规则前必须修改：`schemas.py`、`types.ts`、`prompts/parser.py`、`aggregator.NON_EFFICIENCY_DIMS`、`DimensionAccordion.DIM_LABEL`、`ScoreRadar.DIM_LABEL`、`rules.evaluate_rule`。

---

## 9. 禁止事项

### 9.1 架构 / 依赖

- ❌ **禁止**新增前端状态库（redux、jotai、recoil 等）；只有 zustand。
- ❌ **禁止**新增 UI 库（antd、mui、shadcn 等）；只用 Tailwind 原子类。
- ❌ **禁止**新增图表库；图表统一用 recharts。
- ❌ **禁止**在前端引入 axios / swr / react-query；用原生 `fetch`。
- ❌ **禁止**在后端新增数据库 / 缓存 / Redis；当前系统是无状态的。
- ❌ **禁止**替换 DeepSeek 为其他 LLM（OpenAI、Anthropic 等），endpoint 与模型名固定。

### 9.2 代码层面

- ❌ **禁止**在 `routes/*.py` 里写业务逻辑（评分计算、prompt 拼接）。
- ❌ **禁止**在 `prompts/*.py` 里调 LLM；它们只导出字符串。
- ❌ **禁止**在 `components/*.tsx` 里直接 `fetch` 或导入 `api/*`。
- ❌ **禁止**绕过 store action 直接 `useAppStore.setState({...})` 操作业务字段。
- ❌ **禁止**修改 SSE 事件名（`turn_start / delta / turn_end / error / done`），前后端紧耦合。
- ❌ **禁止**修改 JSON 字段命名风格（前端 snake_case 与后端契约一致；不要为了"前端规范"改成 camelCase）。
- ❌ **禁止**在 `index.css` 加全局 class；样式一律用 Tailwind 原子类。
- ❌ **禁止**引入 CSS Modules / styled-components / emotion。
- ❌ **禁止**写无意义注释（`// 设置 state`、`// 调用接口`）；注释只解释"为什么"。
- ❌ **禁止**在 TS 中用 `any`；用 `unknown` + narrowing。

### 9.3 LLM / 评测

- ❌ **禁止**把 `agentKey` / `evaluatorKey` 持久化到 localStorage / cookie / 后端数据库（store 内仅为展示占位假值）。
- ✅ **真实** DeepSeek Key 仅存后端环境变量 `DEEPSEEK_API_KEY`（见 `backend/.env.example`）；路由层通过 `app/config.py` 的 `get_deepseek_key()` 读取，**忽略**请求体中的 key 字段。
- ❌ **禁止**在解析 LLM 返回后跳过 `ParseResponse(**data)` 校验。
- ❌ **禁止**让 LLM 评分返回非 [0,1] 区间的分数（必须 clamp）。
- ❌ **禁止**修改 `weight = 0.35/0.25/0.15/0.15/0.10` 的默认权重契约（parser prompt 已写死）。
- ❌ **禁止**修改硬上限公式 `hard_max = ceil(estimated × 1.5)`（前后端共识；比较对象为 **agent 轮数**，达限后允许当前轮 user 说完）。

### 9.4 UX

- ❌ **禁止**用 `alert` / `confirm` / `prompt`；错误用红色条，确认用页面跳转或行内按钮。
- ❌ **禁止**自动跳转覆盖用户当前页（除"解析成功 → /branches"是显式动作）。
- ❌ **禁止**让用户在对话进行中开第二条对话（runningBranchId 互斥锁）。
- ❌ **禁止**渲染不在 `STATUS_LABEL` / `STATUS_META` 里的状态字符串。

---

## 10. 后续开发原则

### 10.1 任务最小化

1. **改一处只改一处**。例如要加新规则评分：
   - 必改：`schemas.py`（不必，eval_type 已是字面量） → `scoring/rules.py` 新分支 → `prompts/parser.py` 新规则说明。
   - 不许改：UI 样式、store 形状、SSE 事件。
2. 不重构与本任务无关的代码（即使看着丑）。
3. PR / commit 信息一句话说清"做了什么、为什么"。

### 10.2 类型与契约先行

- 后端先改 `schemas.py`，再改 `routes/*`，再改 `scoring/*`。
- 前端先改 `types.ts`，再改 `api/*`，再改 `store`，最后改 UI。
- 任何新字段必须在前后端**同时**加，否则 PR 不完整。

### 10.3 错误处理

| 层 | 策略 |
|---|---|
| LLM 调用 | 统一抛 `DeepSeekError`；上层判断后返回 HTTP 502 或写入 status |
| `/api/parse_instruction` JSON 错 | 422 + `{error, msg, raw}` 三段 |
| `/api/simulate/stream` | 错误以 `event: error` + `event: done(reason=llm_error)` 推回前端，不抛 HTTP |
| `/api/evaluate` LLM summary 失败 | 静默返回空 `advantages/improvements`，**不**让整份报告失败 |
| 前端 fetch 异常 | 写入对应 store 的 `error*` action，UI 渲染红色条 + 重试 |

### 10.4 性能

- LLM 评分并发：`asyncio.Semaphore(LLM_CONCURRENCY = 8)`，新增 LLM 调用必须走 semaphore。
- 流式逐 token：前端用 `delta` 累加，`turn_end` 收到后覆盖一次完整 text 校正。
- store 订阅按字段切片，避免组件大面积重渲染（尤其 SimulatePage 流式期间）。

### 10.5 兼容性

- Python ≥ 3.10、Node ≥ 18、浏览器 ≥ Edge/Chrome/Safari 现代版。
- SSE 解析同时兼容 `\r\n\r\n` 与 `\n\n` 分隔（已实现于 `api/simulate.ts`）。
- 字符串严格使用中文标点 / 全角，UI 复制粘贴的"…"等保持原样。

### 10.6 新功能落点速查

| 想做什么 | 改哪里 |
|---|---|
| 加一个预置任务 | `frontend/src/data/presets.ts` |
| 加一个 LLM 模型 | **禁止**，仅 deepseek-chat |
| 加一种规则类评分 | `backend/app/scoring/rules.py` + `prompts/parser.py` 说明 |
| 加一个评分维度 | 走完第 8.3 节的全部 7 个文件 |
| 改卡片视觉 | 只动 `components/*.tsx`，不改逻辑 |
| 换报告布局 | 只动 `pages/ReportPage.tsx` 的 `ReportBody` 块 |
| 加一条 SSE 事件类型 | **禁止**（先和负责人讨论） |
| 接入持久化 | **禁止**（项目定位为无状态评测，要做请重新设计架构） |

### 10.7 如需用户配合的事项

如下情况**必须**先告知用户、获得明确同意：

- 安装新依赖（package.json / requirements.txt 任一新增）；
- 修改端口 / 代理 / CORS；
- 让用户提供 / 配置新的 API Key 或第三方服务；
- 任何超过 50 行的非新增文件改动。

---

> 📌 **本文件由 AI 接手任何工作前必须先读一遍。**
> 若开发任务与本文档冲突，**先停下来跟用户确认**，不要私自重构。
