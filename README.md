# MindGraph

**AI-Powered Diagram Generation Platform** | **AI驱动的图表生成平台**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-3.0.14-brightgreen.svg)](CHANGELOG.md)
[![Production Ready](https://img.shields.io/badge/Production-Ready-success.svg)](CHANGELOG.md)
[![wakatime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/@lyc9527/projects/tkidgnziyn)

Transform natural language into professional diagrams. Supports 10 diagram types including Thinking Maps, Mind Maps, and Concept Maps with intelligent LLM classification and D3.js rendering.

将自然语言转换为专业图表。支持10种图表类型，包括思维导图、思维导图和概念图，具有智能LLM分类和D3.js渲染功能。

## 🎯 **Production Ready** | **生产就绪**

✅ **Comprehensive Code Review Completed** - Validated as production-ready with excellent architecture  
✅ **Thread-Safe Concurrent Processing** - Supports 6 simultaneous users with proper isolation  
✅ **Comprehensive Testing Suite** - Production simulation with 45 diverse test cases  
✅ **Professional Code Quality** - Clean, maintainable, and well-documented codebase  
✅ **Security Validated** - Comprehensive input validation and error handling  

✅ **全面代码审查完成** - 验证为生产就绪，架构优秀  
✅ **线程安全并发处理** - 支持6个并发用户，适当隔离  
✅ **全面测试套件** - 45个多样化测试用例的生产模拟  
✅ **专业代码质量** - 清洁、可维护、文档完善的代码库  
✅ **安全验证** - 全面的输入验证和错误处理

## Features | 功能特性

### 🎨 Interactive Editor | 交互式编辑器
Professional web-based diagram editor with comprehensive bilingual support | 专业的网页图表编辑器，全面支持双语

- **Full Bilingual Interface** | **完整双语界面**
  - Seamless Chinese/English language switching | 中英文无缝切换
  - All UI elements translated (buttons, tooltips, notifications) | 所有UI元素已翻译（按钮、工具提示、通知）
  - Dynamic node creation in current language | 当前语言动态节点创建
  - 60+ notification messages fully localized | 60+条通知消息完全本地化

- **Rich Editing Tools** | **丰富的编辑工具**
  - **Add/Delete Nodes**: Context-aware node operations for all diagram types | **添加/删除节点**: 所有图表类型的上下文感知节点操作
  - **Text Editing**: Double-click inline editing with properties panel | **文本编辑**: 双击内联编辑，带属性面板
  - **Visual Styling**: Font size, color, style customization | **视觉样式**: 字体大小、颜色、样式自定化
  - **Line Mode**: Toggle black & white line-art mode for printing | **线稿模式**: 切换黑白线条模式用于打印
  - **Undo/Redo**: Full history management with state restoration (Ctrl+Z/Ctrl+Y) | **撤销/重做**: 完整历史记录管理与状态恢复（Ctrl+Z/Ctrl+Y）
  - **Node Counter**: Real-time node count display for all diagram types | **节点计数**: 所有图表类型的实时节点计数显示

- **AI-Powered Features** | **AI功能**
  - **Auto-Complete**: AI intelligently expands diagrams based on existing content | **自动完成**: AI根据现有内容智能扩展图表
  - **MindMate AI Assistant**: Integrated Dify-powered AI helper in side panel | **MindMate AI助手**: 集成Dify驱动的AI助手在侧边栏
  - **Smart Prompt Processing**: Natural language to diagram generation | **智能提示处理**: 自然语言转图表生成

- **Export & Share** | **导出与分享**
  - **PNG Export**: High-quality image export with watermark | **PNG导出**: 高质量图像导出，带水印
  - **Share URL**: One-click URL sharing with QR code | **分享URL**: 一键URL分享，带二维码
  - **Canvas Reset**: Quick reset to blank template | **画布重置**: 快速重置为空白模板

- **Professional UI** | **专业界面**
  - Gallery view with 10 diagram templates | 画廊视图，10种图表模板
  - AI prompt input with history | AI提示输入，带历史记录
  - Properties panel for fine-tuned styling | 属性面板用于精细样式调整
  - Real-time diagram rendering with D3.js | D3.js实时图表渲染

### 🚀 Core Features | 核心功能

- **Smart Classification**: LLM-based diagram type detection | **智能分类**: 基于LLM的图表类型检测
- **10 Diagram Types**: Complete Thinking Maps coverage plus Mind Maps and Concept Maps | **10种图表类型**: 完整的思维导图覆盖，包括思维导图和概念图
- **Learning Sheets (半成品)**: Educational mode with 20% content hidden for student practice | **学习半成品**: 教育模式，隐藏20%内容供学生练习
- **API-First**: RESTful endpoints for integrations | **API优先**: 用于集成的RESTful端点
- **Production Ready**: Thread-safe, enterprise-grade architecture | **生产就绪**: 线程安全的企业级架构

## Quick Start | 快速开始

### Prerequisites | 前置要求
- Python 3.8+
- Modern web browser | 现代网页浏览器
- Internet connection for LLM API access | 用于LLM API访问的互联网连接

### Installation | 安装

1. **Clone and Setup | 克隆和设置**
   ```bash
   git clone https://github.com/lycosa9527/MindGraph.git
   cd MindGraph
   python setup.py
   ```

2. **Configure Environment | 配置环境**
   ```bash
   cp env.example .env
   # Edit .env with your QWEN_API_KEY
   # 编辑.env文件，添加你的QWEN_API_KEY
   ```

3. **Run Server | 运行服务器**
   ```bash
   python run_server.py  # Production server | 生产服务器
   # OR
   python app.py         # Development server | 开发服务器
   ```

4. **Access Interface | 访问界面**
   - **Interactive Editor**: `http://localhost:9527/editor` | **交互式编辑器**
   - Web UI: `http://localhost:9527/debug` | 网页界面
   - API: `http://localhost:9527/api/generate_png` | API接口

## 📝 Using the Interactive Editor | 使用交互式编辑器

### Getting Started | 快速入门

1. **Navigate to Editor** | **进入编辑器**
   ```
   http://localhost:9527/editor
   ```

2. **Choose Your Workflow** | **选择工作流程**
   
   **Option A: AI-Generated Diagrams | 选项A: AI生成图表**
   - Enter a natural language prompt in the input box | 在输入框中输入自然语言提示
   - Examples: "Compare online vs offline learning" | 示例："比较线上与线下学习"
   - AI generates complete diagram automatically | AI自动生成完整图表
   
   **Option B: Manual Creation | 选项B: 手动创建**
   - Select a diagram type from the gallery (10 types available) | 从画廊选择图表类型（10种可用）
   - Click to start with a blank template | 点击开始空白模板
   - Build your diagram node by node | 逐个节点构建图表

3. **Edit Your Diagram** | **编辑图表**
   - **Double-click** any node to edit text | **双击**任意节点编辑文本
   - **Click** Add button (or select node + Add) to add nodes | **点击**添加按钮（或选择节点+添加）添加节点
   - **Select** nodes to delete, style, or modify | **选择**节点以删除、样式化或修改
   - Use **Properties Panel** for fine-grained styling | 使用**属性面板**进行精细样式调整

4. **AI Enhancement** | **AI增强**
   - Click **Auto** button to let AI expand your diagram | 点击**自动**按钮让AI扩展你的图表
   - AI analyzes existing content and adds relevant nodes | AI分析现有内容并添加相关节点
   - Works with all diagram types | 适用于所有图表类型

5. **Export & Share** | **导出与分享**
   - Click **Export** to save as PNG image | 点击**导出**保存为PNG图像
   - Click **Share** to get shareable URL with QR code | 点击**分享**获取可分享URL及二维码
   - Toggle **Line Mode** for black & white printing | 切换**线稿模式**用于黑白打印

### Language Switching | 语言切换

- Click the language toggle button (EN/中文) in top right | 点击右上角语言切换按钮（EN/中文）
- **Entire interface switches instantly** | **整个界面立即切换**
- All buttons, tooltips, and notifications change language | 所有按钮、工具提示和通知都会改变语言
- New nodes created in selected language | 新节点以选定语言创建

### Keyboard Shortcuts | 键盘快捷键

- `Ctrl/Cmd + Z` - Undo (restores previous state) | 撤销（恢复之前的状态）
- `Ctrl/Cmd + Y` - Redo (restores undone action) | 重做（恢复撤销的操作）
- `Delete` - Delete selected node(s) | 删除选定节点
- `Double-click` - Edit node text | 编辑节点文本
- `Esc` - Close panels/modals | 关闭面板/模态框

### Editor Features by Diagram Type | 各图表类型编辑功能

Each diagram type has specialized node operations: | 每种图表类型都有专门的节点操作：

- **Circle Map** (圆圈图): Add context nodes around central topic | 在中心主题周围添加背景节点
- **Bubble Map** (气泡图): Add attribute bubbles to describe subject | 添加属性气泡描述主题
- **Double Bubble Map** (双气泡图): Add similarities and differences | 添加相似点和差异
- **Tree Map** (树形图): Add categories and hierarchical items | 添加类别和层次项目
- **Brace Map** (括号图): Add parts and subparts in whole-part structure | 在整体-部分结构中添加部分和子部分
- **Flow Map** (流程图): Add sequential steps and substeps | 添加顺序步骤和子步骤
- **Multi-Flow Map** (复流程图): Add causes and effects to events | 为事件添加原因和结果
- **Bridge Map** (桥形图): Add analogical pairs | 添加类比对
- **Mind Map** (思维导图): Add branches and sub-branches | 添加分支和子分支
- **Concept Map** (概念图): Add concepts and relationships | 添加概念和关系

## Docker Deployment | Docker部署

### Quick Docker Setup | 快速Docker设置

1. **Build Docker Image | 构建Docker镜像**
   ```bash
   # From project root | 从项目根目录
   docker build -f docker/Dockerfile -t mindgraph:latest .
   ```

2. **Run with Docker Compose | 使用Docker Compose运行**
   ```bash
   # Copy environment template | 复制环境模板
   cp docker/docker.env.example .env
   
   # Edit .env with your values | 编辑.env文件
   # - QWEN_API_KEY=your-api-key
   # - EXTERNAL_HOST=your-server-ip
   
   # Start the application | 启动应用
   docker-compose -f docker/docker-compose.yml up -d
   ```

3. **Access the Application | 访问应用**
   - **Interactive Editor**: `http://localhost:9527/editor` | **交互式编辑器**
   - Web UI: `http://localhost:9527/debug` | 网页界面
   - API: `http://localhost:9527/api/generate_png` | API接口

### Docker Features | Docker特性

- **✅ Optimized Image**: 2.93GB multi-stage build with Playwright pre-installed | **优化镜像**: 2.93GB多阶段构建，预装Playwright
- **✅ Production Ready**: Health checks, non-root user, comprehensive logging | **生产就绪**: 健康检查、非root用户、全面日志
- **✅ Easy Configuration**: Environment variables with sensible defaults | **简单配置**: 环境变量，合理默认值
- **✅ Complete Setup**: All dependencies included, no runtime downloads | **完整设置**: 包含所有依赖，无需运行时下载

### Docker Commands | Docker命令

```bash
# Build image | 构建镜像
docker build -f docker/Dockerfile -t mindgraph:latest .

# Run container | 运行容器
docker run -d -p 9527:9527 \
  -e QWEN_API_KEY=your-api-key \
  -e EXTERNAL_HOST=localhost \
  mindgraph:latest

# View logs | 查看日志
docker logs -f mindgraph-app

# Stop container | 停止容器
docker stop mindgraph-app
```

## API Reference | API参考

### Core Endpoints | 核心端点

#### Generate PNG Image | 生成PNG图片
```http
POST /api/generate_png
Content-Type: application/json

{
  "prompt": "Create a mind map about artificial intelligence",
  "language": "en"
}
```

#### Generate Interactive Diagram | 生成交互式图表
```http
POST /api/generate_graph
Content-Type: application/json

{
  "prompt": "Compare traditional education vs online learning",
  "language": "en"
}
```

#### DingTalk Integration | 钉钉集成
```http
POST /api/generate_dingtalk
Content-Type: application/json

{
  "prompt": "Show the workflow of software development",
  "language": "zh"
}
```

**Response | 响应:**
```json
{
  "success": true,
  "markdown": "![Software Development Workflow](http://localhost:9527/api/temp_images/dingtalk_abc123_1692812345.png)",
  "image_url": "http://localhost:9527/api/temp_images/dingtalk_abc123_1692812345.png",
  "graph_type": "flow_map",
  "timing": {
    "total_time": 3.42
  }
}
```

## Integration Examples | 集成示例

### Python Integration | Python集成

```python
import requests

def generate_png(prompt, language="en"):
    response = requests.post(
        "http://localhost:9527/api/generate_png",
        json={"prompt": prompt, "language": language}
    )
    return response.content  # PNG binary data

# Example usage | 使用示例
png_data = generate_png("Create a mind map about machine learning")
with open("diagram.png", "wb") as f:
    f.write(png_data)
```

### DingTalk Bot Integration | 钉钉机器人集成

```python
import requests

def generate_dingtalk_diagram(prompt, language="zh"):
    response = requests.post(
        "http://your-mindgraph-server:9527/api/generate_dingtalk",
        json={"prompt": prompt, "language": language}
    )
    return response.json()

# Example usage | 使用示例
result = generate_dingtalk_diagram("Create a flow map about project management")
if result["success"]:
    markdown = result["markdown"]
    image_url = result["image_url"]
    # Send markdown to DingTalk chat | 发送markdown到钉钉聊天
```

## Supported Diagram Types | 支持的图表类型

### Thinking Maps | 思维导图
1. **Bubble Map** - Define concepts and characteristics | **气泡图** - 定义概念和特征
2. **Circle Map** - Brainstorming and context definition | **圆圈图** - 头脑风暴和上下文定义
3. **Double Bubble Map** - Compare and contrast concepts | **双气泡图** - 比较和对比概念
4. **Brace Map** - Part-whole relationships | **括号图** - 部分-整体关系
5. **Flow Map** - Processes and sequences | **流程图** - 过程和序列
6. **Multi-Flow Map** - Complex multi-process flows | **复流程图** - 复杂的多过程流程
7. **Bridge Map** - Analogies and relationships | **桥形图** - 类比和关系
8. **Tree Map** - Hierarchical data visualization | **树形图** - 分层数据可视化

### Additional Types | 其他类型
9. **Mind Map** - Clockwise branch positioning | **思维导图** - 顺时针分支定位
10. **Concept Map** - Advanced relationship mapping | **概念图** - 高级关系映射

## Learning Sheets (半成品功能) | 学习半成品

### Educational Feature for K-12 Teachers | K-12教师教育功能

MindGraph supports **Learning Sheets (半成品)** - a special mode designed for classroom learning where the system automatically generates practice diagrams with 20% of content hidden.

MindGraph支持**学习半成品功能** - 专为课堂学习设计的特殊模式，系统自动生成隐藏20%内容的练习图表。

### How It Works | 工作原理

1. **Add "半成品" to Your Prompt** | **在提示中添加"半成品"**
   ```
   "生成鸦片战争的半成品流程图"
   "创建关于光合作用的半成品思维导图"
   "制作中国历史朝代的半成品树形图"
   ```

2. **System Generates Complete Content** | **系统生成完整内容**
   - LLM creates full diagram with all information
   - LLM创建包含所有信息的完整图表

3. **20% Text Randomly Hidden** | **随机隐藏20%文本**
   - System randomly removes text from 20% of nodes
   - Students fill in missing content for practice
   - 系统随机删除20%节点的文本
   - 学生填写缺失内容进行练习

### Usage Examples | 使用示例

#### API Request | API请求
```python
import requests

# Generate a learning sheet flow map
response = requests.post(
    "http://localhost:9527/api/generate_png",
    json={
        "prompt": "生成鸦片战争的半成品流程图",
        "language": "zh"
    }
)

# Returns PNG with 20% of text hidden for student practice
# 返回隐藏20%文本的PNG供学生练习
```

#### DingTalk Integration | 钉钉集成
```python
# Generate learning sheet for DingTalk classroom
result = requests.post(
    "http://localhost:9527/api/generate_dingtalk",
    json={
        "prompt": "创建关于光合作用的半成品思维导图",
        "language": "zh"
    }
).json()

# Result includes image URL with hidden content
# 结果包含隐藏内容的图片URL
print(result["image_url"])
```

### Educational Benefits | 教育价值

✅ **Active Learning**: Students engage by filling in missing information | **主动学习**: 学生通过填写缺失信息参与学习  
✅ **Practice Mode**: Teachers create practice materials instantly | **练习模式**: 教师即时创建练习材料  
✅ **All Diagram Types**: Works with Flow Maps, Mind Maps, Concept Maps, etc. | **所有图表类型**: 适用于流程图、思维导图、概念图等  
✅ **Automatic**: No manual editing required | **自动化**: 无需手动编辑  
✅ **Customizable**: 20% default, configurable for different difficulty levels | **可定制**: 默认20%，可配置不同难度级别

### Supported Prompts | 支持的提示词

- "生成[主题]的半成品[图表类型]" - Generate learning sheet for any topic
- "创建[主题]的半成品图" - Create learning sheet diagram
- "制作[主题]的半成品导图" - Make learning sheet mind map

### Technical Details | 技术细节

- **Detection**: Automatic keyword detection in prompt | **检测**: 提示中的自动关键词检测
- **Cleaning**: Removes keywords before LLM processing | **清理**: LLM处理前删除关键词
- **Rendering**: Random text knockout in final SVG | **渲染**: 最终SVG中随机删除文本
- **Metadata**: Learning sheet flags preserved throughout pipeline | **元数据**: 学习半成品标志在整个流程中保留

## Testing | 测试

### Comprehensive Test Suite | 全面测试套件

MindGraph includes a comprehensive testing framework that validates all diagram types and simulates production workloads.

MindGraph包含一个全面的测试框架，验证所有图表类型并模拟生产工作负载。

#### Test Modes | 测试模式

**Sequential Testing | 顺序测试**
```bash
python test/test_all_agents.py
# Tests all 10 diagram types individually
# 单独测试所有10种图表类型
```

**Concurrent Testing | 并发测试**
```bash
python test/test_all_agents.py concurrent
# Tests 3 rounds × 4 concurrent requests (12 total)
# 测试3轮 × 4个并发请求（总共12个）
```

**Production Simulation | 生产模拟**
```bash
python test/test_all_agents.py production
# Tests 5 rounds × 9 diagrams (45 total requests)
# 测试5轮 × 9种图表（总共45个请求）
```

#### Test Features | 测试功能

- **Real PNG Generation**: Generates actual PNG images for visual validation | **真实PNG生成**: 生成实际PNG图像进行视觉验证
- **Threading Analysis**: Validates multi-threading functionality | **线程分析**: 验证多线程功能
- **Performance Metrics**: Detailed timing breakdowns and statistics | **性能指标**: 详细的时序分解和统计
- **Diverse Topics**: 50+ diverse topics for realistic testing | **多样化主题**: 50+个多样化主题进行真实测试
- **Success Rate Tracking**: Monitors success rates and error patterns | **成功率跟踪**: 监控成功率和错误模式

#### Test Results | 测试结果

**Production Simulation Results | 生产模拟结果:**
- **Success Rate**: 97.8% (44/45 requests successful) | **成功率**: 97.8%（45个请求中44个成功）
- **Threading**: 45 unique threads used (true multi-threading) | **线程**: 使用45个唯一线程（真正的多线程）
- **Average Time**: 9.88s per request | **平均时间**: 每个请求9.88秒
- **Concurrent Users**: 6 simultaneous requests supported | **并发用户**: 支持6个并发请求

#### Running Tests | 运行测试

1. **Start the Server | 启动服务器**
   ```bash
   python run_server.py
   ```

2. **Run Tests | 运行测试**
   ```bash
   cd test
   python test_all_agents.py production
   ```

3. **View Results | 查看结果**
   - Test images saved to `test/images/` | 测试图像保存到`test/images/`
   - Detailed performance analysis in console | 控制台中的详细性能分析
   - Threading verification and statistics | 线程验证和统计

## Performance | 性能

- **Total Request Time**: 8.7s average | **总请求时间**: 平均8.7秒
- **LLM Processing**: 5.94s (69% of total time) | **LLM处理**: 5.94秒（占总时间的69%）
- **Browser Rendering**: 2.7s (31% of total time) | **浏览器渲染**: 2.7秒（占总时间的31%）
- **Concurrent Users**: 6 simultaneous requests | **并发用户**: 6个并发请求
- **Classification**: ~1.5s (qwen-turbo) | **分类**: ~1.5秒 (qwen-turbo)
- **Generation**: ~3-5s (qwen-plus) | **生成**: ~3-5秒 (qwen-plus)
- **Rendering**: ~0.1-0.2s (D3.js) | **渲染**: ~0.1-0.2秒 (D3.js)
- **PNG Export**: ~1-2s (Playwright) | **PNG导出**: ~1-2秒 (Playwright)

## Deployment | 部署

### Production Server | 生产服务器
```bash
python run_server.py  # Waitress WSGI server | Waitress WSGI服务器
```

### Environment Variables | 环境变量
```bash
QWEN_API_KEY=your_api_key_here  # Required | 必需
PORT=9527                        # Optional | 可选
DEBUG=false                      # Optional | 可选
```

## Troubleshooting | 故障排除

### Common Issues | 常见问题

**API Key Configuration | API密钥配置**
```bash
# Check .env file | 检查.env文件
cat .env | grep QWEN_API_KEY
```

**Font Rendering | 字体渲染**
- Fonts are embedded as base64 data URIs | 字体以base64数据URI嵌入
- No additional font installation required | 无需额外安装字体

## Contributing | 贡献

1. Fork the repository | Fork仓库
2. Create a feature branch | 创建功能分支
3. Make your changes with tests | 进行更改并添加测试
4. Submit a pull request | 提交拉取请求

## License | 许可证

This project is licensed under the AGPLv3 License - see the [LICENSE](LICENSE) file for details.

本项目采用AGPLv3许可证 - 详情请参阅[LICENSE](LICENSE)文件。

## Documentation | 文档

- [Interactive Editor Guide](docs/INTERACTIVE_EDITOR.md) - Complete editor usage guide | 完整编辑器使用指南
- [API Reference](docs/API_REFERENCE.md) - Complete API documentation | 完整API文档
- [Changelog](CHANGELOG.md) - Version history and updates | 版本历史和更新
- [Optimization Checklist](docs/MINDGRAPH_OPTIMIZATION_CHECKLIST.md) - Performance improvements and architecture analysis | 性能改进和架构分析
- [Test Documentation](test/test_all_agents.py) - Comprehensive testing framework | 全面测试框架

## Code Review & Architecture | 代码审查和架构

### Production Readiness Assessment | 生产就绪评估

**Overall Rating**: ⭐⭐⭐⭐⭐ **Excellent** | **总体评级**: ⭐⭐⭐⭐⭐ **优秀**

| Category | Rating | Status |
|----------|--------|--------|
| **Architecture** | ⭐⭐⭐⭐⭐ | Excellent - Well-structured, modular, thread-safe |
| **Code Quality** | ⭐⭐⭐⭐ | Very Good - Clean, maintainable, professional |
| **Security** | ⭐⭐⭐⭐ | Good - Comprehensive validation and error handling |
| **Performance** | ⭐⭐⭐⭐ | Good - Optimized with clear bottleneck identification |
| **Testing** | ⭐⭐⭐⭐⭐ | Excellent - Comprehensive coverage with production simulation |

### Key Findings | 关键发现

- **Production Ready**: Application validated for production deployment | **生产就绪**: 应用程序已验证可用于生产部署
- **Thread-Safe**: Proper concurrent request handling with isolated browser instances | **线程安全**: 适当的并发请求处理，浏览器实例隔离
- **Comprehensive Testing**: 45 diverse test cases with production simulation | **全面测试**: 45个多样化测试用例，包含生产模拟
- **Performance Optimized**: Clear bottleneck identification (LLM processing: 69% of total time) | **性能优化**: 明确的瓶颈识别（LLM处理：占总时间的69%）
- **Security Validated**: Comprehensive input validation and XSS protection | **安全验证**: 全面的输入验证和XSS保护
