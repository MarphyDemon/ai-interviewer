# Docker 开发环境使用指南

## 前置条件

1. 安装 Docker Desktop：<https://www.docker.com/products/docker-desktop/>
2. 启动 Docker Desktop（任务栏图标不闪烁即为启动完成）

## 一键启动（评审 / 演示推荐）

构建前端镜像 + 后端镜像 + PostgreSQL，无需预先构建 `dist/`，也不需要 `server/.env`。三种方式按"是否需要凭证 / 是否需要下载模型"选择：

### 方式一：云端凭证（功能最全，含具身播报）

```bash
# 可选：配置凭证（留空也能启动，只是 AI 能力不可用）
cp .env.example .env

docker compose up -d --build
```

### 方式二：本地大模型（无凭证，AI 链路完整）

```bash
docker compose -f docker-compose.yml -f docker-compose.local-llm.yml up -d --build
```

额外启动 Ollama 并拉取 `qwen2.5:3b`（大脑）与 `bge-m3`（向量化），首次约 2.5GB；后端会等模型就绪后再启动。下载慢时改用方式三。

### 方式三：离线规则模式（零依赖，秒级启动）

```bash
# Linux / macOS
OFFLINE_MODE=true docker compose up -d --build
# Windows PowerShell
$env:OFFLINE_MODE="true"; docker compose up -d --build
```

不调用任何模型：出题来自内置题库，点评由规则计算（非大模型），知识库检索退化为关键词匹配；判题仍走真实 Judge0 CE。页面顶部会显示运行模式提示条。

访问 `http://localhost:8080`（端口由 `APP_PORT` 控制）。

## 开发模式（源码挂载 + 热更新）

```bash
cp server/.env.example server/.env   # 按需填写

docker compose -f docker-compose.dev.yml up -d
```

访问 `http://localhost:5173`（Vite）与 `http://localhost:8000`（API）。

## 查看日志

```bash
# 查看所有服务日志
docker compose logs -f

# 查看单个服务日志
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

## 停止服务

```bash
# 停止所有服务（保留数据卷）
docker compose down

# 停止所有服务并删除数据卷（清空数据库）
docker compose down -v
```

## 重启服务

```bash
# 重启单个服务
docker compose restart backend
docker compose restart frontend

# 重启所有服务
docker compose restart
```

## 重新构建（修改依赖后）

```bash
# 重新构建镜像
docker compose build

# 重新构建并启动
docker compose up -d --build
```

## 使用国内镜像加速

```bash
# 在根目录 .env 中设置后重新构建（compose 会自动读取）
#   PIP_INDEX_URL=https://pypi.mirrors.ustc.edu.cn/simple
#   PIP_TRUSTED_HOST=pypi.mirrors.ustc.edu.cn
docker compose up -d --build
```

## 进入容器内部

```bash
# 进入后端容器
docker exec -it ai-interviewer-backend /bin/bash

# 进入 PostgreSQL 并执行 SQL
docker exec -it ai-interviewer-postgres psql -U postgres -d ai_interviewer
```

## 查看容器状态

```bash
# 查看运行中的容器
docker compose ps

# 查看容器资源占用
docker stats
```

## 清理（删除所有容器、网络、镜像）

```bash
# 停止并删除所有容器
docker compose down -v

# 删除构建的镜像
docker rmi ai-interviewer-backend
```

