# Deep Researcher 简化 Makefile
# 提供便捷的Docker操作命令

.PHONY: help build up dev down logs clean backup shell status health setup

# Docker Compose文件路径
COMPOSE_FILE = deploy/docker/docker-compose.yml
COMPOSE_DEV_FILE = deploy/docker/docker-compose.dev.yml

# 默认目标
help:
	@echo "Deep Researcher 简化操作命令:"
	@echo ""
	@echo "  build     - 构建Docker镜像"
	@echo "  up        - 启动生产环境"
	@echo "  dev       - 启动开发环境"
	@echo "  down      - 停止所有服务"
	@echo "  restart   - 重启服务"
	@echo "  logs      - 查看服务日志"
	@echo "  status    - 查看服务状态"
	@echo "  clean     - 清理容器和镜像"
	@echo "  backup    - 备份研究数据"
	@echo "  shell     - 进入容器shell"
	@echo "  health    - 检查服务健康"
	@echo "  setup     - 初始化环境配置"
	@echo "  help      - 显示此帮助信息"

# 构建镜像
build:
	@echo "构建Docker镜像..."
	docker-compose -f $(COMPOSE_FILE) build --no-cache

# 生产环境
up:
	@echo "启动生产环境..."
	docker-compose -f $(COMPOSE_FILE) up -d
	@echo "生产环境已启动!"
	@echo "前端: http://localhost:8501"
	@echo "API: http://localhost:8000"

# 开发环境
dev:
	@echo "启动开发环境..."
	docker-compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV_FILE) up -d
	@echo "开发环境已启动!"
	@echo "前端: http://localhost:8501"
	@echo "API: http://localhost:8000"

# 停止服务
down:
	@echo "停止所有服务..."
	docker-compose -f $(COMPOSE_FILE) down
	docker-compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV_FILE) down 2>/dev/null || true

# 重启服务
restart:
	@echo "重启服务..."
	docker-compose -f $(COMPOSE_FILE) restart

# 查看日志
logs:
	docker-compose -f $(COMPOSE_FILE) logs -f

# 查看服务状态
status:
	docker-compose -f $(COMPOSE_FILE) ps

# 清理资源
clean:
	@echo "清理Docker资源..."
	docker-compose -f $(COMPOSE_FILE) down --volumes --rmi all
	docker system prune -f

# 深度清理
clean-all:
	@echo "深度清理Docker资源..."
	docker-compose -f $(COMPOSE_FILE) down --volumes --rmi all
	docker system prune -a -f --volumes

# 备份数据
backup:
	@echo "备份研究结果..."
	mkdir -p backup/$(shell date +%Y%m%d_%H%M%S)
	docker cp deep-researcher-app:/app/research_result backup/$(shell date +%Y%m%d_%H%M%S)/ 2>/dev/null || \
	cp -r research_result backup/$(shell date +%Y%m%d_%H%M%S)/
	@echo "备份完成: backup/$(shell date +%Y%m%d_%H%M%S)/"

# 进入容器shell
shell:
	docker-compose -f $(COMPOSE_FILE) exec deep-researcher /bin/bash

# 更新应用
update:
	@echo "更新应用..."
	git pull origin main
	make down
	make build
	make up
	@echo "更新完成!"

# 查看资源使用
stats:
	docker stats $(shell docker-compose -f $(COMPOSE_FILE) ps -q)

# 检查健康状态
health:
	@echo "检查API健康状态..."
	curl -f http://localhost:8000/health || echo "API服务异常"
	@echo "检查前端状态..."
	curl -f http://localhost:8501 > /dev/null || echo "前端服务异常"

# 环境配置
setup:
	@echo "初始化环境配置..."
	@if [ ! -f .env ]; then \
		cp deploy/configs/env.example .env; \
		echo "已创建.env文件，请编辑配置后再启动服务"; \
	else \
		echo ".env文件已存在"; \
	fi
	mkdir -p research_result/cache research_result/reports

# 生产部署前检查
pre-deploy:
	@echo "部署前检查..."
	@if grep -q "your_openai_api_key_here" .env; then \
		echo "❌ 请配置OPENAI_API_KEY"; \
		exit 1; \
	fi
	@echo "✅ 配置检查通过"

# 快速启动（推荐用于新手）
quick-start: setup pre-deploy up
	@echo "🚀 快速启动完成!"
	@echo "访问 http://localhost:8501 开始使用"
