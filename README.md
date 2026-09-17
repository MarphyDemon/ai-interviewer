# 🤖 AI 面试官

> 一款基于具身交互智能体的 AI 模拟面试平台。用户上传简历、选择岗位方向，由具身交互智能体面试官按题库知识点和简历内容进行语音/文字问答，结束后输出多维度点评报告。

---

## ✨ 核心特性

- 🎭 **具身交互智能体面试官** — 3D 具身交互智能体形象 + 语音交互，贴近真实面试场景（支持 WebGL 硬件加速 / Lottie 动画降级）
- 📚 **知识驱动出题** — Markdown 题库 + RAG 检索，AI 基于知识点自主生成题目与参考答案
- 📄 **简历针对性** — PDF/Word 简历解析，AI 基于简历内容进行针对性追问和人岗匹配评估
- 💬 **语音优先交互** — 麦克风录音 → ASR 转文字 → AI 追问 → TTS 语音播报，支持文字输入兜底
- 📊 **多维度评估** — 雷达图评分（技术深度、表达力、逻辑性、人岗匹配）+ 逐题点评 + PDF 报告导出
- 💻 **代码练习** — 内置算法练习模块，支持在线编码与自动判题（Piston API）
- 📱 **跨端支持** — Web / iOS / Android（Capacitor）/ 微信小程序 四端统一

---

## 🏗️ 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | Vue 3 + TypeScript + Vite 6 |
| 状态管理 | Pinia |
| UI 样式 | TailwindCSS + HeadlessUI |
| 路由 | Vue Router 4 |
| 国际化 | vue-i18n (中/英) |
| 代码编辑器 | Monaco Editor |
| 具身交互智能体 SDK | @xmov/avatar |
| 动画降级 | vue3-lottie |
| 后端框架 | FastAPI + Uvicorn |
| ORM | SQLModel (SQLAlchemy) |
| 数据库 | PostgreSQL 16 / SQLite (默认) |
| 向量库 | ChromaDB |
| LLM | Deepseek / 兼容 OpenAI API |
| Embedding | SiliconFlow BAAI/bge-m3 |
| 部署 | Docker Compose |
| 跨端 | Capacitor 7 (iOS/Android) |

---

## 📁 项目结构

```
ai-interviewer/
├── src/                        # 前端源码 (Vue 3 + TypeScript)
│   ├── api/                    # API 请求模块
│   ├── components/             # 公共组件
│   │   ├── common/             # 导航、TabBar 等
│   │   └── DeviceCheckModal.vue
│   ├── composables/            # 组合式函数
│   │   ├── useAvatar.ts        # 具身交互智能体面试官管理
│   │   ├── useDevice.ts        # 设备检测
│   │   ├── useMobile.ts        # 移动端工具
│   │   ├── useMediaDevices.ts  # 摄像头/麦克风
│   │   └── useMediaRecorder.ts # 录音
│   ├── i18n/                   # 国际化 (中/英)
│   ├── router/                 # 路由配置
│   ├── stores/                 # Pinia 状态
│   ├── views/                  # 页面视图
│   ├── utils/                  # 工具函数
│   ├── App.vue                 # 根组件
│   └── main.ts                 # 入口
├── server/                     # 后端源码 (FastAPI)
│   ├── routers/                # API 路由
│   │   ├── auth.py             # 认证 (登录/注册)
│   │   ├── interview.py        # 面试核心
│   │   ├── report.py           # 报告生成
│   │   ├── knowledge.py        # 题库管理
│   │   ├── resume.py           # 简历解析
│   │   ├── code.py             # 代码练习
│   │   ├── recordings.py       # 录制回放
│   │   └── ...
│   ├── services/               # 业务服务
│   │   ├── interview_service.py
│   │   ├── judge_service.py    # 代码判题
│   │   ├── pdf_service.py      # PDF 生成
│   │   └── ...
│   ├── config.py               # 配置 (基于 pydantic-settings)
│   ├── database.py             # 数据库初始化
│   └── main.py                 # FastAPI 入口
├── pg/                         # 内置 PostgreSQL 安装包 (Windows)
├── miniprogram/                # 微信小程序壳工程
├── public/                     # 静态资源
├── data/                       # 运行时数据 (上传文件、录屏等)
├── docs/                       # 项目文档
├── Dockerfile                  # 后端 Docker 镜像
├── Dockerfile.frontend         # 前端 Docker 镜像 (Vite 构建 + Nginx)
├── docker-compose.yml          # 一键启动编排 (Postgres + Backend + Frontend)
├── docker-compose.dev.yml      # 开发模式编排 (源码挂载 + 热更新)
├── capacitor.config.ts         # Capacitor 配置
├── vite.config.ts              # Vite 配置
├── package.json                # 前端依赖
├── server/requirements.txt     # 后端依赖
└── install_postgresql.bat      # Windows 一键安装 PostgreSQL
```

---

## 🚀 快速开始

### 环境要求

- **Node.js** >= 20
- **Python** >= 3.12
- **PostgreSQL** 16+（可选，默认使用 SQLite）
- **Docker** 24+（可选，容器化部署）

### 1. 克隆项目

```bash
git clone <repo-url>
cd ai-interviewer
```

### 2. 后端启动

```bash
# 进入后端目录
cd server

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt

# 创建 .env 配置文件
copy .env.example .env
# 编辑 .env，填入 API Key 等配置

# 启动服务
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

后端服务启动于 `http://localhost:8000`

### 3. 前端启动

```bash
# 回到项目根目录
cd ..

# 安装依赖
npm install

# 开发模式启动
npm run dev
```

前端服务启动于 `http://localhost:5173`，自动代理 `/api` 到后端 `localhost:8000`

### 4. 访问应用

打开浏览器访问 `http://localhost:5173`

---

## ⚙️ 配置说明

> 本地源码启动 / Docker 开发模式读取 `server/.env`（模板 `server/.env.example`）；
> Docker 一键启动读取根目录 `.env`（模板 `.env.example`）。两处变量名一致。

### 后端环境变量 (`server/.env`)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | 数据库连接串 | `sqlite:///data/app.db` |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.deepseek.com` |
| `LLM_API_KEY` | LLM API Key | — |
| `LLM_MODEL` | LLM 模型名称 | `deepseek-chat` |
| `EMBEDDING_API_KEY` | Embedding API Key | — |
| `EMBEDDING_BASE_URL` | Embedding API 地址 | `https://api.siliconflow.cn/v1` |
| `EMBEDDING_MODEL` | Embedding 模型 | `BAAI/bge-m3` |
| `AVATAR_APP_ID` | 具身交互智能体 App ID | — |
| `AVATAR_APP_SECRET` | 具身交互智能体 App Secret | — |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` |
| `S3_ENDPOINT` | S3 兼容存储地址 (可选) | — |
| `S3_ACCESS_KEY` | S3 Access Key | — |
| `S3_SECRET_KEY` | S3 Secret Key | — |
| `S3_BUCKET` | S3 Bucket | `ai-interviewer` |
| `ENCRYPTION_KEY` | 加密密钥 | `change-me-in-production-32bytes!!` |

### 前端构建模式

| 命令 | 模式 | 环境文件 | 说明 |
|------|------|----------|------|
| `npm run build:web` | Web | `.env.web` | 普通网页部署 |
| `npm run build:capacitor` | 移动 App | `.env.capacitor` | iOS/Android 打包 |
| `npm run build:miniprogram` | 小程序 | `.env.miniprogram` | 微信小程序嵌入 |

---

## 🐳 Docker 部署

提供三种运行方式，按"是否需要凭证 / 是否需要下载模型"选择：

| 方式 | 需要什么 | 出题与点评 | 具身播报 | 首次启动 |
|---|---|---|---|---|
| **一、云端凭证** | LLM / Embedding / 魔珐凭证 | 云端大模型（质量最好） | ✅ 口型 / 表情 / 关键动作 | 构建镜像 |
| **二、本地大模型** | 无需任何凭证 | 本地 Ollama（qwen2.5:3b） | ⚠️ 降级为 Lottie + 浏览器语音 | 下载约 2.5GB 模型 |
| **三、离线规则** | 无需凭证、无需下载 | 内置题库 + 规则模板（非大模型） | ⚠️ 同上 | 秒级 |

### 方式一：云端凭证（功能最全）

```bash
# 1) 配置凭证
cp .env.example .env        # Windows: copy .env.example .env
#    填入 LLM_API_KEY / EMBEDDING_API_KEY / AVATAR_APP_ID / AVATAR_APP_SECRET

# 2) 构建并启动（PostgreSQL + 后端 + 前端 Nginx）
docker compose up -d --build
```

**凭证从哪来**

- 具身交互智能体（魔珐星云）：[官网注册](https://www.xingyun3d.com)，本赛题邀请码 `XJKA436Y6J`（注册即送 1000 积分）
- LLM：任选 OpenAI 兼容服务（DeepSeek / 阿里百炼 / 火山方舟等）
- Embedding：硅基流动 `BAAI/bge-m3`（有免费额度）

### 方式二：本地大模型（无凭证，AI 链路完整）

```bash
docker compose -f docker-compose.yml -f docker-compose.local-llm.yml up -d --build
```

额外启动 [Ollama](https://ollama.com) 并拉取两个模型（模型就绪后才启动后端）：

| 用途 | 模型 |
|---|---|
| 面试官大脑（LLM） | `qwen2.5:3b`（可用 `LOCAL_LLM_MODEL=qwen2.5:7b` 换更大的） |
| 题库向量化（Embedding） | `bge-m3`（1024 维，与云端 bge-m3 一致） |

> 下载慢或不想下载模型时，请用方式三。

### 方式三：离线规则模式（零依赖，秒级启动）

```bash
OFFLINE_MODE=true docker compose up -d --build
# Windows PowerShell: $env:OFFLINE_MODE="true"; docker compose up -d --build
```

不调用任何模型，用**内置题库 + 规则模板**驱动"出题 → 追问 → 算法题 → 判题 → 报告"全流程；知识库检索退化为关键词匹配。判题仍走真实 Judge0 CE（公网 API）。

> 该模式**不是大模型**：出题来自题库，点评由"回答长度 / 技术关键词覆盖 / 表达结构"等可解释规则计算，页面顶部会显示模式提示条。适合评审在无网络、无凭证环境下快速验证端到端流程。

启动后（三种方式一致）：

- 前端: `http://localhost:8080`（端口可用 `APP_PORT` 修改）
- 后端: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- Ollama: `localhost:11434`（仅方式二）

> 方式二、三下**无需任何云端 Key**；具身播报走魔珐云端 TTSA，未配置 `AVATAR_APP_ID` / `AVATAR_APP_SECRET` 时前端自动降级为 Lottie 形象 + 浏览器语音（Web Speech）。

> 首次构建需要联网拉取依赖：pip 走 `PIP_INDEX_URL`（默认阿里云镜像），npm 需能访问 `npmjs.org` 与 `npm.xmov.ai`（`@xmov/avatar` 所在源）。

### 开发模式（源码挂载 + 热更新）

```bash
cp server/.env.example server/.env    # 按需填写，可留空
docker compose -f docker-compose.dev.yml up -d
```

前端 `http://localhost:5173`，后端 `http://localhost:8000`（`--reload`，改动即生效）。

### 常用命令

```bash
docker compose logs -f backend        # 查看日志
docker compose ps                     # 查看状态
docker compose down                   # 停止 (保留数据)
docker compose down -v                # 停止并删除数据卷
```

---

## 📱 移动端集成

### Capacitor (iOS / Android)

```bash
# 安装 Capacitor CLI
npm install @capacitor/cli --save-dev

# 初始化 (首次)
npx cap init "AI面试官" "com.aiinterviewer.app"

# 添加平台
npm install @capacitor/android @capacitor/ios
npx cap add android
npx cap add ios

# 构建前端 (capacitor 模式)
npm run build:capacitor

# 同步到原生项目
npx cap sync

# 打开 Xcode / Android Studio
npx cap open ios
npx cap open android

# 开发调试
npm run dev:capacitor   # 本地调试模式，允许 App 连接 localhost
```

### 微信小程序

```bash
# 1. 用微信开发者工具打开 miniprogram/ 目录
# 2. 修改 miniprogram/app.js 中的 webViewUrl 为已部署的 H5 地址
# 3. 在微信开发者工具中上传小程序代码
# 4. 提交审核发布
```

小程序壳使用 `<web-view>` 嵌入 H5 页面，通过 JSSI（`evalJS` / `postMessage`）实现双向通信：

| 方向 | 方式 | 场景 |
|------|------|------|
| 小程序 → H5 | `evalJS` 调用 `window.__onMiniMessage` | 实时消息（如分享回调） |
| H5 → 小程序 | `wx.miniProgram.navigateBack` 等 | 关闭页面、返回上一页 |
| H5 → 小程序 | URL hash `#/mp-action?action=xxx` | 触发小程序原生能力 |

---

## 🗄️ 数据库

### 内置 PostgreSQL (Windows)

项目已内置 PostgreSQL 16 安装包至 `pg/` 目录。

```bash
# 一键安装 (需管理员权限)
install_postgresql.bat
```

安装完成后在 `server/.env` 中设置：

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_interviewer
```

### SQLite (默认)

不配置 `DATABASE_URL` 时，默认使用 SQLite，无需额外安装。

### 数据迁移

```bash
python server/scripts/migrate_to_pg.py
```

---

## 🔧 常用命令

| 命令 | 说明 |
|------|------|
| `npm run dev` | 前端开发模式 |
| `npm run build` | 生产构建 (默认 web) |
| `npm run build:web` | Web 模式构建 |
| `npm run build:capacitor` | Capacitor 模式构建 |
| `npm run build:miniprogram` | 小程序模式构建 |
| `npm run typecheck` | TypeScript 类型检查 |
| `npm run lint` | ESLint 代码检查（TS + Vue） |
| `npm run preview` | 本地预览构建产物 |

---

## 📖 文档

- [项目说明](docs/项目说明.md) — 技术架构、创新点、能力现状与边界（对外版）
- [需求文档](docs/需求文档.md)
- [技术方案](docs/技术方案.md)
- [三期技术方案 - 跨端移动与小程序](docs/三期技术方案-跨端移动与小程序.md)
- [Docker 部署指南](DOCKER.md)
- [变更日志](CHANGELOG.md)

---

## 📄 License

本项目基于 [MIT License](LICENSE) 开源，Copyright (c) 2026 MarphyDemon。