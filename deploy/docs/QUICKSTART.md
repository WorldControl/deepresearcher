# Deep Researcher 快速开始

## 🚀 30秒快速部署

### 前提条件
- 安装Docker和Docker Compose
- 准备OpenAI API密钥

### 一键启动
```bash
# 1. 配置环境变量
cp deploy/configs/env.example .env
# 编辑.env文件，设置OPENAI_API_KEY

# 2. 启动服务
./deploy/scripts/start.sh

# 3. 访问应用
# 打开浏览器访问: http://localhost:8501
```

## 📋 常用命令

### 服务管理
```bash
# 启动服务
./deploy/scripts/start.sh prod    # 生产模式
./deploy/scripts/start.sh dev     # 开发模式

# 停止服务
./deploy/scripts/stop.sh

# 查看状态
docker-compose -f deploy/docker/docker-compose.yml ps
```

### 使用Makefile（推荐）
```bash
cd deploy/scripts

make help          # 查看所有命令
make quick-start   # 一键启动
make up            # 启动生产模式
make dev           # 启动开发模式
make down          # 停止服务
make logs          # 查看日志
```

## 🔧 配置要点

### 必需配置
在`.env`文件中设置：
```bash
OPENAI_API_KEY=sk-your_actual_api_key_here
```

### 可选配置
```bash
SEARCH_API_KEY=your_search_key    # 搜索功能
DEBUG=false                       # 调试模式
LOG_LEVEL=INFO                    # 日志级别
```

## 🌐 访问地址

启动成功后，访问以下地址：
- **前端界面**: http://localhost:8501
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 🐛 常见问题

### 端口被占用
```bash
# 修改端口（编辑deploy/docker/docker-compose.yml）
ports:
  - "8502:8501"  # 前端改为8502端口
  - "8001:8000"  # API改为8001端口
```

### API密钥配置
确保在`.env`文件中正确设置：
```bash
OPENAI_API_KEY=sk-proj-...  # 以sk-开头的完整密钥
```

### 查看日志
```bash
cd deploy/scripts && make logs
```

## 📚 更多信息

详细文档: [deploy/docs/DEPLOYMENT.md](DEPLOYMENT.md)
