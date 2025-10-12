# MindGraph

**Enterprise-Grade AI Diagram Generation Platform** | **企业级AI图表生成平台**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-4.9.1-brightgreen.svg)](CHANGELOG.md)
[![Async Ready](https://img.shields.io/badge/Async-100%25-success.svg)](CHANGELOG.md)
[![Multi-LLM](https://img.shields.io/badge/LLMs-4_Models-blue.svg)](CHANGELOG.md)
[![Bilingual](https://img.shields.io/badge/Languages-EN%20%7C%20中文-orange.svg)](CHANGELOG.md)
[![wakatime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/@lyc9527/projects/tkidgnziyn)

Transform natural language into professional visual diagrams. **API-first platform** for Dify, Coze, and any HTTP POST integration. **Complete interactive suite** for K-12 education with AI-powered learning tools.

将自然语言转换为专业可视化图表。面向Dify、Coze和任何HTTP POST集成的**API优先平台**。面向K-12教育的**完整交互套件**，配备AI驱动的学习工具。

**⚡ Minimum Python Version: 3.8 | Recommended: 3.13+ for 2x faster async performance**

---

## 🎯 Two Integration Modes | 两种集成模式

### 🔌 Mode 1: API Integration | 模式1：API集成

**Perfect for Dify, Coze, and Custom AI Platforms | 完美适配Dify、Coze和定制AI平台**

One-line integration for your AI workflow:

```http
POST /api/generate_png
Content-Type: application/json

{
  "prompt": "Compare online vs offline learning",
  "language": "en"
}

→ Returns professional PNG diagram instantly
```

**Use Cases | 使用场景:**
- ✅ **Dify Workflows**: Add visual diagram generation to your AI workflows | **Dify工作流**: 为AI工作流添加可视化图表生成
- ✅ **Coze Bots**: Return diagrams in chatbot responses | **Coze机器人**: 在聊天机器人响应中返回图表
- ✅ **DingTalk Integration**: Direct markdown image format support | **钉钉集成**: 直接支持markdown图片格式
- ✅ **Custom Platforms**: RESTful API for any HTTP POST integration | **定制平台**: 适用于任何HTTP POST集成的RESTful API

**Why Choose MindGraph API | 为什么选择MindGraph API:**
- 🚀 **Production Ready**: FastAPI async architecture, 4,000+ concurrent connections | **生产就绪**: FastAPI异步架构，4000+并发连接
- 🎨 **10 Diagram Types**: Auto-detect or specify (Thinking Maps, Mind Maps, Concept Maps) | **10种图表类型**: 自动检测或指定
- 🌐 **100% Bilingual**: Perfect Chinese/English support for global audiences | **100%双语**: 完美支持中英文，面向全球受众
- ⚡ **Fast Response**: Average 8.7s end-to-end (LLM + rendering + export) | **快速响应**: 平均8.7秒端到端

[**→ View Complete API Documentation**](docs/API_REFERENCE.md)

---

### 🎨 Mode 2: Complete Interactive Suite | 模式2：完整交互套件

**Professional Web Editor with AI-Powered Tools | 配备AI工具的专业网页编辑器**

Full-featured platform for educators, students, and knowledge workers:

#### **🤖 4-LLM Parallel Auto-Complete | 4-LLM并行自动完成**
Click one button → Get 4 AI perspectives simultaneously | 点击一个按钮 → 同时获得4个AI视角

- **Qwen (通义千问)**: Fast & reliable, default choice | 快速可靠，默认选择
- **DeepSeek-v3.1**: High-quality reasoning & analysis | 高质量推理与分析  
- **Kimi (月之暗面)**: Moonshot AI, creative solutions | 月之暗面AI，创意解决方案
- **Hunyuan (混元)**: Tencent Cloud AI, enterprise-grade | 腾讯云AI，企业级

**Visual Feedback**: Each LLM glows with unique color when ready (Blue, Purple, Orange, Teal) | **视觉反馈**: 每个LLM就绪时发出独特颜色光芒

#### **🧠 Interactive Learning Mode (K-12 Education) | 交互式学习模式（K-12教育）**
AI-powered tutoring system for classroom learning:

- **20% Intelligent Knockout**: System hides nodes for active recall practice | **20%智能隐藏**: 系统隐藏节点进行主动回忆练习
- **Real-time Validation**: AI validates answers with semantic understanding | **实时验证**: AI通过语义理解验证答案
- **Multi-Angle Teaching**: Tests understanding from 4 cognitive perspectives | **多角度教学**: 从4个认知角度测试理解
- **3-Level Escalation**: Progressive teaching when students struggle | **3级升级**: 学生遇到困难时渐进式教学
- **Node Highlighting**: Golden pulse animation highlights current question | **节点高亮**: 金色脉动动画高亮当前问题

#### **✨ Professional Editing Tools | 专业编辑工具**
- **Add/Delete Nodes**: Context-aware operations for all diagram types | **添加/删除节点**: 所有图表类型的上下文感知操作
- **Visual Styling**: Font size, color, style customization | **视觉样式**: 字体大小、颜色、样式自定义
- **Undo/Redo**: Full history management (Ctrl+Z/Ctrl+Y) | **撤销/重做**: 完整历史管理
- **Line Mode**: Toggle black & white for printing | **线稿模式**: 切换黑白用于打印
- **PNG Export**: High-quality export with watermark | **PNG导出**: 高质量导出带水印

[**→ Launch Interactive Editor**](http://localhost:9527/editor) (after installation)

---

## 🎯 Key Features | 核心功能

### Diagram Types | 图表类型
**10 Professional Diagram Types | 10种专业图表类型:**

**Thinking Maps (8 Types) | 八大思维图示:**
1. **Circle Map** - Define topics in context | 定义主题和背景
2. **Bubble Map** - Describe with attributes | 用属性描述
3. **Double Bubble Map** - Compare and contrast | 比较和对比
4. **Tree Map** - Classify hierarchically | 分层分类
5. **Brace Map** - Analyze whole-part relationships | 分析整体-部分关系
6. **Flow Map** - Sequence events and processes | 序列化事件和过程
7. **Multi-Flow Map** - Examine cause and effect | 研究因果关系
8. **Bridge Map** - Show analogies | 展示类比

**Additional Types | 其他类型:**
9. **Mind Map** - Radial brainstorming | 放射状头脑风暴
10. **Concept Map** - Advanced relationship mapping | 高级关系映射

### AI & LLM Features | AI与LLM功能
- **Smart Classification**: Auto-detect diagram type from natural language | **智能分类**: 从自然语言自动检测图表类型
- **4-LLM Comparison**: Parallel generation with Qwen, DeepSeek, Kimi, Hunyuan | **4-LLM比较**: 使用Qwen、DeepSeek、Kimi、Hunyuan并行生成
- **Auto-Complete**: AI expands your diagrams intelligently | **自动完成**: AI智能扩展您的图表
- **Contextual Questions**: LLM generates questions based on diagram structure | **上下文问题**: LLM根据图表结构生成问题

### Educational Features | 教育功能
- **Interactive Learning Mode**: AI tutor with real-time validation | **交互式学习模式**: 带实时验证的AI导师
- **Learning Sheets (半成品)**: 20% content hidden for practice worksheets | **学习半成品**: 隐藏20%内容用于练习工作表
- **Progress Tracking**: Monitor student performance and misconceptions | **进度追踪**: 监控学生表现和误解
- **Multi-Angle Verification**: Test understanding from 4 cognitive perspectives | **多角度验证**: 从4个认知角度测试理解

### Technical Excellence | 技术优势
- **100% Async Architecture**: FastAPI + Uvicorn ASGI | **100%异步架构**
- **Production Ready**: 4,000+ concurrent SSE connections | **生产就绪**: 4000+并发SSE连接
- **Type-Safe**: Pydantic models with full validation | **类型安全**: Pydantic模型完整验证
- **Auto-Generated Docs**: Interactive Swagger UI at `/docs` | **自动生成文档**: 交互式Swagger UI
- **Cross-Platform**: Windows & Ubuntu tested | **跨平台**: Windows和Ubuntu测试通过

---

## 🚀 Quick Start | 快速开始

### Prerequisites | 前置要求

**Minimum Requirements | 最低要求:**
- **Python 3.8 or higher** (Tested: 3.8, 3.9, 3.10, 3.11, 3.12, 3.13) | **Python 3.8或更高版本**
- **Recommended:** Python 3.13+ for best async performance (up to 2x faster) | **推荐**: Python 3.13+以获得最佳异步性能（快达2倍）
- Internet connection for LLM API access | 用于LLM API访问的互联网连接
- Modern web browser (Chrome, Firefox, Safari, Edge) | 现代网页浏览器

### Installation | 安装

   ```bash
# 1. Clone repository
   git clone https://github.com/lycosa9527/MindGraph.git
   cd MindGraph

# 2. Automated setup (installs all dependencies)
   python setup.py

# 3. Configure API key
   cp env.example .env
# Edit .env and add your QWEN_API_KEY
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
   Expected Capacity: 4,000+ concurrent SSE connections

   ✅ Server ready at: http://localhost:9527
   ✅ Interactive Editor: http://localhost:9527/editor
✅ API Documentation: http://localhost:9527/docs
✅ Health Check: http://localhost:9527/health
```

### Access Points | 访问入口

| Service | URL | Description |
|---------|-----|-------------|
| **Interactive Editor** | http://localhost:9527/editor | Full-featured web editor |
| **API Docs (Swagger)** | http://localhost:9527/docs | Auto-generated API documentation |
| **Health Check** | http://localhost:9527/health | Server status endpoint |
| **Landing Page** | http://localhost:9527/ | Welcome page with gallery |

---

## 📚 API Integration Examples | API集成示例

### Dify Workflow Integration | Dify工作流集成

**HTTP Request Node Configuration:**

```json
{
  "url": "http://your-mindgraph-server:9527/api/generate_png",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "prompt": "{{user_input}}",
  "language": "en"
}
}
```

**Response:** Binary PNG image ready for display or download

---

### Coze Bot Integration | Coze机器人集成

**Python SDK Example:**

```python
import requests

def generate_diagram_for_coze(user_message):
    response = requests.post(
        "http://your-server:9527/api/generate_png",
        json={
            "prompt": user_message,
            "language": "en"  # or "zh" for Chinese
        }
    )
    
    # Save PNG or return URL
with open("diagram.png", "wb") as f:
        f.write(response.content)
    
    return "diagram.png"

# In your Coze bot handler:
user_msg = "Compare online vs offline learning"
diagram_file = generate_diagram_for_coze(user_msg)
# Send diagram_file to user
```

---

### DingTalk Integration | 钉钉集成

**Perfect for Classroom Bots | 完美适配课堂机器人:**

```python
import requests

def send_diagram_to_dingtalk(prompt):
    # Generate diagram
    response = requests.post(
        "http://your-server:9527/api/generate_dingtalk",
        json={
            "prompt": prompt,
            "language": "zh"
        }
    )
    
    # Response is plain text: ![](image_url)
    markdown_text = response.text
    
    # Send directly to DingTalk (already in markdown format)
    return markdown_text

# Example usage
result = send_diagram_to_dingtalk("创建鸦片战争的流程图")
# Returns: ![](http://server:9527/api/temp_images/dingtalk_xxx.png)
```

---

### Custom Platform Integration | 定制平台集成

**JavaScript/Node.js Example:**

```javascript
const axios = require('axios');
const fs = require('fs');

async function generateDiagram(prompt, language = 'en') {
    const response = await axios.post(
        'http://localhost:9527/api/generate_png',
        { prompt, language },
        { responseType: 'arraybuffer' }
    );
    
    fs.writeFileSync('diagram.png', response.data);
    return 'diagram.png';
}

// Usage
generateDiagram('Create a mind map about AI')
    .then(file => console.log(`Saved: ${file}`))
    .catch(err => console.error('Error:', err));
```

---

## 🎓 Educational Features | 教育功能

### Interactive Learning Mode | 交互式学习模式

**AI-Powered Tutoring for K-12 Classrooms | K-12课堂AI驱动辅导**

Transform any diagram into an interactive learning experience:

#### How It Works | 工作原理

1. **Create Complete Diagram** | **创建完整图表**
   - Generate with AI or manually create
   - Ensure all nodes have meaningful content
   
2. **Click "Learning" Button** | **点击"学习"按钮**
   - System analyzes diagram structure
   - Intelligently selects 20% of nodes to hide
   - Generates contextual questions for each node
   
3. **Interactive Q&A** | **交互式问答**
   - Student reads question in overlay panel
   - Types answer into blank node on canvas
   - Clicks "Submit" for instant validation
   
4. **AI Tutoring** | **AI辅导**
   - ✅ **Correct**: Progress to next question
   - ❌ **Wrong**: Teaching modal appears with:
     - Golden pulse animation highlighting the node
     - AI-generated explanation of the concept
     - Correct answer display
   - Click "I Understand" → Verification question from different angle
   - Still wrong? System escalates with new teaching strategy (up to 3 times)

5. **Complete Session** | **完成会话**
   - View final score and performance summary
   - All nodes revealed with full content
   - Progress tracking for teacher review

#### Educational Benefits | 教育价值

✅ **Active Recall**: Research-proven technique for memory retention | **主动回忆**: 经研究证明的记忆保持技术  
✅ **Intelligent Tutoring**: AI adapts teaching based on misconceptions | **智能辅导**: AI根据误解调整教学  
✅ **Multi-Angle Learning**: Tests understanding from 4 cognitive perspectives | **多角度学习**: 从4个认知角度测试理解  
✅ **Immediate Feedback**: Real-time validation with contextual explanations | **即时反馈**: 实时验证和上下文解释  
✅ **Visual Learning**: Node highlighting and animations enhance engagement | **视觉学习**: 节点高亮和动画增强参与度  
✅ **Progress Tracking**: Monitor student performance and misconception patterns | **进度追踪**: 监控学生表现和误解模式  

[**→ Try Interactive Learning Demo**](http://localhost:9527/editor?mode=learning)

---

### Learning Sheets (半成品) | 学习半成品

**Static Practice Worksheets for Printing | 用于打印的静态练习工作表**

Generate printable worksheets with 20% content hidden:

```bash
# Via API
POST /api/generate_png
{
        "prompt": "生成鸦片战争的半成品流程图",
        "language": "zh"
    }

# Returns PNG with 20% text hidden for student practice
```

**Perfect for | 完美适用于:**
- Paper-based classroom activities | 纸质课堂活动
- Homework assignments | 家庭作业
- Quiz preparation | 测验准备
- Print-friendly worksheets | 打印友好工作表

---

## 🐳 Docker Deployment | Docker部署

### Quick Docker Setup | 快速Docker设置

```bash
# 1. Build image
docker build -f docker/Dockerfile -t mindgraph:latest .

# 2. Run container
docker run -d -p 9527:9527 \
  -e QWEN_API_KEY=your-api-key \
  -e EXTERNAL_HOST=your-server-ip \
  --name mindgraph-app \
  mindgraph:latest

# 3. View logs
docker logs -f mindgraph-app
```

### Docker Compose | Docker Compose部署

```bash
# 1. Copy environment template
cp docker/docker.env.example .env

# 2. Edit .env with your configuration
# - QWEN_API_KEY=your-key
# - EXTERNAL_HOST=your-server-ip

# 3. Start application
docker-compose -f docker/docker-compose.yml up -d
```

**Docker Features | Docker特性:**
- ✅ **Optimized**: 2.93GB multi-stage build | **优化镜像**: 2.93GB多阶段构建
- ✅ **Production Ready**: Health checks, non-root user | **生产就绪**: 健康检查、非root用户
- ✅ **Complete Setup**: All dependencies included | **完整设置**: 包含所有依赖

---

## 📊 Performance | 性能指标

**Benchmark Results (Production Simulation) | 基准测试结果（生产模拟）:**

| Metric | Value | Notes |
|--------|-------|-------|
| **Average Response Time** | 8.7s | End-to-end (LLM + rendering + export) |
| **LLM Processing** | 5.94s (69%) | Main bottleneck |
| **Browser Rendering** | 2.7s (31%) | Playwright PNG export |
| **Concurrent Users** | 6 simultaneous | Tested with real workloads |
| **Success Rate** | 97.8% | 44/45 requests successful |
| **Thread Safety** | ✅ Validated | 45 unique threads, isolated instances |

**Performance Breakdown | 性能分解:**
- Classification: ~1.5s (qwen-turbo) | 分类
- Generation: ~3-5s (qwen-plus) | 生成
- Rendering: ~0.1-0.2s (D3.js) | 渲染
- PNG Export: ~1-2s (Playwright) | PNG导出

---

## 🧪 Testing | 测试

**Comprehensive Test Suite | 全面测试套件:**

   ```bash
# Start server first
   python run_server.py

# Run production simulation
   cd test
   python test_all_agents.py production
   ```

**Test Modes | 测试模式:**
- **Sequential**: Test all 10 diagram types individually | **顺序**: 单独测试所有10种图表类型
- **Concurrent**: 3 rounds × 4 concurrent (12 total) | **并发**: 3轮 × 4并发（总共12个）
- **Production**: 5 rounds × 9 diagrams (45 total) | **生产**: 5轮 × 9图表（总共45个）

**Test Results | 测试结果:**
- Real PNG generation for visual validation | 真实PNG生成用于视觉验证
- Threading analysis and safety validation | 线程分析和安全验证
- Performance metrics and timing breakdowns | 性能指标和时序分解
- 50+ diverse topics for realistic testing | 50+个多样化主题进行真实测试

---

## 📖 Documentation | 文档

- [**API Reference**](docs/API_REFERENCE.md) - Complete API documentation with examples | 完整API文档及示例
- [**Changelog**](CHANGELOG.md) - Version history and updates | 版本历史和更新
- [**Optimization Guide**](docs/MINDGRAPH_OPTIMIZATION_CHECKLIST.md) - Performance improvements | 性能改进指南
- [**Testing Guide**](test/test_all_agents.py) - Comprehensive testing framework | 全面测试框架

---

## 🤝 Contributing | 贡献

We welcome contributions! Here's how:

1. Fork the repository | Fork仓库
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License | 许可证

This project is licensed under the **AGPLv3 License** - see the [LICENSE](LICENSE) file for details.

本项目采用**AGPLv3许可证** - 详情请参阅[LICENSE](LICENSE)文件。

**Key Points | 要点:**
- ✅ Free for personal and educational use | 免费用于个人和教育用途
- ✅ Open source contributions welcome | 欢迎开源贡献
- ⚠️ Commercial use requires compliance with AGPLv3 | 商业用途需遵守AGPLv3

---

## 💬 Support & Community | 支持与社区

**Questions? Issues? Feedback?**

- 📧 **Email**: lycosa9527@example.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/lycosa9527/MindGraph/issues)
- 📖 **Wiki**: [Documentation Wiki](https://github.com/lycosa9527/MindGraph/wiki)

---

## 🌟 Star History | 星标历史

If you find MindGraph useful, please consider giving it a ⭐ on GitHub!

如果您觉得MindGraph有用，请考虑在GitHub上给它一个⭐！

---

**Built with ❤️ by lycosa9527 | Made by MindSpring Team**

*AI-Powered Visual Learning for the Next Generation*

*下一代AI驱动的可视化学习*

