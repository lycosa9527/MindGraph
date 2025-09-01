# MindGraph

**AI-Powered Diagram Generation Platform** | **AI驱动的图表生成平台**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com/)
[![D3.js](https://img.shields.io/badge/D3.js-7.0+-orange.svg)](https://d3js.org/)
[![License](https://img.shields.io/badge/License-AGPLv3-red.svg)](LICENSE)
[![wakatime](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199.svg)](https://wakatime.com/badge/user/60ba0518-3829-457f-ae10-3eff184d5f69/project/a278db63-dcfb-4dae-b731-330443000199)

Transform natural language into professional diagrams. Supports 10 diagram types including Thinking Maps, Mind Maps, and Concept Maps with intelligent LLM classification and D3.js rendering.

将自然语言转换为专业图表。支持10种图表类型，包括思维导图、思维导图和概念图，具有智能LLM分类和D3.js渲染功能。

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

## Performance | 性能

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
- [Changelog](CHANGELOG.md) - Version history | 版本历史
- [Optimization Checklist](docs/MINDGRAPH_OPTIMIZATION_CHECKLIST.md) - Performance improvements | 性能改进
