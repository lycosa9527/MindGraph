# MindGraph

**Enterprise-Grade AI Diagram Generation Platform** | **企业级AI图表生成平台**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5+-42b883.svg)](https://vuejs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6+-3178c6.svg)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-5.15.1-brightgreen.svg)](CHANGELOG.md)
[![Built with Cursor](https://img.shields.io/badge/Built%20with-Cursor%20AI-blueviolet.svg)](https://cursor.sh)
[![wakatime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/@lyc9527/projects/tkidgnziyn)

Transform natural language into professional visual diagrams. API-first platform for Dify, Coze, and HTTP integrations. Complete interactive suite for K-12 education with AI-powered learning tools.

将自然语言转换为专业可视化图表。面向Dify、Coze和HTTP集成的API优先平台。面向K-12教育的完整交互套件，配备AI驱动的学习工具。

---

## 💡 Project Highlight | 项目亮点

> **Built with [Cursor AI](https://cursor.sh)** - This enterprise-grade application demonstrates that anyone with vision can build professional software through AI-assisted development, regardless of technical background.  
> **使用 [Cursor AI](https://cursor.sh) 构建** - 这个企业级应用证明了在AI时代，任何有愿景的人都可以通过AI辅助开发构建专业软件，无论技术背景如何。

---

## ✨ Features | 核心功能

### 🎯 Diagram Types | 图表类型
**10 Professional Diagram Types | 10种专业图表类型**

- **Thinking Maps | 思维图示** (8 types | 8种): Circle Map, Bubble Map, Double Bubble Map, Tree Map, Brace Map, Flow Map, Multi-Flow Map, Bridge Map
- **Mind Map | 思维导图**: Radial brainstorming and concept organization | 放射状头脑风暴和概念组织
- **Concept Map | 概念图**: Advanced relationship mapping between concepts | 概念间的高级关系映射

### 🧠 Thinking Tools | 思考工具
**9 Analysis Tools | 9种分析工具**

5W1H Analysis, Four Quadrant, Three Position, WHWM Analysis, Factor Analysis, Goal Analysis, Possibility Analysis, Result Analysis, Perspective Analysis

### 🤖 AI-Powered Generation | AI驱动生成
- **Smart Classification | 智能分类**: Auto-detect diagram type from natural language | 从自然语言自动检测图表类型
- **Multi-LLM Support | 多LLM支持**: Qwen, DeepSeek, Kimi (Moonshot), Hunyuan, Doubao (Volcengine)
- **Node Palette | 节点调色板**: AI-suggested nodes with streaming batches | AI推荐节点流式批次
- **Auto-Complete | 智能补全**: Context-aware diagram completion | 上下文感知图表补全
- **Math & Chemical Formulas | 数学和化学公式**: LaTeX and chemical equation rendering | LaTeX和化学方程式渲染
- **Bilingual Support | 双语支持**: Perfect Chinese/English support | 完美中英文支持

### 🎤 Voice Input | 语音输入
- **Real-time Recognition | 实时识别**: Browser-based speech-to-text | 浏览器语音转文字
- **Voice-to-Diagram | 语音生成图表**: Speak your idea, get a diagram | 说出想法，生成图表
- **Hands-free Editing | 免提编辑**: Voice commands for node editing | 语音命令编辑节点

### 🎓 Education Features | 教育功能
- **Interactive Learning Mode | 交互式学习模式**: AI tutor with real-time validation | AI导师实时验证
- **20% Intelligent Knockout | 20%智能隐藏**: Active recall practice | 主动回忆练习
- **Multi-Angle Teaching | 多角度教学**: Tests understanding from multiple perspectives | 从多个角度测试理解

### 🔐 Authentication & Security | 认证与安全
- **API Key Authentication | API密钥认证**: For external services (Dify, partners) | 用于外部服务（Dify、合作伙伴）
- **JWT Token Authentication | JWT令牌认证**: For authenticated users | 用于已认证用户
- **SMS Verification | 短信验证**: Secure phone-based authentication | 安全的手机验证
- **Admin Panel | 管理面板**: Complete API key management | 完整的API密钥管理

### 💾 Database & Storage | 数据库和存储
- **Hybrid Architecture | 混合架构**: SQLite (persistent) + Redis (ephemeral) + Qdrant (vectors) | SQLite（持久化）+ Redis（临时数据）+ Qdrant（向量）
- **Automated Backups | 自动备份**: Daily scheduled backups with retention policy | 每日定时备份与保留策略
- **Recovery Wizard | 恢复向导**: Interactive database recovery system | 交互式数据库恢复系统
- **Data Anomaly Detection | 数据异常检测**: Detects significant data loss | 检测重大数据丢失

### 📚 Knowledge Space (RAG) | 知识空间 (RAG)
- **Document Management | 文档管理**: Upload, process, and manage knowledge documents | 上传、处理和管理知识文档
- **Intelligent Chunking | 智能分块**: Semantic chunking with MindChunk or fast SemChunk | 使用MindChunk语义分块或快速SemChunk
- **Advanced Retrieval | 高级检索**: Vector search, keyword search, hybrid retrieval with reranking | 向量搜索、关键词搜索、混合检索与重排序
- **Chunk Testing | 分块测试**: Evaluate and optimize chunking strategies | 评估和优化分块策略
- **Background Processing | 后台处理**: Celery-based async document processing | 基于Celery的异步文档处理

### ⚡ Performance | 性能表现
- **4,000+ Concurrent Connections | 4,000+并发连接**: FastAPI async architecture | FastAPI异步架构
- **Average Response Time | 平均响应时间**: 8.7s end-to-end | 8.7秒端到端
- **Production Ready | 生产就绪**: FastAPI + Uvicorn ASGI
- **systemd Support | systemd支持**: One-command Linux deployment | 一键Linux部署

---

## 🏗️ Tech Stack | 技术栈

### Frontend | 前端
- **Vue 3.5+** - Composition API with `<script setup>` syntax
- **TypeScript 5.6+** - Type-safe development
- **Vite 6.0+** - Next-generation frontend tooling
- **Tailwind CSS 4.0+** - Utility-first CSS framework
- **Pinia** - Intuitive state management
- **Vue Router** - Official routing solution
- **Vue Flow** - Interactive diagram canvas

### Backend | 后端
- **Python 3.8+** - High-performance backend
- **FastAPI** - Modern async web framework
- **Uvicorn** - Lightning-fast ASGI server
- **SQLite** - Persistent data storage
- **Redis** - Caching and session management
- **Qdrant** - Vector database for RAG and semantic search
- **Celery** - Distributed task queue for background processing
- **Playwright** - PNG diagram generation

### AI/LLM | AI/大语言模型
- **Qwen** - Primary LLM for diagram generation
- **DeepSeek** - Alternative LLM option
- **Doubao (Volcengine)** - Bytedance LLM integration
- **Hunyuan** - Tencent LLM integration

---

## 🚀 Quick Start | 快速开始

### Prerequisites | 前置要求

- **Python 3.8+** (Recommended: 3.13+ | 推荐：3.13+)
- **Node.js 18+** (Required for frontend | 前端必需)
- **Redis 7.0+** (Required | 必需) - For caching, rate limiting, sessions | 用于缓存、速率限制、会话
- **Qdrant** (Required for Knowledge Space | 知识空间必需) - Vector database for RAG | RAG向量数据库
- Internet connection for LLM API access | 互联网连接以访问LLM API

**Setup Redis | Redis设置:**

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server && sudo systemctl enable redis-server

# macOS
brew install redis && brew services start redis

# Verify | 验证
redis-cli ping  # Should return: PONG
```

**Setup Qdrant | Qdrant设置:**

```bash
# Recommended: Use provided script | 推荐：使用提供的脚本
bash scripts/install_qdrant.sh

# Or Docker | 或使用Docker
docker run -p 6333:6333 qdrant/qdrant

# Verify | 验证
curl http://localhost:6333/collections  # Should return JSON
```

### Installation | 安装

```bash
# 1. Clone repository | 克隆仓库
git clone https://github.com/lycosa9527/MindGraph.git
cd MindGraph

# 2. Install backend dependencies and Playwright browsers | 安装后端依赖和Playwright浏览器
python scripts/setup.py

# 3. Build frontend | 构建前端
cd frontend
npm install
npm run build
cd ..

# 4. Configure environment | 配置环境
cp env.example .env
# Edit .env and add your QWEN_API_KEY | 编辑.env并添加您的QWEN_API_KEY
```

**Frontend Development | 前端开发:**

```bash
cd frontend
npm run dev  # Hot reload development mode | 热重载开发模式
```

### Configuration | 配置

**Required environment variables | 必需的环境变量:**

```bash
# LLM API Key (Required | 必需)
QWEN_API_KEY=your-qwen-api-key-here

# Redis Configuration (REQUIRED | 必需)
REDIS_URL=redis://localhost:6379/0

# Qdrant Configuration (REQUIRED for Knowledge Space | 知识空间必需)
QDRANT_HOST=localhost:6333

# Server Configuration | 服务器配置
PORT=9527
HOST=0.0.0.0
DEBUG=False  # Set to True for development | 开发时设置为True

# Authentication Mode | 认证模式 (standard, enterprise, demo, bayi)
AUTH_MODE=standard
```

**See `env.example` for complete configuration options | 查看 `env.example` 了解完整配置选项**

### Running the Server | 运行服务器

```bash
python main.py
```

**Important Notes | 重要提示:**

- **Redis** must be running before starting the server | Redis必须在启动服务器前运行
- **Qdrant** is required for Knowledge Space features | 知识空间功能需要Qdrant
- **Celery** worker starts automatically for background processing | Celery工作进程自动启动用于后台处理
- **API documentation** (`/docs`) is only available when `DEBUG=True` | API文档 (`/docs`) 仅在 `DEBUG=True` 时可用

### Access Points | 访问入口

| Service | URL | Description |
|---------|-----|-------------|
| **Interactive Editor** | http://localhost:9527/editor | Full-featured web editor |
| **API Documentation** | http://localhost:9527/docs | Interactive Swagger UI (DEBUG mode only) |
| **Admin Panel** | http://localhost:9527/admin | Manage API keys, users, settings |
| **Health Check** | http://localhost:9527/health | Server status endpoint |
| **Database Health** | http://localhost:9527/health/database | Database integrity check |
| **Redis Health** | http://localhost:9527/health/redis | Redis connection status |
| **Qdrant Health** | http://localhost:9527/health/qdrant | Qdrant connection status |
| **Knowledge Space** | http://localhost:9527/knowledge-space | Knowledge Space management interface |

---

## 🔌 API Integration | API集成

### Authentication | 身份验证

MindGraph supports two authentication methods | MindGraph支持两种认证方式:

**1. API Key | API密钥** (for external services | 用于外部服务)

```http
POST /api/generate_png
Content-Type: application/json
X-API-Key: mg_your_api_key_here

{
  "prompt": "Compare cats and dogs",
  "language": "en"
}
```

**2. JWT Token | JWT令牌** (for authenticated users | 用于已认证用户)

```http
POST /api/generate_png
Content-Type: application/json
Authorization: Bearer your_jwt_token_here

{
  "prompt": "Compare cats and dogs",
  "language": "en"
}
```

**Generate API Key | 生成API密钥:**

1. Access admin panel at `/admin` | 访问 `/admin` 管理面板
2. Go to "🔑 API Keys" tab | 进入"🔑 API Keys"标签页
3. Click "Create New API Key" | 点击"创建新API密钥"
4. Copy the generated key (shown only once!) | 复制生成的密钥（仅显示一次！）

**Note | 注意:** API keys are generated with the `mg_` prefix | API密钥以 `mg_` 前缀生成

### Dify Integration | Dify集成

**HTTP Request Node Configuration | HTTP请求节点配置:**

```json
{
  "url": "http://your-server:9527/api/generate_png",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "X-API-Key": "mg_your_key_here"
  },
  "body": {
    "prompt": "{{user_input}}",
    "language": "en"
  }
}
```

**Returns | 返回:** Binary PNG image ready for display | 可直接显示的二进制PNG图像

### Python Example | Python示例

```python
import requests

def generate_diagram(prompt, api_key, language="en"):
    response = requests.post(
        "http://localhost:9527/api/generate_png",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key
        },
        json={
            "prompt": prompt,
            "language": language
        }
    )
    
    if response.status_code == 200:
        with open("diagram.png", "wb") as f:
            f.write(response.content)
        return "diagram.png"
    else:
        raise Exception(f"Error: {response.json()}")

# Usage
api_key = "mg_abc123xyz456..."  # Generated from admin panel
diagram = generate_diagram("Compare online vs offline learning", api_key)
print(f"Saved: {diagram}")
```

### JavaScript Example | JavaScript示例

```javascript
const axios = require('axios');
const fs = require('fs');

async function generateDiagram(prompt, apiKey, language = 'en') {
    const response = await axios.post(
        'http://localhost:9527/api/generate_png',
        { prompt, language },
        {
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey
            },
            responseType: 'arraybuffer'
        }
    );
    
    fs.writeFileSync('diagram.png', response.data);
    return 'diagram.png';
}

// Usage
const apiKey = 'mg_abc123xyz456...';  // Generated from admin panel
generateDiagram('Create a mind map about AI', apiKey)
    .then(file => console.log(`Saved: ${file}`))
    .catch(err => console.error('Error:', err));
```

---

## 🎓 Interactive Learning Mode | 交互式学习模式

**AI-Powered Tutoring for K-12 Education | K-12教育AI辅导**

Transform any diagram into an interactive learning experience | 将任何图表转换为交互式学习体验:

### How It Works | 工作原理

1. **Create or Generate Diagram | 创建或生成图表** - Use AI or manual creation | 使用AI或手动创建
2. **Click "Learning" Button | 点击"学习"按钮** - System analyzes and hides 20% of nodes | 系统分析并隐藏20%的节点
3. **Answer Questions | 回答问题** - AI validates answers with semantic understanding | AI通过语义理解验证答案
4. **Get Real-time Feedback | 获得实时反馈** - Correct answers progress, wrong answers trigger teaching | 正确答案继续，错误答案触发教学
5. **Multi-Level Teaching | 多级教学** - Progressive escalation with different perspectives | 从不同角度渐进升级
6. **Complete Session | 完成会话** - View final score and performance summary | 查看最终分数和表现总结

### Educational Benefits | 教育价值

✅ **Active Recall | 主动回忆** - Research-proven memory retention technique | 经研究证明的记忆保持技术  
✅ **Intelligent Tutoring | 智能辅导** - AI adapts teaching based on misconceptions | AI根据误解调整教学  
✅ **Multi-Angle Learning | 多角度学习** - Tests understanding from 4 cognitive perspectives | 从4个认知角度测试理解  
✅ **Immediate Feedback | 即时反馈** - Real-time validation with explanations | 实时验证和解释  
✅ **Visual Learning | 视觉学习** - Node highlighting and animations | 节点高亮和动画  

---

## 📚 Knowledge Space (RAG) | 知识空间 (RAG)

**Enterprise-Grade RAG System for Document Management | 企业级RAG文档管理系统**

### Features | 功能特性

- **Document Upload & Processing | 文档上传和处理**: Support for PDF, DOCX, TXT, MD with automatic extraction and background processing | 支持PDF、DOCX、TXT、MD格式，自动提取和后台处理
- **Intelligent Chunking | 智能分块**: SemChunk (fast) or MindChunk (LLM-based semantic) with configurable size and overlap | SemChunk（快速）或MindChunk（基于LLM的语义分块），可配置大小和重叠
- **Advanced Retrieval | 高级检索**: Vector search, keyword search, hybrid retrieval with Qwen3-rerank model | 向量搜索、关键词搜索、混合检索与Qwen3-rerank模型
- **Chunk Testing & Evaluation | 分块测试与评估**: Test strategies, evaluate quality, performance metrics | 测试策略、评估质量、性能指标
- **Vector Database | 向量数据库**: Qdrant integration with per-user isolation and automatic embeddings | Qdrant集成，每用户隔离，自动嵌入生成

### Usage | 使用方法

1. **Access Knowledge Space | 访问知识空间**: Navigate to `/knowledge-space` in the web interface | 在Web界面中导航到 `/knowledge-space`
2. **Upload Documents | 上传文档**: Upload your knowledge documents | 上传您的知识文档
3. **Wait for Processing | 等待处理**: Documents are processed in the background | 文档在后台处理
4. **Query Knowledge | 查询知识**: Use semantic search to find relevant information | 使用语义搜索查找相关信息
5. **Test Chunking | 测试分块**: Evaluate and optimize chunking strategies | 评估和优化分块策略

### Configuration | 配置

Key environment variables for Knowledge Space | 知识空间的关键环境变量:

```bash
# Qdrant Configuration (REQUIRED)
QDRANT_HOST=localhost:6333

# Chunking Configuration
CHUNKING_ENGINE=semchunk  # or mindchunk for LLM-based chunking
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# Retrieval Configuration
DEFAULT_RETRIEVAL_METHOD=hybrid  # vector, keyword, or hybrid
HYBRID_VECTOR_WEIGHT=0.5
HYBRID_KEYWORD_WEIGHT=0.5
RERANKING_MODE=reranking_model

# Embedding Configuration
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4
DASHSCOPE_RERANK_MODEL=qwen3-rerank
```

---

## 📚 Documentation

- [**API Reference**](docs/API_REFERENCE.md) - Complete API documentation with bilingual examples
- [**API Key Authentication**](docs/API_KEY_AUTHENTICATION_GUIDE.md) - Security implementation guide
- [**Math & Chemical Formulas**](docs/MATH_CHEMICAL_IMPLEMENTATION_GUIDE.md) - LaTeX and chemical equation guide
- [**Auto-Complete Cache**](docs/AUTO_COMPLETE_CACHE_FRAMEWORK.md) - Cache framework documentation
- [**Tab Mode Feature**](docs/TAB_MODE_FEATURE_DESIGN.md) - Tab mode autocomplete and expansion
- [**Health Check**](docs/HEALTH_CHECK.md) - Health check endpoints documentation
- [**Changelog**](CHANGELOG.md) - Version history and updates

---

## 🧪 Testing | 测试

```bash
# Start server | 启动服务器
python main.py

# Run tests (in another terminal) | 运行测试（在另一个终端）
cd tests
python test_all_agents.py production
```

**Test Coverage | 测试覆盖:**
- 10 diagram types with diverse topics | 10种图表类型及多样化主题
- 9 thinking tools with analysis scenarios | 9种思考工具及分析场景
- Concurrent request handling | 并发请求处理
- PNG generation validation | PNG生成验证
- Performance benchmarking | 性能基准测试

---

## 📊 Performance Metrics | 性能指标

| Metric 指标 | Value 值 | Notes 说明 |
|--------|-------|-------|
| **Average Response Time 平均响应时间** | 8.7s | End-to-end (LLM + rendering + export) 端到端 |
| **Concurrent Connections 并发连接** | 4,000+ | FastAPI async architecture FastAPI异步架构 |
| **Success Rate 成功率** | 97.8% | Production simulation results 生产模拟结果 |
| **LLM Processing LLM处理** | 5.94s | Main bottleneck (69% of total time) 主要瓶颈（总时间的69%） |
| **PNG Export PNG导出** | 2.7s | Playwright rendering (31% of total time) Playwright渲染（总时间的31%） |

---

## 🤝 Contributing | 贡献

We welcome contributions! | 欢迎贡献！ Please follow these steps | 请遵循以下步骤:

1. Fork the repository | Fork仓库
2. Create a feature branch | 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. Commit your changes | 提交更改 (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch | 推送到分支 (`git push origin feature/AmazingFeature`)
5. Open a Pull Request | 打开Pull Request

---

## 📄 License | 许可证

This project is licensed under a **Proprietary License (All Rights Reserved)** - see the [LICENSE](LICENSE) file for details.  
本项目采用**专有许可证（保留所有权利）** - 详情请参阅[LICENSE](LICENSE)文件。

**IMPORTANT NOTICE | 重要声明:**

This software is **NOT open source**. All use, modification, distribution, or execution requires explicit written permission.  
本软件**不是开源软件**。所有使用、修改、分发或执行都需要明确的书面许可。

**Licensing Inquiries | 许可咨询:**

- **GitHub**: [lycosa9527](https://github.com/lycosa9527)
- **Company | 公司**: 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)

See [NOTICE](NOTICE) file for complete trademark and attribution information.

---

## 💬 Support | 支持

**Questions? Issues? Feedback? | 问题？错误？反馈？**

- 🐛 **Issues | 问题**: [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
- 📧 **Email | 邮件**: Contact via GitHub | 通过GitHub联系
- 📖 **Docs | 文档**: [API Reference | API参考](docs/API_REFERENCE.md)

---

## 🌟 Acknowledgments | 致谢

**Developed by 北京思源智教科技有限公司 | 由北京思源智教科技有限公司开发**  
**Beijing Siyuan Zhijiao Technology Co., Ltd. | 北京思源智教科技有限公司**

> **Powered by [Cursor AI](https://cursor.sh)** - The AI-first code editor that made this project possible  
> **由 [Cursor AI](https://cursor.sh) 驱动** - 让这个项目成为可能的AI优先代码编辑器

---

### ⭐ Star This Project | 给项目加星

If you find MindGraph useful, please consider giving it a ⭐ on GitHub!  
如果您觉得MindGraph有用，请考虑在GitHub上给它一个⭐！
