# Deep Researcher 简化部署指南

本指南介绍如何使用Docker部署Deep Researcher项目的简化版本。

## 📋 部署概览

Deep Researcher支持以下部署模式：
- **开发模式**: 支持代码热重载的开发环境
- **生产模式**: 优化的生产环境

## 🔧 环境要求

### 系统要求
- Docker 20.10+
- Docker Compose 2.0+
- 至少2GB可用内存
- 至少1GB可用磁盘空间

### 网络端口
- `8000`: API服务器
- `8501`: Streamlit前端

## 📁 目录结构

```
deploy/
├── docker/                 # Docker配置文件
│   ├── docker-compose.yml     # 生产环境配置
│   ├── docker-compose.dev.yml # 开发环境配置
│   ├── Dockerfile             # 容器镜像配置
│   └── .dockerignore          # Docker忽略文件
├── scripts/                # 部署脚本
│   ├── start.sh              # 启动脚本
│   ├── stop.sh               # 停止脚本
│   └── Makefile              # 便捷命令
├── configs/                # 配置文件
│   └── env.example           # 环境变量示例
└── docs/                   # 部署文档
    └── DEPLOYMENT.md         # 本文档
```

## 🚀 快速开始

### 1. 环境配置
```bash
# 复制环境变量示例文件
cp deploy/configs/env.example .env

# 编辑环境变量文件
nano .env
```

**重要**: 请确保在`.env`文件中配置：
- `OPENAI_API_KEY`: OpenAI API密钥（必需）
- `SEARCH_API_KEY`: 搜索服务API密钥（可选）

### 2. 启动服务

#### 方法1: 使用启动脚本（推荐）
```bash
# 生产模式
./deploy/scripts/start.sh prod

# 开发模式
./deploy/scripts/start.sh dev
```

#### 方法2: 使用Makefile
```bash
# 进入deploy/scripts目录
cd deploy/scripts

# 快速启动（推荐新手）
make quick-start

# 或手动启动
make setup    # 初始化配置
make up       # 生产模式
make dev      # 开发模式
```

#### 方法3: 使用Docker Compose
```bash
# 生产模式
docker-compose -f deploy/docker/docker-compose.yml up -d

# 开发模式
docker-compose -f deploy/docker/docker-compose.yml -f deploy/docker/docker-compose.dev.yml up -d
```

### 3. 访问应用
- **前端界面**: http://localhost:8501
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## ⚙️ 配置说明

### 环境变量配置
主要配置项：

```bash
# API配置
API_HOST=0.0.0.0
API_PORT=8000

# LLM配置
OPENAI_API_KEY=sk-...          # 必需
OPENAI_MODEL=gpt-4

# 搜索配置
SEARCH_API_KEY=...             # 可选
SEARCH_ENGINE=google

# 应用配置
DEBUG=false
LOG_LEVEL=INFO
CACHE_TYPE=file
```

### 开发模式特性
- 代码热重载
- 详细调试日志
- 源码挂载到容器

### 生产模式特性
- 优化的容器配置
- 非root用户运行
- 健康检查

## 🔄 常用操作

### 使用脚本（推荐）
```bash
# 启动服务
./deploy/scripts/start.sh [dev|prod]

# 停止服务
./deploy/scripts/stop.sh

# 停止并清理资源
./deploy/scripts/stop.sh --clean
```

### 使用Makefile
```bash
cd deploy/scripts

# 查看所有命令
make help

# 服务管理
make up         # 启动生产环境
make dev        # 启动开发环境
make down       # 停止服务
make restart    # 重启服务

# 运维操作
make logs       # 查看日志
make status     # 查看状态
make shell      # 进入容器
make backup     # 备份数据
make clean      # 清理资源
```

### 使用Docker Compose
```bash
# 查看服务状态
docker-compose -f deploy/docker/docker-compose.yml ps

# 查看日志
docker-compose -f deploy/docker/docker-compose.yml logs -f

# 重启服务
docker-compose -f deploy/docker/docker-compose.yml restart

# 停止服务
docker-compose -f deploy/docker/docker-compose.yml down
```

## 📊 监控和维护

### 健康检查
```bash
# 使用Makefile
cd deploy/scripts && make health

# 手动检查
curl http://localhost:8000/health
curl http://localhost:8501
```

### 日志管理
```bash
# 查看实时日志
cd deploy/scripts && make logs

# 或直接使用Docker Compose
docker-compose -f deploy/docker/docker-compose.yml logs -f
```

### 数据备份
```bash
# 使用Makefile备份
cd deploy/scripts && make backup

# 手动备份
mkdir -p backup/$(date +%Y%m%d_%H%M%S)
cp -r research_result backup/$(date +%Y%m%d_%H%M%S)/
```

## 🐛 故障排除

### 常见问题

#### 1. 端口冲突
```bash
# 检查端口占用
netstat -tlnp | grep :8501

# 修改端口（在docker-compose.yml中）
ports:
  - "8502:8501"  # 使用其他端口
```

#### 2. 权限问题
```bash
# 检查文件权限
ls -la research_result/

# 修复权限
sudo chown -R $USER:$USER research_result/
```

#### 3. 容器启动失败
```bash
# 查看详细日志
docker-compose -f deploy/docker/docker-compose.yml logs

# 重新构建镜像
docker-compose -f deploy/docker/docker-compose.yml build --no-cache
```

### 调试模式
启用调试模式获取更多信息：

```bash
# 在.env文件中设置
DEBUG=true
LOG_LEVEL=DEBUG

# 重启服务
cd deploy/scripts && make restart
```

## 🔄 更新和升级

### 应用更新流程
```bash
# 使用Makefile（推荐）
cd deploy/scripts && make update

# 手动更新
git pull origin main
./deploy/scripts/stop.sh
docker-compose -f deploy/docker/docker-compose.yml build --no-cache
./deploy/scripts/start.sh
```

## 📈 性能优化

### 资源配置
根据使用场景调整：

```yaml
# 在docker-compose.yml中添加资源限制
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '1.0'
    reservations:
      memory: 1G
      cpus: '0.5'
```

### 存储优化
```bash
# 定期清理缓存
rm -rf research_result/cache/*

# 清理Docker资源
cd deploy/scripts && make clean
```

## 🔒 安全建议

1. **环境变量保护**
   ```bash
   chmod 600 .env
   ```

2. **网络访问控制**
   - 仅在必要时暴露端口
   - 使用防火墙限制访问

3. **定期更新**
   ```bash
   # 更新基础镜像
   docker pull python:3.11-slim
   cd deploy/scripts && make build
   ```

## 📞 技术支持

如需技术支持，请提供：
1. 部署模式（dev/prod）
2. Docker版本：`docker --version`
3. 错误日志：`cd deploy/scripts && make logs`
4. 系统信息：`uname -a`

---

**注意**: 此简化版本移除了Redis缓存和Nginx代理，适合中小规模部署。如需高可用部署，请考虑添加相应组件。
