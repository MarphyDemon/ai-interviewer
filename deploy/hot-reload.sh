#!/usr/bin/env bash
set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-$(pwd)}"
ARCHIVE="${1:-}"
SKIP_BACKUP="${SKIP_BACKUP:-0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════╗"
    echo "║   AI Interviewer — 后端热更新脚本             ║"
    echo "║   $(date '+%Y-%m-%d %H:%M:%S')                           ║"
    echo "╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info()  { echo -e "  ${GREEN}→${NC} $1"; }
log_ok()    { echo -e "  ${GREEN}✔${NC} $1"; }
log_warn()  { echo -e "  ${YELLOW}⚠${NC} $1"; }
log_err()   { echo -e "  ${RED}✘${NC} $1"; }

main() {
    banner
    cd "$DEPLOY_DIR"

    # 1. 解压新包（覆盖 server/ 代码，保留 .env）
    if [[ -n "$ARCHIVE" && -f "$ARCHIVE" ]]; then
        log_info "解压部署包: $ARCHIVE"
        tar -xzf "$ARCHIVE"
        log_ok "解压完成"
    else
        log_warn "未指定部署包或文件不存在，跳过解压"
        log_info "用法: $0 <archive.tar.gz>"
    fi

    # 2. 重建后端镜像
    echo ""
    log_info "重建后端镜像 (--no-cache)..."
    docker compose -f docker-compose.prod.yml build --no-cache backend
    log_ok "镜像构建完成"

    # 3. 重启后端
    echo ""
    log_info "重启后端服务..."
    docker compose -f docker-compose.prod.yml up -d backend
    log_ok "后端服务已重启"

    # 4. 等待健康检查
    echo ""
    log_info "等待后端就绪..."
    local waited=0 max_wait=20
    while [[ $waited -lt $max_wait ]]; do
        sleep 2; waited=$((waited + 2))
        local running
        running=$(docker compose -f docker-compose.prod.yml ps -q backend 2>/dev/null | xargs -r docker inspect --format='{{.State.Running}}' 2>/dev/null || echo "false")
        if [[ "$running" == "true" ]]; then
            log_ok "后端容器运行中 (${waited}s)"
            break
        fi
        log_info "等待中... (${waited}s)"
    done

    # 5. 显示状态
    echo ""
    log_info "服务状态:"
    docker compose -f docker-compose.prod.yml ps

    echo ""
    log_ok "后端热更新完成！"
}

main "$@"