#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-$(pwd)}"
ARCHIVE="${1:-ai-interviewer-deploy.tar.gz}"
SKIP_BACKUP="${SKIP_BACKUP:-0}"
SKIP_MIGRATE="${SKIP_MIGRATE:-1}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_step()  { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }
log_ok()    { echo -e "  ${GREEN}✔${NC} $1"; }
log_warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
log_err()   { echo -e "  ${RED}✘${NC} $1"; }
log_info()  { echo -e "  ${GREEN}→${NC} $1"; }

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════╗"
    echo "║   AI Interviewer — 一键部署脚本              ║"
    echo "║   $(date '+%Y-%m-%d %H:%M:%S')                           ║"
    echo "╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prereqs() {
    log_step "检查前置条件"

    if ! command -v docker &>/dev/null; then
        log_err "Docker 未安装"
        exit 1
    fi
    log_ok "Docker 已安装"

    if ! docker compose version &>/dev/null && ! command -v docker-compose &>/dev/null; then
        log_err "Docker Compose 未安装"
        exit 1
    fi
    log_ok "Docker Compose 已安装"

    if [[ ! -d "$DEPLOY_DIR" ]]; then
        log_err "部署目录不存在: $DEPLOY_DIR"
        exit 1
    fi
    log_ok "部署目录: $DEPLOY_DIR"

    if [[ ! -f "$DEPLOY_DIR/docker-compose.prod.yml" ]]; then
        log_err "docker-compose.prod.yml 未找到"
        exit 1
    fi

    if [[ ! -f "$DEPLOY_DIR/$ARCHIVE" ]]; then
        log_err "部署包未找到: $DEPLOY_DIR/$ARCHIVE"
        echo ""
        echo "  用法: $0 [部署包文件名]"
        echo "  示例: $0 ai-interviewer-deploy-20260819-175211.tar.gz"
        exit 1
    fi
    log_ok "部署包: $ARCHIVE"
}

do_backup() {
    if [[ "$SKIP_BACKUP" == "1" ]]; then
        log_warn "跳过备份 (SKIP_BACKUP=1)"
        return
    fi

    log_step "备份旧版本"
    local ts
    ts=$(date +%Y%m%d_%H%M%S)

    for item in dist server; do
        if [[ -d "$item" ]]; then
            cp -r "$item" "${item}.bak.${ts}"
            log_ok "已备份 ${item} → ${item}.bak.${ts}"
        fi
    done

    # 清理 7 天前的备份
    find "$DEPLOY_DIR" -maxdepth 1 -name "dist.bak.*" -mtime +7 -exec rm -rf {} + 2>/dev/null || true
    find "$DEPLOY_DIR" -maxdepth 1 -name "server.bak.*" -mtime +7 -exec rm -rf {} + 2>/dev/null || true
}

do_extract() {
    log_step "解压新版本"

    # 前端产物是带内容哈希的分块，tar 解压不会删除归档中已不存在的旧文件。
    # 不清空 dist 会导致历次构建的废弃分块不断堆积（且仍可被公开访问，
    # 里面可能残留旧文案/旧逻辑），因此解压前必须整体清空。
    if [[ -d dist ]]; then
        rm -rf dist
        log_info "已清空旧 dist"
    fi

    tar -xzf "$ARCHIVE"
    log_ok "解压完成"

    # 清理不该进入镜像的残留文件。
    # 归档里已排除这些内容，但 tar 不会删除服务器上的历史文件，它们会被
    # Dockerfile 的 COPY server/ 一并打进镜像，因此必须显式清理。
    local pyc_dirs env_baks
    pyc_dirs=$(find server -name '__pycache__' -type d 2>/dev/null | wc -l)
    if [[ "$pyc_dirs" -gt 0 ]]; then
        find server -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
        log_info "已清理 ${pyc_dirs} 个 __pycache__ 目录（其他 Python 版本的旧字节码）"
    fi

    env_baks=$(find server -maxdepth 1 -name '.env.bak.*' -type f 2>/dev/null | wc -l)
    if [[ "$env_baks" -gt 0 ]]; then
        find server -maxdepth 1 -name '.env.bak.*' -type f -delete 2>/dev/null || true
        log_info "已清理 ${env_baks} 个 .env 备份（含明文密钥，不可入镜像）"
    fi

    # 保留 .env 配置
    if [[ -f "server/.env" ]]; then
        log_info "server/.env 已保留"
    fi
}

do_build() {
    log_step "重建后端镜像 (--no-cache)"
    docker compose -f docker-compose.prod.yml build --no-cache backend
    log_ok "镜像构建完成"
}

do_restart() {
    log_step "重启服务"
    docker compose -f docker-compose.prod.yml down
    docker compose -f docker-compose.prod.yml up -d
    log_ok "服务已启动"
}

wait_and_healthcheck() {
    log_step "等待服务就绪"

    local max_wait=30
    local waited=0
    local interval=2

    while [[ $waited -lt $max_wait ]]; do
        sleep "$interval"
        waited=$((waited + interval))

        local backend_healthy
        backend_healthy=$(docker compose -f docker-compose.prod.yml ps -q backend 2>/dev/null | head -1)
        if [[ -n "$backend_healthy" ]]; then
            local status
            status=$(docker inspect --format='{{.State.Running}}' "$backend_healthy" 2>/dev/null || echo "false")
            if [[ "$status" == "true" ]]; then
                log_ok "后端容器运行中 (等待 ${waited}s)"
                return 0
            fi
        fi

        local nginx_healthy
        nginx_healthy=$(docker compose -f docker-compose.prod.yml ps -q nginx 2>/dev/null | head -1)
        if [[ -n "$nginx_healthy" ]]; then
            local nstatus
            nstatus=$(docker inspect --format='{{.State.Running}}' "$nginx_healthy" 2>/dev/null || echo "false")
            if [[ "$nstatus" == "true" ]]; then
                log_ok "Nginx 容器运行中 (等待 ${waited}s)"
            fi
        fi

        log_info "等待中... (${waited}s/${max_wait}s)"
    done

    log_warn "等待超时，请手动检查 docker compose -f docker-compose.prod.yml ps"
    return 0
}

do_migrate() {
    if [[ "$SKIP_MIGRATE" == "1" ]]; then
        log_warn "跳过数据库迁移 (SKIP_MIGRATE=1)"
        return
    fi

    log_step "执行数据库迁移"
    docker compose -f docker-compose.prod.yml exec backend \
        python -c "import sys;sys.path.insert(0,'.');from server.database import init_db;init_db()"
    log_ok "数据库迁移完成"
}

show_status() {
    log_step "服务状态"
    docker compose -f docker-compose.prod.yml ps
}

show_tail() {
    log_info "最近日志 (Ctrl+C 退出):"
    echo ""
    timeout 10 docker compose -f docker-compose.prod.yml logs --tail=20 backend 2>/dev/null || true
}

main() {
    banner

    cd "$DEPLOY_DIR"

    check_prereqs
    do_backup
    do_extract
    do_build
    do_restart
    wait_and_healthcheck
    do_migrate
    show_status
    show_tail

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   部署完成！                                   ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
}

main "$@"