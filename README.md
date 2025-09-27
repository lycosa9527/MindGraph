# MindGraph

**AI-Powered Diagram Generation Platform** | **AI驱动的图表生成平台**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.6.0-brightgreen.svg)](CHANGELOG.md)
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

- **Smart Classification**: LLM-based diagram type detection | **智能分类**: 基于LLM的图表类型检测
- **10 Diagram Types**: Complete Thinking Maps coverage plus Mind Maps and Concept Maps | **10种图表类型**: 完整的思维导图覆盖，包括思维导图和概念图
- **Multi-language**: English and Chinese support | **多语言**: 支持英文和中文
- **API-First**: RESTful endpoints for integrations | **API优先**: 用于集成的RESTful端点
- **Export Options**: PNG, SVG, and interactive HTML | **导出选项**: PNG、SVG和交互式HTML
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
   - Web UI: `http://localhost:9527/debug` | 网页界面
   - API: `http://localhost:9527/api/generate_png` | API接口

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
6. **Multi-Flow Map** - Complex multi-process flows | **多流程图** - 复杂的多过程流程
7. **Bridge Map** - Analogies and relationships | **桥形图** - 类比和关系
8. **Tree Map** - Hierarchical data visualization | **树形图** - 分层数据可视化

### Additional Types | 其他类型
9. **Mind Map** - Clockwise branch positioning | **思维导图** - 顺时针分支定位
10. **Concept Map** - Advanced relationship mapping | **概念图** - 高级关系映射

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

- [API Reference](docs/API_REFERENCE.md) - Complete API documentation | 完整API文档
- [Changelog](CHANGELOG.md) - Version history and comprehensive code review | 版本历史和全面代码审查
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
