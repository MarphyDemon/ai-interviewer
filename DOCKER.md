# Docker 开发环境使用指南

## 前置条件

1. 安装 Docker Desktop：https://www.docker.com/products/docker-desktop/
2. 启动 Docker Desktop（任务栏图标不闪烁即为启动完成）

## 首次启动（构建镜像 + 启动所有服务）

```bash
docker-compose up -d
```

## 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看单个服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

## 停止服务

```bash
# 停止所有服务（保留数据卷）
docker-compose down

# 停止所有服务并删除数据卷（清空数据库）
docker-compose down -v
```

## 重启服务

```bash
# 重启单个服务
docker-compose restart backend
docker-compose restart frontend

# 重启所有服务
docker-compose restart
```

## 重新构建（修改依赖后）

```bash
# 重新构建镜像
docker-compose build

# 重新构建并启动
docker-compose up -d --build
```

## 使用国内镜像加速

```bash
# 构建时指定 pip 国内镜像
docker-compose build --build-arg PIP_INDEX_URL=https://pypi.mirrors.ustc.edu.cn/simple

# 或启动时自动构建并使用镜像
docker-compose up -d --build --build-arg PIP_INDEX_URL=https://pypi.mirrors.ustc.edu.cn/simple
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
docker-compose ps

# 查看容器资源占用
docker stats
```

## 清理（删除所有容器、网络、镜像）

```bash
# 停止并删除所有容器
docker-compose down -v

# 删除构建的镜像
docker rmi ai-interviewer-backend
```