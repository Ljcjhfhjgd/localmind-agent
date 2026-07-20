# LocalMind Agent

本地 AI 智能工作台 —— 基于 Ollama + FastAPI + Vue 3 构建的全栈 AI 桌面应用。

集成 5 个本地大模型，覆盖**日常对话、多 Agent 协作、知识库 RAG、胸片 AI 诊断、邮件生成**五大业务场景。

---

## 功能演示

| 多 Agent 协作 | 胸片诊断 | 知识库 RAG |
|---|---|---|
| Master-Worker 架构，7 个 Worker 独立推理 | ResNet50 对比学习，20 类疾病分类 | FAISS + BM25 混合检索，来源标注 |
| 步骤条 + 时间线双视图实时展示 | OOD 检测 + 视觉模型二次验证 | 滑动窗口分块，LLM 评估检索质量 |

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Pinia + Vite + lucide-vue-next |
| 后端 | Python 3.10+ / FastAPI / asyncio |
| 模型 | Ollama（qwen2.5:3b、deepseek-r1:7b、minicpm-v 等 5 个模型） |
| 向量库 | FAISS + BM25 + bge-m3 嵌入 |
| 存储 | JSON 对话持久化 + ChromaDB |
| UI | Apple macOS 浅色风格 |

---

## 快速开始

### 方式一：Docker 部署（推荐，无需配环境）

```bash
git clone https://github.com/你的用户名/localmind-agent.git
cd localmind-agent
docker-compose up -d
浏览器打开 http://localhost。

方式二：本地开发
环境要求： Python 3.10+、Node.js 18+、Ollama

bash
# 1. 安装后端依赖
pip install -r requirements.txt

# 2. 安装前端依赖
cd frontend && npm install && cd ..

# 3. 拉取模型
ollama pull qwen2.5:3b-instruct
ollama pull deepseek-r1:7b
ollama pull minicpm-v:latest
ollama pull qwen3:4b-instruct
ollama pull qwen2.5:7b-instruct

# 4. 启动（后端 + 前端一键）
python start.py

# 5. 浏览器访问
http://localhost:8765/ui
五大模式
模式	功能
日常	流式对话、文件/图片上传、快速/深度思考切换、Ctrl+V 粘贴图片
Agent	Master-Worker 多 Agent 协作，7 个 Worker 独立推理，步骤条实时展示
知识库	文档上传、FAISS + BM25 混合检索、引用来源标注、多文档联合问答
胸片	ResNet50 对比学习诊断，20 类疾病分类，OOD 检测 + 视觉模型二次验证
邮件	AI 起草/润色/重写邮件，SMTP 发送，草稿箱管理
项目结构
text
localmind-agent/
├── agent/              # Agent 主类、对话管理、多 Agent 协作引擎
│   ├── core.py         # LocalMindAgent 主类
│   ├── conversation.py # 对话持久化管理
│   └── orchestrator/   # Master + 7 个 Worker
├── server/             # FastAPI 入口、路由、中间件
├── frontend/           # Vue 3 前端（Pinia 状态管理）
├── tools/              # 工具：搜索、代码执行、天气、翻译等
├── llm/                # Ollama API 封装
├── data/               # 对话持久化、设置
├── config.yaml         # 模型配置（切换模型只改这里）
├── start.py            # 一键启动脚本
├── Dockerfile          # Docker 容器化
└── docker-compose.yml  # 一键部署
配置
编辑 config.yaml 切换模型：

yaml
ollama:
  mode_models:
    default: qwen2.5:7b-instruct   # 日常
    fast: qwen2.5:3b-instruct      # 快速模式
    reasoning: deepseek-r1:7b      # 深度思考
    vision: minicpm-v:latest       # 视觉模型
    agent_planner: qwen3:4b-instruct  # Agent 规划