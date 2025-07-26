# D3.js_Dify - Modular D3.js Graph Generator

A Flask-based application that generates high-quality, AI-powered graph specifications for D3.js rendering. Supports custom graph types and modular, maintainable architecture.

## 🏗️ Modular Architecture

### Core Modules
- **`app.py`** - Main Flask application with API endpoints and simple logging
- **`config.py`** - Centralized configuration management
- **`agent.py`** - LangChain agent for content generation using Qwen API
- **`agent_utils.py`** - Utility functions supporting agent operations
- **`graph_specs.py`** - Graph type schema validation

### Supported Graph Types
- Double Bubble Map
- Bubble Map
- Circle Map
- Tree Map
- Concept Map
- Mindmap

### Quick Start

#### Prerequisites
- Python 3.8+
- Node.js 18.19+ or 20+
- Qwen API key

#### Installation
1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd D3.js_Dify
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Node.js dependencies for D3.js**
   ```bash
   cd d3.js
   npm install
   cd ..
   ```

4. **Install Playwright Chrome browser**
   ```bash
   python -m playwright install chromium
   ```

5. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your Qwen API key and preferences
   ```

6. **Check dependencies (optional but recommended)**
    ```bash
    python dependency_checker/check_dependencies.py
    # or use the convenience script
    dependency_checker/check_dependencies.bat  # Windows
    dependency_checker/check_dependencies.sh   # Linux/macOS
    ```

7. **Run the application**
   ```bash
   python app.py
   # or with Docker Compose
   docker compose up --build
   ```

### Dependency Checking

The application includes comprehensive dependency checking that runs automatically at startup:

- **Python packages**: Verifies all required packages from `requirements.txt` are installed
- **Node.js installation**: Checks if Node.js and npm are available
- **D3.js dependencies**: Ensures all Node.js dependencies in the `d3.js` directory are installed

#### Interactive Installation

The dependency checker now provides interactive installation options:

**Command Line Interface:**
```bash
python dependency_checker/check_dependencies.py
# or use the convenience script
dependency_checker/check_dependencies.bat  # Windows
dependency_checker/check_dependencies.sh   # Linux/macOS
```

**Graphical User Interface (Windows):**
```bash
dependency_checker/check_dependencies_gui.bat
# or
python dependency_checker/check_dependencies_gui.py
```

**Installation Options:**
- **Yes**: Install all missing dependencies automatically
- **No**: Skip installation and get manual instructions

The system will automatically:
- Install Python packages using `pip install -r requirements.txt`
- Install D3.js dependencies using `npm install` in the d3.js directory
- Install Playwright Chrome browser using `python -m playwright install chromium`
- Install Node.js using platform-specific package managers (winget, chocolatey, homebrew, apt, etc.)
- Provide comprehensive Node.js installation guides for all platforms

The dependency checker now provides a simple "Yes/No" prompt for installing all missing dependencies at once.

### Development
- Add new graph types by updating `graph_specs.py` and the D3.js renderer in `demo.html`.
- All graph rendering is handled in the browser using D3.js.
- No image/PNG export or external CLI tools are used; PNG export is handled client-side from D3.js SVG.

### Logging & Monitoring

The application includes simple, practical logging and monitoring:

#### Logging
- **Console output**: Real-time logs during development
- **File logging**: `logs/app.log` for persistent logs
- **Request tracking**: Automatic logging of requests and responses
- **Error logging**: Detailed error information with stack traces

#### API Endpoints
- **Status**: `GET /status` - Simple application status (uptime, memory)

#### Log Format
```
2024-01-15 10:30:45 - INFO - 🚀 Starting D3.js_Dify application
2024-01-15 10:30:46 - INFO - Request: GET /status from 127.0.0.1
2024-01-15 10:30:46 - INFO - Response: 200 in 0.015s
2024-01-15 10:30:46 - INFO - Status check: OK
```

### Documentation
- [Configuration Guide](docs/CONFIGURATION.md)
- [Agent Guide](docs/AGENT.md)
- [Graph Specs Guide](docs/GRAPH_SPECS.md)


## 🤝 Contributing
- Follow the modular structure
- Add new graph types to `graph_specs.py` and D3.js renderers
- Update documentation
- Test thoroughly
- Submit pull request

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details. 