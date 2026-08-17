#!/bin/bash
# ============================================
# AI 面试官 - 一键部署脚本
# 支持: Ubuntu/Debian/CentOS/Alibaba Cloud Linux
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}=== AI 面试官 一键部署脚本 ===${NC}\n"

# 检测包管理器
detect_pkg_manager() {
    if check_command apt-get; then
        echo "apt"
    elif check_command dnf; then
        echo "dnf"
    elif check_command yum; then
        echo "yum"
    else
        echo "unknown"
    fi
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

PKG_MGR=$(detect_pkg_manager)
echo -e "${BLUE}检测到包管理器: ${PKG_MGR}${NC}"

# 1. 检查并安装系统依赖
echo -e "\n${YELLOW}[1/6] 检查系统依赖...${NC}"

install_docker() {
    if check_command docker && docker compose version >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Docker 已安装${NC}"
        docker compose version
    else
        echo -e "${YELLOW}安装 Docker...${NC}"
        if [ "$PKG_MGR" = "apt" ]; then
            curl -fsSL https://get.docker.com | sh
        elif [ "$PKG_MGR" = "dnf" ] || [ "$PKG_MGR" = "yum" ]; then
            curl -fsSL https://get.docker.com | sh
        else
            echo -e "${RED}无法自动安装 Docker，请手动安装后重试${NC}"
            exit 1
        fi
        if check_command usermod; then
            sudo usermod -aG docker $USER
        fi
        echo -e "${GREEN}✓ Docker 安装完成，请重新登录或执行 newgrp docker 后重跑脚本${NC}"
        exit 1
    fi
}

install_node() {
    if check_command node && check_command npm; then
        echo -e "${GREEN}✓ Node.js $(node -v) 已安装${NC}"
    else
        echo -e "${YELLOW}安装 Node.js 20...${NC}"
        if [ "$PKG_MGR" = "apt" ]; then
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt-get install -y nodejs
        elif [ "$PKG_MGR" = "dnf" ]; then
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo dnf install -y nodejs
        elif [ "$PKG_MGR" = "yum" ]; then
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo yum install -y nodejs
        else
            echo -e "${YELLOW}尝试使用 nvm 安装 Node.js...${NC}"
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
            export NVM_DIR="$HOME/.nvm"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            nvm install 20
        fi
        echo -e "${GREEN}✓ Node.js 安装完成: $(node -v)${NC}"
    fi
}

# 检查 openssl（用于生成密码）
check_openssl() {
    if ! check_command openssl; then
        echo -e "${YELLOW}安装 openssl...${NC}"
        if [ "$PKG_MGR" = "apt" ]; then
            sudo apt-get install -y openssl
        elif [ "$PKG_MGR" = "dnf" ]; then
            sudo dnf install -y openssl
        elif [ "$PKG_MGR" = "yum" ]; then
            sudo yum install -y openssl
        fi
    fi
}

install_docker
install_node
check_openssl

# 2. 检查环境配置
echo -e "\n${YELLOW}[2/6] 检查环境配置...${NC}"

if [ ! -f "server/.env" ]; then
    echo -e "${YELLOW}⚠ server/.env 不存在，将从模板创建...${NC}"
    cp server/.env.example server/.env
    echo -e "${RED}请编辑 server/.env 填入真实的 API Key 和密码后重新运行！${NC}"
    echo -e "${YELLOW}编辑命令: nano server/.env${NC}"
    exit 1
fi

# 检查必填配置
REQUIRED_VARS=("LLM_API_KEY" "EMBEDDING_API_KEY")
MISSING_VARS=""
for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=[^<]*$" server/.env; then
        MISSING_VARS="${MISSING_VARS} ${var}"
    fi
done

if [ -n "$MISSING_VARS" ]; then
    echo -e "${RED}⚠ server/.env 中缺少或未填写:${MISSING_VARS}${NC}"
    echo -e "${YELLOW}请补充配置后重新运行！${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 环境配置检查通过${NC}"

# 3. 构建前端（如果已有 dist/ 则跳过）
echo -e "\n${YELLOW}[3/6] 检查前端产物...${NC}"

if [ -f "dist/index.html" ] && [ -d "dist/assets" ]; then
    echo -e "${GREEN}✓ 检测到预构建的 dist/ 目录，跳过前端构建${NC}"
else
    echo "在服务器上构建前端..."
    if [ ! -d "node_modules" ]; then
        echo "安装前端依赖..."
        npm install
    fi
    echo "构建前端（Web 模式）..."
    npm run build:web
    echo -e "${GREEN}✓ 前端构建完成，产物在 dist/ 目录${NC}"
fi

# 4. 创建必要目录
echo -e "\n${YELLOW}[4/6] 创建必要目录...${NC}"
mkdir -p data/knowledge data/resumes data/recordings
chmod -R 755 data/
echo -e "${GREEN}✓ 数据目录就绪${NC}"

# 5. 生成生产环境 .env 变量
echo -e "\n${YELLOW}[5/6] 准备生产环境变量...${NC}"

# 生成安全的 PostgreSQL 密码（如果未设置）
if ! grep -q "^POSTGRES_PASSWORD=" .env 2>/dev/null; then
    POSTGRES_PASSWORD=$(openssl rand -base64 12 | tr -d '/+=' | head -c 24)
    echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" > .env
    echo -e "${GREEN}✓ 已生成 PostgreSQL 密码${NC}"
fi

# 生成 Encryption Key（如果未设置且还是默认值）
if grep -q "^ENCRYPTION_KEY=change-me-in-production-32bytes!!$" server/.env; then
    ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    # 使用 sed 替换
    if check_command sed; then
        sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${ENCRYPTION_KEY}|" server/.env
    fi
    echo -e "${GREEN}✓ 已生成加密密钥${NC}"
fi

# 6. 启动服务
APP_PORT="${APP_PORT:-8080}"
echo -e "\n${YELLOW}[6/6] 启动 Docker Compose 服务（端口: $APP_PORT）...${NC}"

echo "停止旧服务（如果存在）..."
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

echo "构建并启动服务..."
APP_PORT=$APP_PORT docker compose -f docker-compose.prod.yml up -d --build

# 等待服务就绪
echo -e "\n${YELLOW}等待服务就绪...${NC}"
sleep 5

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo -e "\n${GREEN}============================================${NC}"
echo -e "${GREEN}🚀 AI 面试官部署完成！${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e ""
echo -e "访问地址:"
echo -e "  本机访问:  http://localhost:$APP_PORT"
echo -e "  外部访问:  http://$SERVER_IP:$APP_PORT"
echo -e "  API 文档:  http://localhost:$APP_PORT/docs"
echo -e "  健康检查:  http://localhost:$APP_PORT/api/health"
echo -e ""
echo -e "常用命令:"
echo -e "  查看状态:  docker compose -f docker-compose.prod.yml ps"
echo -e "  查看日志:  docker compose -f docker-compose.prod.yml logs -f"
echo -e "  停止服务:  docker compose -f docker-compose.prod.yml down"
echo -e "  重启服务:  docker compose -f docker-compose.prod.yml restart"
echo -e ""
echo -e "${YELLOW}⚠ 如需修改端口，执行: APP_PORT=9090 ./deploy.sh${NC}"
echo -e "${YELLOW}⚠ 请确保防火墙开放端口 $APP_PORT${NC}"
