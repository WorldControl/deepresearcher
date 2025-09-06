# Deep Researcher 容器化快速开始

## 🚀 一键启动

### 前提条件
- 安装Docker和Docker Compose
- 准备OpenAI API密钥

### 快速启动步骤

1. **配置环境变量**
```bash
# 复制配置文件
cp env.example .env

# 编辑配置文件，至少需要配置:
# OPENAI_API_KEY=your_actual_api_key
nano .env
```

2. **启动服务**
```bash
# 方法1: 使用启动脚本（推荐）
./docker-start.sh

# 方法2: 使用Makefile
make quick-start

# 方法3: 使用Docker Compose
docker-compose up -d
```

3. **访问应用**
- 前端界面: http://localhost:8501
- API文档: http://localhost:8000/docs

## 📋 可用命令

### 使用Makefile（推荐）
```bash
make help          # 查看所有命令
make up             # 启动标准环境  
make dev            # 启动开发环境
make prod           # 启动生产环境
make down           # 停止服务
make logs           # 查看日志
make clean          # 清理资源
make backup         # 备份数据
```

### 使用启动脚本
```bash
./docker-start.sh dev        # 开发模式
./docker-start.sh standard   # 标准模式（默认）
./docker-start.sh production # 生产模式
```

### 使用Docker Compose
```bash
docker-compose up -d                        # 标准启动
docker-compose --profile production up -d   # 生产启动
docker-compose down                          # 停止服务
docker-compose logs -f                       # 查看日志
```

## 🔧 配置选项

### 环境模式
- **dev**: 开发模式，支持代码热重载
- **standard**: 标准模式，包含应用+Redis
- **production**: 生产模式，包含Nginx反向代理

### 重要环境变量
```bash
# 必需配置
OPENAI_API_KEY=sk-...          # OpenAI API密钥
SEARCH_API_KEY=...             # 搜索API密钥

# 可选配置
DEBUG=false                    # 调试模式
LOG_LEVEL=INFO                 # 日志级别
CACHE_TYPE=redis               # 缓存类型
```

## 🔍 故障排除

### 常见问题
1. **端口冲突**: 修改docker-compose.yml中的端口映射
2. **权限问题**: 确保当前用户有Docker权限
3. **内存不足**: 增加Docker内存限制（至少4GB）

### 检查服务状态
```bash
make status         # 查看容器状态
make health         # 检查服务健康
make logs           # 查看详细日志
```

## 📚 更多信息

详细部署文档请参考: [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
