# AGENTS.md — 具身面试官 / Embodied Interviewer

本文件给在本仓库工作的 AI 助手与贡献者提供最小必要指引。

## 项目速览

- 前端：Vue 3 + TypeScript + Vite（`src/`）
- 后端：FastAPI + SQLModel（`server/`，分层为 `routers/` → `services/` → `models/`）
- 具身交互：魔珐星云 `@xmov/avatar`（Agent 模式，WebGL2 端侧渲染）
- 部署：Docker Compose（`docker-compose.yml` 一键启动，含云端凭证 / 本地模型 / 离线规则三种模式；`docker-compose.prod.yml` 为生产编排）

## 先读哪些文档

| 文档 | 内容 |
|---|---|
| [README.md](README.md) | 快速开始、配置项、Docker 三种运行方式 |
| [docs/项目说明.md](docs/项目说明.md) | 技术架构、创新点、能力现状与边界（对外版） |
| [docs/部署手册.md](docs/部署手册.md) | 生产部署、迭代升级、故障排查 |
| [docs/赛题二-场景创意论证.md](docs/赛题二-场景创意论证.md) | 场景价值与不可替代性论证 |
| [docs/赛题二-具身面试官-升级实施计划.md](docs/赛题二-具身面试官-升级实施计划.md) | 实施状态总览、里程碑与待验证清单 |

## 提交前自查

- 提交信息遵循 Conventional Commits。
- 本地跑通 CI 的检查项（见 [.github/workflows/ci.yml](.github/workflows/ci.yml)）：
  `npm run lint`、`npm run typecheck`、`npm run build:web`、`ruff check server`。
- 真实凭证不入库：仅提交 `*.env.example` 模板；具身交互智能体凭证在管理后台入库（加密），ASR 凭证由后端随 `/api/avatar/config` 下发。

## 关于本地 AI 工具链

开发机上的 `.trellis/`、`.trae/`、`.opencode/` 属于**本机 AI 工具链配置与工作记录，已从仓库移除**（见 `.gitignore`）。
在新克隆的仓库中这些目录并不存在，请勿依赖其中的指令、技能或路径引用。
