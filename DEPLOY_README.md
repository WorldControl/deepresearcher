# Deep Researcher 部署说明

## 📁 部署文件位置

所有部署相关文件已重新组织到 `deploy/` 目录：

```
deploy/
├── docker/                 # Docker配置
├── scripts/                # 启动脚本和Makefile
├── configs/                # 环境配置
└── docs/                   # 部署文档
```

## 🚀 快速启动

### 方法1: 使用启动脚本（推荐）
```bash
# 配置环境变量
cp deploy/configs/env.example .env
nano .env  # 设置OPENAI_API_KEY

# 启动服务
./deploy/scripts/start.sh
```

### 方法2: 使用Makefile
```bash
cd deploy/scripts
make quick-start
```

### 方法3: 使用Docker Compose
```bash
# 配置环境
cp deploy/configs/env.example .env

# 启动服务
docker-compose -f deploy/docker/docker-compose.yml up -d
```

## 📚 详细文档

- [快速开始](deploy/docs/QUICKSTART.md)
- [完整部署指南](deploy/docs/DEPLOYMENT.md)

## 🔧 常用命令

```bash
# 进入脚本目录
cd deploy/scripts

# 查看所有可用命令
make help

# 启动/停止服务
make up      # 启动
make down    # 停止
make dev     # 开发模式
make logs    # 查看日志
```

## 🌐 访问地址

- 前端界面: http://localhost:8501
- API文档: http://localhost:8000/docs

---

**注意**: 旧的部署文件已移动到 `deploy/` 目录，请使用新的路径和命令。
