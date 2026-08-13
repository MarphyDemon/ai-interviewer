# 迭代方案：首页拆分 + UI 改造 + 数字人学习 Chat

> 版本：v1.0 · 2026-08-14
> 状态：已确认，逐步实施中
> 来源：grill-me 需求对齐结论

## 1. 背景与目标

当前问题：
1. 首页 [HomeView.vue](../src/views/HomeView.vue) 是大杂烩——开始面试、历史、管理、题库上传/列表、简历上传/列表全挤一页
2. UI 过于单调——只有功能按钮，无配色/样式/视觉设计
3. 缺少非面试场景的"学习问答"入口——用户无法就单个知识点向数字人提问

目标：拆分信息架构、建立统一设计系统、新增"和数字人聊天学习"的 Chat 界面。

## 2. 已确认决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | chat 形态 | 文字优先 + 数字人可选侧栏（TTS 播报 / ASR 输入，可开关） |
| 2 | chat 知识来源 | RAG 检索题库知识库回答（不做岗位过滤，LLM 自判相关性） |
| 3 | chat 历史 | 持久化 + ChatGPT 式左侧会话列表 |
| 4 | IA 重构 | 知识库→`/admin`；简历→`/setup`；chat→新路由 `/chat`；首页→落地介绍页；顶部全局导航 |
| 5 | chat 交互 | 流式 SSE 输出 + 标准会话管理（自动标题/重命名/删除/切换） |
| 6 | 视觉方向 | 靛紫渐变（indigo→violet）+ 现代 SaaS 落地页 + 全站统一设计系统 |

## 3. 信息架构（拆分后）

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 首页（落地页） | 产品介绍 + 功能入口（开始面试 / 与数字人聊天 / 历史记录 / 管理配置） |
| `/setup` | 面试配置 | 岗位/难度/时长/风格选择 + **简历管理（上传/列表/删除/轻量分析）** |
| `/interview` | 面试进行 | 数字人 + 对话 + 回答输入（沉浸式，无顶部导航） |
| `/chat` | 数字人学习 Chat | 三栏：左会话列表 / 中对话流 / 右可选数字人侧栏 |
| `/report/:id` | 点评报告 | 面试结果展示 + PDF 导出 |
| `/history` | 历史记录 | 面试历史列表 |
| `/admin` | 管理页 | LLM 配置（口令保护）+ **知识库管理（上传/列表/删除）** |

导航策略：顶部导航栏贯穿除 `/interview` 外的所有页面。

## 4. 实现范围

### 4.1 后端（新增）
- `server/routers/chat.py` — SSE 流式聊天接口 + 会话 CRUD
- 新模型（`server/models/__init__.py`）：
  - `ChatConversation`：id / user_id / title / created_at / updated_at
  - `ChatMessage`：id / conversation_id / role / content / created_at
- `server/services/chat_service.py` — 复用 [rag_service.py](../server/services/rag_service.py) 检索（去岗位过滤）+ [llm_service.py](../server/services/llm_service.py) 流式生成 + 首条消息截取生成标题
- `server/main.py` 注册 chat router

### 4.2 后端（无改动）
- knowledge / resume API 不动，仅前端入口迁移

### 4.3 前端（新增）
- `src/views/ChatView.vue` — 三栏布局
- `src/stores/chat.ts` + `src/api/chat.ts`（SSE 处理 + 会话 CRUD）
- 扩展 `src/components/chat/`（会话列表、流式消息渲染）
- 路由 `/chat`

### 4.4 前端（改造）
- [HomeView.vue](../src/views/HomeView.vue) → 重写为落地页（Hero + 功能卡片 + footer）
- [InterviewSetupView.vue](../src/views/InterviewSetupView.vue) → 增加简历管理区
- [AdminView.vue](../src/views/AdminView.vue) → 增加知识库管理区
- 新增 `src/components/common/AppNav.vue` 顶部导航
- [tailwind.config.js](../tailwind.config.js) → 定义靛紫设计系统（色板/阴影/圆角/间距），全站套用
- [App.vue](../src/App.vue) → 引入 AppNav（interview 路由除外）

## 5. 设计系统规范

- **主色**：indigo（#6366f1 系）→ violet（#8b5cf6 系）渐变
- **语义色**：success 绿 / warning 琥珀 / danger 红 / info 天蓝
- **圆角**：卡片 rounded-2xl，按钮 rounded-xl，输入 rounded-lg
- **阴影**：soft shadow 体系（sm/md/lg/xl）
- **字体**：系统字体栈 + 渐变文字工具类

## 6. 风险与对策

1. **SSE 经 vite 代理 + uvicorn**：dev 代理需关 buffer；勿起多个 8000 端口进程（历史教训：多 uvicorn 进程导致 30000ms 超时）。
2. **chat RAG 无岗位过滤**：可能检索到无关块 → prompt 中让 LLM 判断"如不相关则忽略"，无有效检索时退化为纯 LLM 回答。
3. **知识库进 /admin**：/admin 已有口令保护，天然隔离普通用户。
4. **数字人接入 chat**：复用现有 `AvatarProvider.speak()`；TTS 默认关、用户手动开；文字渲染不被 TTS 阻塞。
5. **范围较大**：分 5 步实施（见下）。

## 7. 实施顺序

1. **设计系统 + 顶部导航 + HomeView 落地页**（第 2、4 点 UI 部分）
2. **IA 拆分**：简历移入 /setup、知识库移入 /admin（第 1 点）
3. **chat 后端**：模型 + chat_service + SSE router（第 3 点地基）
4. **chat 前端**：ChatView 三栏 + 会话管理 + 流式渲染（第 3 点）
5. **chat 数字人侧栏**：TTS/ASR 接入（第 3 点增强）
