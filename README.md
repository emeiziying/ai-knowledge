# AI Knowledge Base

AI知识库应用是一个集成了人工智能能力的知识管理系统，支持文档上传、智能问答和语义搜索功能。

## 项目结构

```
ai-knowledge-base/
├── backend/                 # 后端API服务
│   ├── app/                # 应用代码
│   ├── requirements.txt    # Python依赖
│   └── Dockerfile         # 后端Docker配置
├── frontend/               # 前端React应用
│   ├── src/               # 源代码
│   ├── package.json       # Node.js依赖
│   └── Dockerfile         # 前端Docker配置
├── docker-compose.yml     # 生产环境Docker配置
├── docker-compose.dev.yml # 开发环境Docker配置
└── README.md             # 项目说明
```

## 快速开始

### 开发环境

1. 启动基础服务（数据库、缓存等）：
```bash
docker-compose -f docker-compose.dev.yml up -d
```

2. 启动后端服务：
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

3. 启动前端服务：
```bash
cd frontend
npm install
npm run dev
```

### 生产环境

使用Docker Compose一键启动所有服务：
```bash
docker-compose up -d
```

## 服务端口

- 前端应用: http://localhost:3000
- 后端API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Qdrant: http://localhost:6333
- MinIO: http://localhost:9000 (控制台: http://localhost:9001)

## 技术栈

### 后端
- FastAPI (Python)
- PostgreSQL
- Redis
- Qdrant (向量数据库)
- MinIO (对象存储)

### 前端
- React + TypeScript
- Ant Design
- Vite
- Zustand (状态管理)

## 开发指南

详细的开发指南请参考项目规格文档：
- 需求文档: `.kiro/specs/ai-knowledge-base/requirements.md`
- 设计文档: `.kiro/specs/ai-knowledge-base/design.md`
- 任务列表: `.kiro/specs/ai-knowledge-base/tasks.md`