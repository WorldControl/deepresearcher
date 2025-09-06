#!/bin/bash

# Deep Researcher 简化启动脚本
# 用法: ./start.sh [dev|prod]

set -e

# 默认启动模式
MODE=${1:-prod}

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker和Docker Compose
check_requirements() {
    log_info "检查环境要求..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装或不在PATH中"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose未安装或不在PATH中"
        exit 1
    fi
    
    log_success "环境检查通过"
}

# 检查环境变量文件
check_env_file() {
    log_info "检查环境配置..."
    
    if [ ! -f ".env" ]; then
        log_warning "未找到.env文件，从示例文件创建..."
        if [ -f "deploy/configs/env.example" ]; then
            cp deploy/configs/env.example .env
            log_warning "请编辑.env文件并配置必要的环境变量！"
        else
            log_error "未找到deploy/configs/env.example文件"
            exit 1
        fi
    fi
    
    # 检查关键环境变量
    if ! grep -q "OPENAI_API_KEY=" .env || grep -q "OPENAI_API_KEY=your_openai_api_key_here" .env; then
        log_warning "请在.env文件中配置OPENAI_API_KEY"
    fi
    
    log_success "环境配置检查完成"
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."
    
    mkdir -p research_result/cache
    mkdir -p research_result/reports
    
    log_success "目录创建完成"
}

# 启动服务
start_services() {
    log_info "启动模式: $MODE"
    
    case $MODE in
        "dev")
            log_info "启动开发模式..."
            docker-compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.dev.yml up -d
            ;;
        "prod")
            log_info "启动生产模式..."
            docker-compose -f deploy/docker/docker-compose.yml up -d
            ;;
        *)
            log_error "无效的启动模式: $MODE"
            log_info "支持的模式: dev, prod"
            exit 1
            ;;
    esac
}

# 等待服务启动
wait_for_services() {
    log_info "等待服务启动..."
    
    # 等待API服务
    log_info "等待API服务启动..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            log_success "API服务已启动"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "API服务启动超时"
            exit 1
        fi
        sleep 2
    done
    
    # 等待前端服务
    log_info "等待前端服务启动..."
    for i in {1..30}; do
        if curl -s http://localhost:8501 > /dev/null 2>&1; then
            log_success "前端服务已启动"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "前端服务启动超时"
            exit 1
        fi
        sleep 2
    done
}

# 显示服务状态
show_status() {
    log_info "服务状态:"
    docker-compose -f deploy/docker/docker-compose.yml ps
    
    echo ""
    log_success "服务启动完成！"
    echo ""
    echo "访问地址:"
    echo "  前端界面: http://localhost:8501"
    echo "  API文档:  http://localhost:8000/docs"
    echo "  健康检查: http://localhost:8000/health"
    
    echo ""
    echo "管理命令:"
    echo "  查看日志: docker-compose -f deploy/docker/docker-compose.yml logs -f"
    echo "  停止服务: docker-compose -f deploy/docker/docker-compose.yml down"
    echo "  重启服务: docker-compose -f deploy/docker/docker-compose.yml restart"
}

# 主函数
main() {
    echo "========================================="
    echo "  Deep Researcher 简化部署工具"
    echo "========================================="
    echo ""
    
    check_requirements
    check_env_file
    create_directories
    start_services
    wait_for_services
    show_status
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
