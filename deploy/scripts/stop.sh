#!/bin/bash

# Deep Researcher 停止脚本

set -e

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

# 停止服务
stop_services() {
    log_info "停止Deep Researcher服务..."
    
    # 停止所有可能的服务配置
    if docker-compose -f deploy/docker/docker-compose.yml ps -q | grep -q .; then
        docker-compose -f deploy/docker/docker-compose.yml down
        log_success "生产模式服务已停止"
    fi
    
    if docker-compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.dev.yml ps -q 2>/dev/null | grep -q .; then
        docker-compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.dev.yml down
        log_success "开发模式服务已停止"
    fi
    
    # 检查是否还有相关容器在运行
    if docker ps --filter "name=deep-researcher" --format "{{.Names}}" | grep -q .; then
        log_warning "发现仍在运行的容器，正在强制停止..."
        docker stop $(docker ps --filter "name=deep-researcher" --format "{{.Names}}")
        docker rm $(docker ps -a --filter "name=deep-researcher" --format "{{.Names}}")
    fi
    
    log_success "所有服务已停止"
}

# 清理资源（可选）
cleanup_resources() {
    if [ "$1" = "--clean" ]; then
        log_info "清理Docker资源..."
        
        # 删除未使用的镜像
        docker image prune -f
        
        # 删除未使用的网络
        docker network prune -f
        
        log_success "资源清理完成"
    fi
}

# 主函数
main() {
    echo "========================================="
    echo "  Deep Researcher 停止工具"
    echo "========================================="
    echo ""
    
    stop_services
    cleanup_resources "$1"
    
    echo ""
    log_info "服务已完全停止"
    
    if [ "$1" != "--clean" ]; then
        echo ""
        echo "提示:"
        echo "  如需清理Docker资源，请使用: ./stop.sh --clean"
        echo "  重新启动服务: ./start.sh"
    fi
}

# 脚本入口
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
