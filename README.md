# 🎭 具身面试官 · Embodied Interviewer

[![CI](https://github.com/MarphyDemon/ai-interviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/MarphyDemon/ai-interviewer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Vue 3](https://img.shields.io/badge/Vue-3-42b883)
![FastAPI](https://img.shields.io/badge/FastAPI-009688)
![Docker Compose](https://img.shields.io/badge/Docker%20Compose-ready-2496ED)

> **以 3D 具身交互智能体为交互界面、以 LLM + RAG 为大脑、以 Function Calling 为手脚的面试训练智能体。**
>
> 用户上传简历、选择岗位方向，由具身交互智能体面试官按题库知识点与简历内容进行语音问答；面试全程由显式状态机编排、可被中途打断，结束后输出多维度点评报告。

具身交互能力基于 [魔珐星云](https://www.xingyun3d.com) `@xmov/avatar` SDK 构建。

**直达入口：**[快速开始](#quickstart) · [演示视频](#demo) · [系统架构](#architecture) · [能力边界](#limits)

***

<a id="demo"></a>

## 🎬 演示视频

> 🎬 **3\~5 分钟端到端录屏**：待录制，占位待补。
>
> 录制完成后，把视频链接（或 `docs/demo.mp4`）替换到此处。

***

## ✨ 核心能力

能力按 **表达 · 交互 · 行动** 三层组织——分别对应「能说话/有形象」「有状态/有记忆」「能动手调工具」。

### 表达层 · 会说话、有形象

- **具身交互智能体**：`@xmov/avatar` Agent 模式，WebGL2 端侧渲染，口型 / 表情 / 关键动作随语义驱动
- **语音优先**：麦克风 → ASR → LLM → TTS 播报，字幕与语音同步；文字输入兜底
- **多级降级**：WebGL 硬件加速 → Lottie 形象 + 浏览器语音（Web Speech），弱环境仍可用

### 交互层 · 有状态、有记忆、可打断

- **面试流程状态机**：`opening → ask ⇄ followup → algorithm → judge → closing → report → finished`，带合法转移约束，防止 LLM 乱跳流程
- **跨会话记忆**：历史面试沉淀为薄弱点画像，供后续出题与点评引用
- **富交互 Widget**：题目卡 / 评分 / 匹配度 / 简历高亮 / 确定性 Picker 等，由播报指令驱动挂载
- **实时打断**：用户开口即打断当前播报并转向新问题

### 行动层 · 能动手调工具

- **Function Calling**：12 个工具（出题 / 简历解析 / 知识检索 / 代码判题 / 报告生成 / 情绪与动作 …）
- **MCP 工具接入**：自实现 stdio JSON-RPC 客户端，`mcp_*` 前缀转发，见[《MCP 接入方案》](docs/MCP接入方案.md)
- **知识驱动出题**：Markdown 题库 + ChromaDB 向量检索，按知识点自主生成题目与参考答案
- **简历 + 人岗匹配**：PDF / Word 解析，基于简历针对性追问并给出匹配度评估
- **在线编程 + 自动判题**：[Judge0 CE](https://ce.judge0.com) 公共 API，多语言在线运行
- **多维度报告**：雷达图评分（技术深度 / 表达力 / 逻辑性 / 人岗匹配）+ 逐题点评 + PDF 导出

### 场景与形态

- **两种使用方式**：个人练习（默认）与企业候选人初筛（HR 发邀请链接，候选人免注册作答），二者数据隔离
- **四端统一**：Web / iOS / Android（Capacitor）/ 微信小程序

***

<a id="architecture"></a>

## 🏗️ 系统架构

```mermaid
flowchart LR
    client["浏览器 / 移动端 / 小程序"] -->|HTTPS| web["Nginx / Vite"]
    web -->|/api、/v1| api["FastAPI 后端"]
    client <-->|WebGL2 渲染| avatar["魔珐星云 @xmov/avatar"]
    avatar -.->|brain_config 回调| api
    api --> db[("PostgreSQL / SQLite")]
    api --> vec[("ChromaDB 向量库")]
    api --> llm["LLM（OpenAI 兼容）"]
    api --> emb["Embedding（bge-m3）"]
    api --> judge["Judge0 CE 判题"]
    avatar -->|TTSA 播报| cloud["魔珐云端"]
```

面试编排由显式状态机驱动，阶段变化同时**落库**（`interview.stage`）并广播 **SSE** **`stage`** **事件**，前端步骤条与后端状态始终一致：

```mermaid
stateDiagram-v2
    [*] --> opening
    opening --> ask
    ask --> followup
    followup --> ask
    ask --> algorithm
    algorithm --> judge
    judge --> ask
    ask --> closing
    closing --> report
    report --> finished
    finished --> [*]
```

> SSE 事件总线（`/api/interview/{id}/events`）另有 `tool_start` / `tool_result` / `widget` / `emotion` / `metrics` 等事件，用于驱动前端工具栏与实时指标。

技术栈：

| 层级   | 技术                                                                                       |
| ---- | ---------------------------------------------------------------------------------------- |
| 前端   | Vue 3 + TypeScript + Vite 6 · Pinia · Vue Router 4 · TailwindCSS + HeadlessUI · vue-i18n |
| 具身交互 | `@xmov/avatar`（Agent 模式）· vue3-lottie（降级）                                                |
| 后端   | FastAPI + Uvicorn · SQLModel (SQLAlchemy) · pydantic-settings                            |
| 数据   | PostgreSQL 16 / SQLite（默认）· ChromaDB                                                     |
| 模型   | LLM（Deepseek / 任意 OpenAI 兼容）· Embedding（硅基流动 `BAAI/bge-m3`）                              |
| 判题   | Judge0 CE 公共 API（可自托管）                                                                   |
| 部署   | Docker Compose · Capacitor 7（iOS/Android）                                                |

***

<a id="quickstart"></a>

## 🚀 快速开始

### 前置要求

| 方式            | 需要                             |
| ------------- | ------------------------------ |
| Docker 一键（推荐） | Docker 24+ / Docker Compose v2 |
| 本地源码开发        | Node.js ≥ 20 · Python ≥ 3.12   |

### Docker 一键启动（约 5 分钟）

```bash
# 1) 准备凭证模板（留空也能启动，仅 AI 能力不可用）
cp .env.example .env          # Windows: copy .env.example .env
#    填入 LLM_API_KEY / EMBEDDING_API_KEY

# 2) 构建并启动（PostgreSQL + 后端 + 前端 Nginx）
docker compose up -d --build
```

启动后访问 **<http://localhost:8080>**（端口由 `APP_PORT` 控制）。

> 具身智能体（魔珐星云）凭证**不在** **`.env`** **里配**，启动后到「管理后台 → 具身交互智能体」维护，存入数据库即时生效；未配置可用智能体时前端自动降级为 Lottie 形象 + 浏览器语音。

### 本地源码开发

```bash
# 后端
cd server
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # 编辑并填入 API Key
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# 前端（另开终端，回到仓库根目录）
npm install
npm run dev                     # http://localhost:5173，/api 自动代理到 :8000
```

***

## 🐳 Docker 三种运行方式

按「是否需要凭证 / 是否需要下载模型」选择，**推荐云端凭证（能力最全）**：

| 方式             | 需要什么                   | 出题与点评                   | 具身播报                  | 首次启动         |
| -------------- | ---------------------- | ----------------------- | --------------------- | ------------ |
| **一、云端凭证（推荐）** | LLM / Embedding / 魔珐凭证 | 云端大模型（质量最好）             | ✅ 口型 / 表情 / 关键动作      | 构建镜像         |
| 二、本地大模型        | 无需任何凭证                 | 本地 Ollama（`qwen2.5:3b`） | ⚠️ 降级为 Lottie + 浏览器语音 | 下载约 2.5GB 模型 |
| 三、离线规则（兜底）     | 无需凭证、无需下载              | 内置题库 + 规则模板（**非大模型**）   | ⚠️ 同上                 | 秒级           |

### 方式一：云端凭证（功能最全）

```bash
cp .env.example .env            # 填入 LLM_API_KEY / EMBEDDING_API_KEY
docker compose up -d --build
```

**凭证从哪来**

- 具身智能体（魔珐星云）：[官网注册](https://www.xingyun3d.com) → 「管理后台 → 具身交互智能体」新增并设为默认
- LLM：任选 OpenAI 兼容服务（DeepSeek / 阿里百炼 / 火山方舟 …）
- Embedding：硅基流动 `BAAI/bge-m3`（有免费额度）

### 方式二：本地大模型（无凭证，AI 链路完整）

```bash
docker compose -f docker-compose.yml -f docker-compose.local-llm.yml up -d --build
```

额外启动 [Ollama](https://ollama.com) 并拉取两个模型（就绪后后端才启动）：

| 用途               | 模型                                                |
| ---------------- | ------------------------------------------------- |
| 面试官大脑（LLM）       | `qwen2.5:3b`（可用 `LOCAL_LLM_MODEL=qwen2.5:7b` 换更大） |
| 题库向量化（Embedding） | `bge-m3`（1024 维，与云端一致）                            |

### 方式三：离线规则（零依赖兜底）

```bash
OFFLINE_MODE=true docker compose up -d --build
# Windows PowerShell: $env:OFFLINE_MODE="true"; docker compose up -d --build
```

不调用任何模型：出题来自内置题库、点评由可解释规则计算、检索退化为关键词匹配；判题仍走真实 Judge0 CE。适合无网络 / 无凭证环境快速验证端到端流程，**不等同于大模型能力**。

### 开发模式（源码挂载 + 热更新）

```bash
cp server/.env.example server/.env    # 按需填写，可留空
docker compose -f docker-compose.dev.yml up -d
```

前端 `http://localhost:5173`，后端 `http://localhost:8000`（`--reload`）。

### 常用命令

```bash
docker compose logs -f backend        # 查看日志
docker compose ps                     # 查看状态
docker compose down                   # 停止（保留数据）
docker compose down -v                # 停止并删除数据卷
```

> 首次构建需联网拉取依赖：pip 走 `PIP_INDEX_URL`（默认阿里云镜像），npm 需能访问 `npmjs.org` 与 `npm.xmov.ai`（`@xmov/avatar` 所在源）。生产部署见[《部署手册》](docs/部署手册.md)（含 `docker-compose.prod.yml`、一键 `deploy.sh` 与迭代升级说明）。

***

## ⚙️ 配置说明

> 本地源码启动 / Docker 开发模式读取 `server/.env`（模板 `server/.env.example`）；
> Docker 一键启动读取根目录 `.env`（模板 `.env.example`）。两处变量名一致。

### 后端环境变量（`server/.env`）

| 变量                                                              | 说明                                 | 默认值                                                          |
| --------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------ |
| `DATABASE_URL`                                                  | 数据库连接串                             | `sqlite:///data/app.db`                                      |
| `LLM_BASE_URL`                                                  | LLM API 地址                         | `https://api.deepseek.com`                                   |
| `LLM_API_KEY`                                                   | LLM API Key                        | —                                                            |
| `LLM_MODEL`                                                     | LLM 模型名称                           | `deepseek-chat`                                              |
| `EMBEDDING_API_KEY`                                             | Embedding API Key                  | —                                                            |
| `EMBEDDING_BASE_URL`                                            | Embedding API 地址                   | `https://api.siliconflow.cn/v1`                              |
| `EMBEDDING_MODEL`                                               | Embedding 模型                       | `BAAI/bge-m3`                                                |
| `EMBEDDING_PROVIDER`                                            | Embedding 提供方（`openai` / `ollama`） | `openai`                                                     |
| `AVATAR_PROXY_BASE_URL`                                         | brain 代理地址（魔珐云端回调，**需公网可达**）       | —                                                            |
| `ASR_ACCESS_TOKEN` / `ASR_APP_ID`                               | 语音识别凭证（由后端下发给 SDK，**不入源码**）        | —                                                            |
| `ASR_PROVIDER` / `ASR_BASE_URL` / `ASR_RESOURCE_ID`             | 语音识别服务参数（一般无需改）                    | `doubao` / 火山 `bigmodel_async` / `volc.bigasr.sauc.duration` |
| `OFFLINE_MODE`                                                  | 离线规则模式开关                           | `false`                                                      |
| `INTERVIEW_SSML_INJECT`                                         | 播报是否允许注入 SSML 动作/控件标签（待验证项）        | `false`                                                      |
| `ADMIN_PASSWORD`                                                | 管理后台口令                             | `admin123`                                                   |
| `ENCRYPTION_KEY`                                                | 敏感配置加密密钥（32 字节，**生产务必替换**）         | `change-me-in-production-32bytes!!`                          |
| `S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` / `S3_BUCKET` | S3 兼容对象存储（可选，不设则本地存储）              | — / `ai-interviewer`                                         |

> 具身智能体服务凭证（App ID / App Secret / Gateway）自 v3.5 起**已下沉数据库**，不再通过环境变量下发，请在管理后台维护。

### 前端构建模式

| 命令                          | 模式     | 环境文件               | 说明             |
| --------------------------- | ------ | ------------------ | -------------- |
| `npm run build:web`         | Web    | `.env.web`         | 普通网页部署         |
| `npm run build:capacitor`   | 移动 App | `.env.capacitor`   | iOS/Android 打包 |
| `npm run build:miniprogram` | 小程序    | `.env.miniprogram` | 微信小程序嵌入        |

***

## 📁 项目结构

```
embodied-interviewer/
├── src/                         # 前端源码（Vue 3 + TypeScript）
│   ├── api/                     # 接口封装（axios）
│   ├── components/              # 组件（admin / common / interview / knowledge）
│   ├── composables/             # 组合式函数（useAvatar / useASR / useInterviewEvents …）
│   ├── providers/               # 具身 / ASR / TTS 多实现（云端 ↔ 本地降级）
│   ├── stores/                  # Pinia 状态
│   ├── views/                   # 页面（面试 / 报告 / 企业控制台 / 管理后台 …）
│   └── i18n/                    # 中英文案
├── server/                      # 后端源码（FastAPI）
│   ├── routers/                 # 路由层（interview / report / org / jd / avatar / admin …）
│   ├── services/                # 业务层（状态机 / RAG / 工具调用 / MCP / 判题 / 报告 …）
│   ├── parsers/                 # 简历解析（PDF / DOCX / Markdown）
│   ├── mcp_servers/             # 内置示例 MCP Server
│   ├── tests/                   # pytest 用例
│   ├── config.py                # 配置（pydantic-settings）
│   └── main.py                  # 应用入口
├── miniprogram/                 # 微信小程序壳工程
├── deploy/                      # Nginx 配置与部署脚本
├── docs/                        # 项目文档
├── dist/                        # 前端构建产物（部署用，构建生成）
├── Dockerfile                   # 后端镜像
├── Dockerfile.frontend          # 前端镜像（Vite 构建 + Nginx）
├── docker-compose.yml           # 一键编排（PostgreSQL + 后端 + 前端）
├── docker-compose.local-llm.yml # 叠加：本地 Ollama 模型
├── docker-compose.prod.yml      # 生产编排
├── docker-compose.dev.yml       # 开发编排（源码挂载 + 热更新）
├── .github/workflows/ci.yml     # CI：eslint + vue-tsc + build + ruff
└── LICENSE                      # MIT
```

***

## 🧪 开发与自测

```bash
npm run lint          # ESLint（TS + Vue，--max-warnings 0）
npm run typecheck     # vue-tsc 类型检查
npm run build:web     # 生产构建（Web 模式）
ruff check server     # 后端静态检查
```

以上四项即 CI（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)）内容。后端另有 pytest 用例（`server/tests/`）与冒烟脚本（`scripts/smoke_org_flow.py`），尚未接入 CI。

### 数据库

不配置 `DATABASE_URL` 时默认使用 **SQLite**（零安装）。切换到 PostgreSQL：

```bash
# Windows 可选脚本（自动下载并静默安装 PostgreSQL 16，需管理员权限）
install_postgresql.bat
# 然后在 server/.env 设置：
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_interviewer
```

已有数据迁移到 PostgreSQL：

```bash
python server/scripts/migrate_to_pg.py
```

> 仓库**不含** PostgreSQL 安装包（`pg/`、`pg.zip` 均被忽略）；容器部署时 PostgreSQL 由 `docker-compose.yml` 自动拉起。

***

## 📱 跨端（Web / App / 小程序）

同一套前端通过 Capacitor 打包 iOS / Android，通过 `<web-view>` + JSSI 桥接嵌入微信小程序。完整步骤（`npx cap add/sync`、小程序 `webViewUrl` 配置、JSBridge 通信表）见[《移动端集成指南》](docs/移动端集成指南.md)。

***

## 🏢 企业候选人初筛

HR 在「企业控制台」创建邀请链接（岗位 / 难度 / 时长 / 可选 JD / 考察重点），候选人打开 `/invite/{token}` 填姓名即可作答（**无需注册**）；HR 按报告总分横向排名。控制台同时维护组织共享资源：**组织 JD 库**（`scope=org`）与**企业知识库**（进入本组织面试的 RAG 检索，不跨用户串检）。权限矩阵与实现细节见[《项目说明》](docs/项目说明.md)。

***

<a id="limits"></a>

## ⚠️ 能力边界

- 具身播报依赖公网可达的 `AVATAR_PROXY_BASE_URL`（魔珐云端回调地址），本地 `localhost` 无法验证完整语音链路
- 离线规则模式不是大模型，出题与点评由内置题库 + 规则模板生成
- 表情与富交互 Widget 的真机联动验证、错误码分级文案与断线重连提示仍在完善，完整待办见[《项目说明》](docs/项目说明.md) §7.3

***

## 📖 文档

| 文档                                                                            | 内容                    |
| ----------------------------------------------------------------------------- | --------------------- |
| [项目说明.md](docs/项目说明.md)                                                       | 技术架构、创新点、能力现状与边界（对外版） |
| [部署手册.md](docs/部署手册.md) / [部署文档.md](docs/部署文档.md) / [DOCKER.md](DOCKER.md)    | 生产部署、迭代升级、故障排查        |
| [需求文档.md](docs/需求文档.md) / [技术方案.md](docs/技术方案.md)                             | 需求与总体设计               |
| [三期技术方案-跨端移动与小程序.md](docs/三期技术方案-跨端移动与小程序.md) / [移动端集成指南.md](docs/移动端集成指南.md) | 跨端方案                  |
| [MCP接入方案.md](docs/MCP接入方案.md)                                                 | MCP 工具接入设计            |
| [自动化测试方案.md](docs/自动化测试方案.md)                                                 | 测试策略                  |
| [CHANGELOG.md](CHANGELOG.md)                                                  | 变更日志                  |

***

## 📄 License

本项目基于 [MIT License](LICENSE) 开源，Copyright (c) 2026 MarphyDemon。
