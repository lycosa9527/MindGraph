# MindGraph Project Structure
============================

## 📁 Root Directory

### Core Application Files
- `app.py` - Main Flask application entry point
- `config.py` - Centralized configuration management
- `url_config.py` - URL configuration and endpoint management
- `requirements.txt` - Python dependencies
- `package.json` - Node.js dependencies (for D3.js)
- `env.example` - Environment variables template

### API and Routes
- `api_routes.py` - API endpoints for graph generation
- `web_routes.py` - Web page routes and templates
- `agent.py` - Main AI agent for graph generation
- `deepseek_agent.py` - DeepSeek LLM integration
- `brace_map_agent.py` - Specialized brace map agent
- `agent_utils.py` - Agent utility functions
- `llm_clients.py` - LLM client implementations

### Graph Processing
- `graph_specs.py` - Graph specification validation
- `diagram_styles.py` - Diagram styling system

### Documentation
- `README.md` - Main project documentation
- `CHANGELOG.md` - Version history and changes
- `LICENSE` - MIT License
- `WIKI.md` - Project wiki and guides

## 📁 Directories

### `/templates/` - HTML Templates
- `index.html` - Main application interface
- `debug.html` - Debug and testing interface
- `style-demo.html` - Style system demonstration
- `simple_test.html` - Simple style manager test
- `test_style_manager.html` - Style manager testing
- `test_png_generation.html` - PNG generation testing

### `/static/` - Static Assets
- `/js/`
  - `d3-renderers.js` - D3.js rendering functions
  - `style-manager.js` - Centralized style management
- `/css/` - Stylesheets (if any)
- `/images/` - Image assets (if any)

### `/docs/` - Documentation
- `style-system-review.md` - Style system analysis
- `ENHANCED_BRACE_MAP_DOCUMENTATION.md` - Brace map documentation
- `VERSION_UPDATE_SUMMARY.md` - Version update details
- `AGENT_ARCHITECTURE_COMPREHENSIVE.md` - Agent architecture

### `/prompts/` - AI Prompts
- `__init__.py` - Prompt registry
- `thinking_maps.py` - Thinking maps prompts
- `concept_maps.py` - Concept map prompts
- `mind_maps.py` - Mind map prompts
- `common_diagrams.py` - Common diagram prompts
- `README.md` - Prompt system documentation

### `/tests/` - Test Files
- `test_enhanced_brace_map.py` - Brace map tests
- `test_brace_map_spec.json` - Test specifications

### `/dependency_checker/` - Dependency Management
- `check_dependencies.py` - Dependency validation
- `check_dependencies_gui.py` - GUI dependency checker
- `check_dependencies.bat` - Windows batch script
- `check_dependencies.sh` - Linux shell script
- `check_dependencies_gui.bat` - Windows GUI script
- `README.md` - Dependency checker documentation

### `/development_prompts/` - Development Prompts
- Enhanced prompt templates for development

### `/docker/` - Docker Configuration
- `Dockerfile` - Docker container definition
- `docker-compose.yml` - Docker Compose configuration
- `run-docker.bat` - Windows Docker runner
- `run-docker.sh` - Linux Docker runner
- `README.md` - Docker documentation

### `/d3.js/` - D3.js Library
- D3.js library files and documentation

### `/logs/` - Application Logs
- Application log files (auto-generated)

## 🔗 URL Structure

### API Endpoints
- `/api/generate_graph` - Generate graph specification
- `/api/generate_png` - Generate PNG image
- `/api/generate_graph_deepseek` - DeepSeek graph generation
- `/api/generate_development_prompt` - Development prompt generation
- `/api/update_style` - Update diagram styles

### Web Routes
- `/` - Main application interface
- `/debug` - Debug and testing interface
- `/style-demo` - Style system demonstration
- `/test-style-manager` - Style manager testing
- `/test-png-generation` - PNG generation testing
- `/simple-test` - Simple style manager test

### Static Resources
- `/static/js/d3-renderers.js` - D3.js rendering functions
- `/static/js/style-manager.js` - Style management system
- External CDN resources for D3.js and Google Fonts

## 🏗️ Architecture Overview

```
User Interface (HTML) → API Routes → Agent Processing → LLM Integration → Graph Generation → D3.js Rendering → PNG Export
```

### Key Components:
1. **Frontend**: HTML templates with JavaScript for user interaction
2. **API Layer**: Flask routes for handling requests
3. **Agent Layer**: AI agents for graph generation
4. **LLM Integration**: Qwen and DeepSeek LLM clients
5. **Style Management**: Centralized style system
6. **Rendering**: D3.js for graph visualization
7. **Export**: PNG generation with Playwright

## 🎯 Development Workflow

1. **User Input**: User provides prompt via web interface
2. **API Processing**: Request validated and processed
3. **AI Analysis**: LLM extracts topics and styles
4. **Graph Generation**: AI generates graph specification
5. **Style Application**: Style manager applies themes
6. **D3.js Rendering**: JavaScript renders the graph
7. **Export**: PNG generation for download

## 🔧 Configuration

### Environment Variables
- `QWEN_API_KEY` - Required for core functionality
- `DEEPSEEK_API_KEY` - Optional for enhanced features
- See `env.example` for complete configuration

### Configuration Files
- `config.py` - Centralized configuration management
- `url_config.py` - URL endpoint configuration
- `diagram_styles.py` - Default style definitions

## 📊 File Organization Principles

1. **Separation of Concerns**: Each file has a specific responsibility
2. **Modularity**: Components are self-contained and reusable
3. **Documentation**: Comprehensive documentation for all components
4. **Testing**: Dedicated test directory for validation
5. **Configuration**: Centralized configuration management
6. **Logging**: Structured logging throughout the application
7. **Error Handling**: Comprehensive error handling and recovery
8. **Security**: Input validation and sanitization

## 🚀 Deployment

### Local Development
```bash
python app.py
```

### Docker Deployment
```bash
docker-compose up
```

### Production Considerations
- Use proper WSGI server (Gunicorn, uWSGI)
- Configure reverse proxy (Nginx)
- Set up proper logging and monitoring
- Implement rate limiting and security measures
- Use environment variables for configuration

