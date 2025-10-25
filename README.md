# MindGraph

**Enterprise-Grade AI Diagram Generation Platform** | **企业级AI图表生成平台**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-4.12.0-brightgreen.svg)](CHANGELOG.md)
[![Built with Cursor](https://img.shields.io/badge/Built%20with-Cursor%20AI-blueviolet.svg)](https://cursor.sh)
[![wakatime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/@lyc9527/projects/tkidgnziyn)

Transform natural language into professional visual diagrams. **API-first platform** for Dify, Coze, and any HTTP integration. **Complete interactive suite** for K-12 education with AI-powered learning tools.

将自然语言转换为专业可视化图表。面向Dify、Coze和任何HTTP集成的**API优先平台**。面向K-12教育的**完整交互套件**，配备AI驱动的学习工具。

---

## 💡 **Project Highlight** | **项目亮点**

> ### 🎯 **Built by a Non-Programmer with Cursor AI**
> 
> **English:** This **entire enterprise-grade application** was created by someone with **ZERO programming knowledge** using [Cursor AI](https://cursor.sh) - an AI-powered code editor. From FastAPI backend to interactive frontend, from database design to API security, **everything was built through AI pair programming**. This project proves that **anyone with vision and ideas can build professional software** in the AI era, regardless of technical background.
> 
> **中文:** 这个**完整的企业级应用**由一个**零编程知识**的人使用 [Cursor AI](https://cursor.sh)（AI驱动的代码编辑器）创建。从FastAPI后端到交互式前端，从数据库设计到API安全，**一切都通过AI结对编程完成**。这个项目证明了在AI时代，**任何有愿景和想法的人都可以构建专业软件**，无论技术背景如何。
>
> **Key Achievement | 关键成就:**
> - ✅ **6,900+ lines** of production code | **6,900+行**生产代码
> - ✅ **15 files modified** for security system | **15个文件**的安全系统
> - ✅ **4,000+ concurrent connections** supported | 支持**4,000+并发连接**
> - ✅ **10 diagram types** with AI generation | **10种图表类型**的AI生成
> - ✅ **Bilingual** English/Chinese support | **双语**中英文支持
> - ✅ **100% AI-assisted development** | **100% AI辅助开发**

---

## ✨ Features | 核心功能

### 🎯 10 Professional Diagram Types | 10种专业图表类型
- **Thinking Maps | 思维图示** (8 types | 8种): Circle, Bubble, Double Bubble, Tree, Brace, Flow, Multi-Flow, Bridge
- **Mind Map | 思维导图**: Radial brainstorming and concept organization | 放射状头脑风暴和概念组织
- **Concept Map | 概念图**: Advanced relationship mapping | 高级关系映射

### 🤖 AI-Powered Generation | AI驱动生成
- **Smart Classification | 智能分类**: Auto-detect diagram type from natural language | 从自然语言自动检测图表类型
- **Multi-LLM Support | 多LLM支持**: Qwen, DeepSeek, Kimi, Hunyuan
- **Bilingual | 双语**: Perfect Chinese/English support | 完美中英文支持

### 🎓 Education Features | 教育功能
- **Interactive Learning Mode | 交互式学习模式**: AI tutor with real-time validation | AI导师实时验证
- **20% Intelligent Knockout | 20%智能隐藏**: Active recall practice | 主动回忆练习
- **Multi-Angle Teaching | 多角度教学**: Tests understanding from multiple perspectives | 从多个角度测试理解

### 🔐 Secure Authentication | 安全认证
- **API Key Authentication | API密钥认证**: For external services (Dify, partners) | 用于外部服务（Dify、合作伙伴）
- **JWT Token Authentication | JWT令牌认证**: For authenticated users | 用于已认证用户
- **Admin Panel | 管理面板**: Complete API key management | 完整的API密钥管理

### ⚡ Performance | 性能表现
- **Async Architecture | 异步架构**: 4,000+ concurrent connections | 4,000+并发连接
- **Fast Response | 快速响应**: Average 8.7s end-to-end | 平均8.7秒端到端
- **Production Ready | 生产就绪**: FastAPI + Uvicorn ASGI

---

## 🚀 Quick Start | 快速开始

### Prerequisites | 前置要求

- **Python 3.8+** (Recommended: 3.13+ for best performance | 推荐：3.13+以获得最佳性能)
- Internet connection for LLM API access | 互联网连接以访问LLM API
- Modern web browser | 现代网页浏览器

### Installation | 安装

```bash
# 1. Clone repository
git clone https://github.com/lycosa9527/MindGraph.git
cd MindGraph

# 2. Install dependencies
python setup.py

# 3. Configure environment
cp env.example .env
# Edit .env and add your QWEN_API_KEY
```

### Configuration | 配置

**Required environment variables | 必需的环境变量:**

```bash
# LLM API Key (Required)
QWEN_API_KEY=your-qwen-api-key-here

# Optional: Additional LLM models
DEEPSEEK_API_KEY=your-deepseek-key
KIMI_API_KEY=your-kimi-key
HUNYUAN_SECRET_ID=your-hunyuan-id
HUNYUAN_SECRET_KEY=your-hunyuan-key

# Server Configuration
PORT=9527
EXTERNAL_HOST=localhost

# Authentication Mode (standard, enterprise, demo)
AUTH_MODE=standard

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
JWT_EXPIRY_HOURS=168
```

### Running the Server | 运行服务器

```bash
python run_server.py
```

**Server Output | 服务器输出:**
```
🚀 MindGraph FastAPI Server Starting...
Environment: production
Host: 0.0.0.0
Port: 9527
Workers: 4

✅ Server ready at: http://localhost:9527
✅ Interactive Editor: http://localhost:9527/editor
✅ API Documentation: http://localhost:9527/docs
✅ Admin Panel: http://localhost:9527/admin
```

### Access Points | 访问入口

| Service | URL | Description |
|---------|-----|-------------|
| **Interactive Editor** | http://localhost:9527/editor | Full-featured web editor |
| **API Documentation** | http://localhost:9527/docs | Interactive Swagger UI |
| **Admin Panel** | http://localhost:9527/admin | Manage API keys, users, settings |
| **Health Check** | http://localhost:9527/health | Server status endpoint |

---

## 🔌 API Integration | API集成

### Authentication | 身份验证

MindGraph supports two authentication methods | MindGraph支持两种认证方式:

**1. API Key (for external services) | API密钥（用于外部服务）**
```http
POST /api/generate_png
Content-Type: application/json
X-API-Key: sk_mindgraph_your_api_key_here

{
  "prompt": "Compare cats and dogs",
  "language": "en"
}
```

**2. JWT Token (for authenticated users) | JWT令牌（用于已认证用户）**
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

### Dify Integration | Dify集成

**HTTP Request Node Configuration:**

```json
{
  "url": "http://your-server:9527/api/generate_png",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "X-API-Key": "sk_mindgraph_your_key_here"
  },
  "body": {
    "prompt": "{{user_input}}",
    "language": "en"
  }
}
```

**Returns:** Binary PNG image ready for display

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
api_key = "sk_mindgraph_abc123xyz456"
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
const apiKey = 'sk_mindgraph_abc123xyz456';
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

## 🐳 Docker Deployment | Docker部署

### Quick Start with Docker | Docker快速开始

```bash
# Build image
docker build -f docker/Dockerfile -t mindgraph:latest .

# Run container
docker run -d -p 9527:9527 \
  -e QWEN_API_KEY=your-api-key \
  -e EXTERNAL_HOST=your-server-ip \
  --name mindgraph \
  mindgraph:latest

# View logs
docker logs -f mindgraph
```

### Docker Compose

```bash
# Copy environment template
cp docker/docker.env.example .env

# Edit .env with your configuration

# Start application
docker-compose -f docker/docker-compose.yml up -d
```

---

## 📚 Documentation

- [**API Reference**](docs/API_REFERENCE.md) - Complete API documentation with bilingual examples
- [**API Key Security**](docs/API_KEY_SECURITY_IMPLEMENTATION.md) - Security implementation guide
- [**Changelog**](CHANGELOG.md) - Version history and updates

---

## 🧪 Testing | 测试

```bash
# Start server | 启动服务器
python run_server.py

# Run tests (in another terminal) | 运行测试（在另一个终端）
cd tests
python test_all_agents.py production
```

**Test Coverage | 测试覆盖:**
- 10 diagram types with diverse topics | 10种图表类型及多样化主题
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

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.  
本项目采用**Apache 2.0许可证** - 详情请参阅[LICENSE](LICENSE)文件。

**Key Points | 要点:**
- ✅ Free for personal, educational, and commercial use | 免费用于个人、教育和商业用途
- ✅ Open source contributions welcome | 欢迎开源贡献
- ✅ Patent grant and protection included | 包含专利授权和保护
- ⚠️ **Trademark NOT included**: MindGraph name and logos are protected | **商标不包括在内**：MindGraph名称和标志受保护

**Trademark Notice | 商标声明:**

The **MindGraph** name, logos, and branding are trademarks of lycosa9527/MindSpring Team and are NOT included in the Apache 2.0 license grant. If you fork or redistribute this software:

**MindGraph** 名称、标志和品牌是lycosa9527/MindSpring团队的商标，不包含在Apache 2.0许可授权中。如果您fork或重新分发此软件：

- ❌ Remove all MindGraph branding and logos | 删除所有MindGraph品牌和标志
- ❌ Use a different name for your project | 为您的项目使用不同的名称
- ✅ Provide attribution to the original project | 对原始项目提供署名

See [NOTICE](NOTICE) file for complete trademark and attribution information.

---

## 💬 Support | 支持

**Questions? Issues? Feedback? | 问题？错误？反馈？**

- 🐛 **Issues | 问题**: [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
- 📧 **Email | 邮件**: Contact via GitHub | 通过GitHub联系
- 📖 **Docs | 文档**: [API Reference | API参考](docs/API_REFERENCE.md)

---

## 🌟 Acknowledgments | 致谢

### Built with ❤️ by lycosa9527 | 由lycosa9527用❤️构建
**Made by MindSpring Team | MindSpring团队出品**

> **Powered by [Cursor AI](https://cursor.sh)** - The AI-first code editor that made this project possible
> 
> **由 [Cursor AI](https://cursor.sh) 驱动** - 让这个项目成为可能的AI优先代码编辑器

*AI-Powered Visual Learning for the Next Generation*  
*下一代AI驱动的可视化学习*

---

### ⭐ Star This Project | 给项目加星

If you find MindGraph useful, please consider giving it a ⭐ on GitHub!  
如果您觉得MindGraph有用，请考虑在GitHub上给它一个⭐！

**This project demonstrates that with AI assistance, anyone can build enterprise software - no coding background required!**  
**这个项目证明了在AI的帮助下，任何人都可以构建企业软件 - 无需编程背景！**
