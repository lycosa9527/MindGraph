# Installation Guide - Version 2.1.0

**D3.js_Dify** - AI-Powered Graph Generation Application

Complete installation guide for D3.js_Dify version 2.1.0 with enhanced dependency validation and professional startup sequences.

## 📋 Prerequisites

### **System Requirements**

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Python** | 3.8+ | 3.11+ |
| **Node.js** | 18.19+ | 20+ |
| **RAM** | 4GB | 8GB+ |
| **Storage** | 2GB | 5GB+ |
| **OS** | Windows 10+, macOS 10.15+, Ubuntu 18.04+ | Latest LTS |

### **Required API Keys**

- **Qwen API Key** (required for core functionality)
  - Get from: [Alibaba Cloud DashScope](https://dashscope.aliyun.com/)
  - Required for AI-powered graph generation

- **DeepSeek API Key** (optional for enhanced features)
  - Get from: [DeepSeek AI](https://platform.deepseek.com/)
  - Provides enhanced AI capabilities

## 🚀 Installation Methods

### **Method 1: Local Installation (Recommended for Development)**

#### **Step 1: Clone the Repository**

```bash
git clone https://github.com/lycosa9527/D3.js_Dify.git
cd D3.js_Dify
```

#### **Step 2: Install Python Dependencies**

```bash
# Install all required packages
pip install -r requirements.txt

# Verify installation
python -c "import flask, requests, langchain, yaml, dotenv, nest_asyncio, pyee, playwright, PIL; print('✅ All dependencies installed successfully')"
```

#### **Step 3: Install Node.js Dependencies**

```bash
# Navigate to D3.js directory
cd d3.js

# Install Node.js dependencies
npm install

# Return to project root
cd ..
```

#### **Step 4: Install Playwright Browser**

```bash
# Install Playwright browsers (handled automatically in v2.1.0)
python -m playwright install chromium
```

#### **Step 5: Configure Environment Variables**

```bash
# Copy example environment file
cp env.example .env

# Edit the .env file with your API keys
nano .env  # or use your preferred editor
```

**Required `.env` configuration:**
```bash
# Required for core functionality
QWEN_API_KEY=your_qwen_api_key_here

# Optional for enhanced features
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Application settings
HOST=0.0.0.0
PORT=9527
DEBUG=False
GRAPH_LANGUAGE=zh
```

#### **Step 6: Run the Application**

```bash
python app.py
```

**Expected output:**
```
🔍 Validating dependencies and configuration...
✅ All dependencies and configuration validated successfully
🚀 Starting D3.js_Dify application...
📋 Configuration Summary:
   Flask: 0.0.0.0:9527 (Debug: False)
   Qwen: qwen-turbo at https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
   DeepSeek: deepseek-chat (❌ Not Available)
   Language: zh
   Theme: #4e79a7 / #a7c7e7 / #f4f6fb
   Dimensions: 700x500px

================================================================================
    ███╗   ███╗██╗███╗   ██╗██████╗ ███╗   ███╗ █████╗ ████████╗███████╗
    ████╗ ████║██║████╗  ██║██╔══██╗████╗ ████║██╔══██╗╚══██╔══╝██╔════╝
    ██╔████╔██║██║██╔██╗ ██║██║  ██║██╔████╔██║███████║   ██║   █████╗  
    ██║╚██╔╝██║██║██║╚██╗██║██║  ██║██║╚██╔╝██║██╔══██║   ██║   ██╔══╝  
    ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝██║ ╚═╝ ██║██║  ██║   ██║   ███████╗
    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
================================================================================

🌐 Application URLs:
   Local: http://localhost:9527
   Network: http://192.168.0.94:9527

🌐 Open in browser: http://localhost:9527

🌐 Starting Flask development server...
```

### **Method 2: Docker Installation (Recommended for Production)**

#### **Step 1: Install Docker**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

**macOS:**
```bash
# Install Docker Desktop
brew install --cask docker
```

**Windows:**
- Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop)

#### **Step 2: Clone and Configure**

```bash
git clone https://github.com/lycosa9527/D3.js_Dify.git
cd D3.js_Dify
cp env.example .env
```

#### **Step 3: Configure Environment Variables**

Edit the `.env` file:
```bash
# Required for core functionality
QWEN_API_KEY=your_qwen_api_key_here

# Optional for enhanced features
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Application settings
HOST=0.0.0.0
PORT=9527
DEBUG=False
GRAPH_LANGUAGE=zh
```

#### **Step 4: Run with Docker Compose**

```bash
cd docker
docker-compose up -d
```

#### **Step 5: Verify Installation**

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f

# Test the application
curl http://localhost:9527/status
```

### **Method 3: Virtual Environment Installation**

#### **Step 1: Create Virtual Environment**

```bash
# Create virtual environment
python -m venv d3js_env

# Activate virtual environment
# On Windows:
d3js_env\Scripts\activate
# On macOS/Linux:
source d3js_env/bin/activate
```

#### **Step 2: Install Dependencies**

```bash
# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### **Step 3: Configure and Run**

```bash
# Copy environment file
cp env.example .env

# Edit configuration
nano .env

# Run application
python app.py
```

## 🔧 Configuration Options

### **Environment Variables Reference**

#### **Required Variables**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `QWEN_API_KEY` | Qwen API key for core functionality | None | ✅ Yes |
| `QWEN_API_URL` | Qwen API endpoint | DashScope URL | No |
| `QWEN_MODEL` | Qwen model name | qwen-turbo | No |
| `QWEN_TEMPERATURE` | Model creativity (0.0-1.0) | 0.7 | No |
| `QWEN_MAX_TOKENS` | Maximum response tokens | 1000 | No |
| `QWEN_TIMEOUT` | API timeout in seconds | 40 | No |

#### **Optional Variables**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API key for enhanced features | None | No |
| `DEEPSEEK_API_URL` | DeepSeek API endpoint | DeepSeek URL | No |
| `DEEPSEEK_MODEL` | DeepSeek model name | deepseek-chat | No |
| `DEEPSEEK_TEMPERATURE` | Model creativity (0.0-1.0) | 0.7 | No |
| `DEEPSEEK_MAX_TOKENS` | Maximum response tokens | 2000 | No |
| `DEEPSEEK_TIMEOUT` | API timeout in seconds | 60 | No |

#### **Application Settings**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `HOST` | Flask host address | 0.0.0.0 | No |
| `PORT` | Flask port number | 9527 | No |
| `DEBUG` | Debug mode (True/False) | False | No |
| `GRAPH_LANGUAGE` | Graph language (zh/en) | zh | No |
| `WATERMARK_TEXT` | Watermark text | MindSpring | No |

#### **D3.js Visualization Settings**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TOPIC_FONT_SIZE` | Topic font size in pixels | 18 | No |
| `CHAR_FONT_SIZE` | Character font size in pixels | 14 | No |
| `D3_BASE_WIDTH` | Base width in pixels | 700 | No |
| `D3_BASE_HEIGHT` | Base height in pixels | 500 | No |
| `D3_PADDING` | Padding in pixels | 40 | No |

#### **Color Theme Settings**

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `D3_TOPIC_FILL` | Topic fill color | #4e79a7 | No |
| `D3_TOPIC_TEXT` | Topic text color | #ffffff | No |
| `D3_TOPIC_STROKE` | Topic stroke color | #2c3e50 | No |
| `D3_SIM_FILL` | Similarity fill color | #a7c7e7 | No |
| `D3_SIM_TEXT` | Similarity text color | #2c3e50 | No |
| `D3_SIM_STROKE` | Similarity stroke color | #4e79a7 | No |
| `D3_DIFF_FILL` | Difference fill color | #f4f6fb | No |
| `D3_DIFF_TEXT` | Difference text color | #2c3e50 | No |
| `D3_DIFF_STROKE` | Difference stroke color | #a7c7e7 | No |

## 🔍 Verification and Testing

### **Health Check**

Test the application status:
```bash
curl http://localhost:9527/status
```

Expected response:
```json
{
  "status": "running",
  "uptime_seconds": 45.2,
  "memory_percent": 12.3,
  "timestamp": 1640995200.0
}
```

### **Dependency Verification**

Check if all dependencies are properly installed:
```bash
python -c "
import sys
deps = ['flask', 'requests', 'langchain', 'yaml', 'dotenv', 'nest_asyncio', 'pyee', 'playwright', 'PIL']
missing = []
for dep in deps:
    try:
        __import__(dep)
        print(f'✅ {dep}')
    except ImportError:
        missing.append(dep)
        print(f'❌ {dep}')
if missing:
    print(f'\n❌ Missing: {missing}')
    sys.exit(1)
else:
    print('\n🎉 All dependencies verified successfully!')
"
```

### **API Key Verification**

Test API key configuration:
```bash
python -c "
from config import config
print(f'Qwen API Key: {'✅ Set' if config.QWEN_API_KEY else '❌ Missing'}')
print(f'DeepSeek API Key: {'✅ Set' if config.DEEPSEEK_API_KEY else '❌ Missing'}')
print(f'Qwen Config Valid: {'✅ Yes' if config.validate_qwen_config() else '❌ No'}')
print(f'DeepSeek Config Valid: {'✅ Yes' if config.validate_deepseek_config() else '❌ No'}')
"
```

## 🐛 Troubleshooting

### **Common Installation Issues**

#### **Python Version Issues**
```
❌ Python 3.8 or higher is required
```
**Solution:**
```bash
# Check Python version
python --version

# Install Python 3.8+ if needed
# Ubuntu/Debian:
sudo apt install python3.8 python3.8-venv

# macOS:
brew install python@3.8
```

#### **Missing Dependencies**
```
❌ Missing required packages: pillow
```
**Solution:**
```bash
# Install missing packages
pip install pillow

# Or reinstall all dependencies
pip install -r requirements.txt
```

#### **Playwright Installation Issues**
```
❌ Failed to install Playwright browser
```
**Solution:**
```bash
# Manual Playwright installation
pip install playwright
python -m playwright install chromium

# Or with system dependencies (Ubuntu/Debian)
sudo apt install libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1
python -m playwright install chromium
```

#### **Node.js Dependencies Issues**
```
npm ERR! code ENOENT
```
**Solution:**
```bash
# Check Node.js version
node --version

# Install Node.js if needed
# Ubuntu/Debian:
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs

# macOS:
brew install node

# Then reinstall D3.js dependencies
cd d3.js
npm install
cd ..
```

#### **Port Already in Use**
```
Address already in use
```
**Solution:**
```bash
# Change port in .env file
echo "PORT=9528" >> .env

# Or kill existing process
lsof -ti:9527 | xargs kill -9
```

#### **Permission Issues (Docker)**
```
Got permission denied while trying to connect to the Docker daemon
```
**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

### **API Key Issues**

#### **Qwen API Key Invalid**
```
❌ Qwen configuration validation failed
```
**Solution:**
1. Verify your API key at [DashScope Console](https://dashscope.console.aliyun.com/)
2. Ensure the key has proper permissions
3. Check the API URL in your `.env` file

#### **DeepSeek API Key Invalid**
```
❌ DeepSeek configuration validation failed
```
**Solution:**
1. Verify your API key at [DeepSeek Platform](https://platform.deepseek.com/)
2. Ensure the key has proper permissions
3. Check the API URL in your `.env` file

### **Performance Issues**

#### **Slow Startup**
```
Slow request: POST /generate_graph took 15.234s
```
**Solution:**
1. Check your internet connection
2. Verify API key permissions
3. Consider using a different API endpoint
4. Increase timeout values in `.env`

#### **Memory Issues**
```
Memory usage high: 85%
```
**Solution:**
1. Increase system RAM
2. Optimize Docker memory limits
3. Restart the application periodically

## 🔄 Updating

### **Update from Previous Versions**

#### **From Version 1.x to 2.1.0**

1. **Backup your configuration**
   ```bash
   cp .env .env.backup
   ```

2. **Update the repository**
   ```bash
   git pull origin main
   ```

3. **Update dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify configuration**
   ```bash
   python -c "from config import config; print('Configuration valid:', config.validate_qwen_config())"
   ```

5. **Test the application**
   ```bash
   python app.py
   ```

### **Docker Updates**

```bash
# Pull latest image
docker pull d3js-dify:latest

# Update with docker-compose
cd docker
docker-compose pull
docker-compose up -d
```

## 📞 Support

### **Getting Help**

- **Documentation**: Check the [full documentation](./)
- **Issues**: Create an issue on [GitHub](https://github.com/lycosa9527/D3.js_Dify/issues)
- **Discussions**: Join the [community discussions](https://github.com/lycosa9527/D3.js_Dify/discussions)

### **Useful Commands**

```bash
# Check application status
curl http://localhost:9527/status

# View application logs
tail -f logs/app.log

# Restart application
python app.py

# Update dependencies
pip install -r requirements.txt

# Docker commands
docker-compose down
docker-compose up -d
docker-compose logs -f

# Check system resources
htop
df -h
free -h
```

---

**🎉 Installation Complete!** Your D3.js_Dify version 2.1.0 is now ready to generate beautiful AI-powered visualizations.

**Made with ❤️ by the MindSpring Team**

Transform your data into beautiful visualizations with the power of AI! 🚀 