# Changelog

All notable changes to the MindGraph project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.1] - 2025-01-27

### 🚀 Major Improvements

#### Application Name Migration
- **Complete Branding Update**: Migrated from "D3.js_Dify" to "MindGraph" across all project files
- **Consistent Naming**: Updated application name in frontend files, backend routes, Docker configurations, and environment examples
- **User Interface Updates**: Updated debug.html with new application name and localStorage keys
- **Docker Configuration**: Updated all Docker files to use "mindgraph_exports" directory instead of "d3js_dify_exports"

#### Enhanced Diagram Type Classification
- **Improved LLM Response Parsing**: Fixed exact matching logic in diagram type classification to prevent substring conflicts
- **Precise Classification**: Changed from substring matching (`in`) to exact matching (`==`) for diagram type detection
- **Better Chinese Support**: Enhanced support for Chinese diagram type requests like "双气泡图" (double bubble map)
- **Reduced Fallback Usage**: Prioritizes LLM classification over hardcoded fallback logic when LLM provides clear answers

### 🔧 Technical Enhancements

#### Code Quality & Architecture
- **Exact String Matching**: Updated `classify_graph_type_with_llm` in `agent.py` to use exact matching
- **Enhanced DeepSeek Agent**: Updated `classify_diagram_type_for_development` in `deepseek_agent.py` with improved parsing
- **Removed Redundant Logic**: Eliminated duplicate diagram type extraction loops for cleaner code
- **Content-Based Inference**: Added intelligent content analysis before falling back to keyword matching

#### File System Updates
- **Frontend Consistency**: Updated `templates/debug.html` with new application name and localStorage keys
- **Backend Routes**: Verified and updated application name references in `web_routes.py`, `api_routes.py`, and `app.py`
- **Docker Files**: Updated `docker/run-docker.sh`, `docker/run-docker.bat`, `docker/Dockerfile`, and `docker/docker-compose.yml`
- **Environment Configuration**: Updated `env.example` with correct application name in comments

### 📋 Documentation Updates

#### User Documentation
- **Application Name**: All documentation now reflects the new "MindGraph" branding
- **Debug Interface**: Updated debug tool interface with new application name
- **Docker Documentation**: Updated Docker deployment instructions with new naming conventions

### 🛡️ Security & Stability

#### Classification Accuracy
- **Reliable Diagram Detection**: Fixed critical issue where "double bubble map" requests were incorrectly classified as "bubble map"
- **LLM Trust**: Enhanced system to trust LLM classification when output is clear and unambiguous
- **Fallback Logic**: Improved fallback mechanism to only trigger when LLM output cannot be parsed

### 🔄 Migration Guide

#### From Version 2.3.0 to 2.3.1

1. **Application Name**: The application is now consistently named "MindGraph" throughout
2. **Docker Exports**: Export directory changed from `d3js_dify_exports` to `mindgraph_exports`
3. **Local Storage**: Debug interface now uses `mindgraph_history` instead of `d3js_dify_history`
4. **No Breaking Changes**: All existing functionality remains the same, only naming has been updated

### 📦 Files Changed

#### Core Application Files
- `agent.py` - Enhanced diagram type classification with exact matching logic
- `deepseek_agent.py` - Improved LLM response parsing and removed redundant loops
- `templates/debug.html` - Updated application name and localStorage keys

#### Docker Files
- `docker/run-docker.sh` - Updated export directory name
- `docker/run-docker.bat` - Updated export directory name
- `docker/Dockerfile` - Updated export directory name
- `docker/docker-compose.yml` - Updated export directory name

#### Configuration Files
- `env.example` - Updated application name in comments

### 🐛 Bug Fixes

- **Diagram Classification**: Fixed critical bug where "double bubble map" requests were incorrectly classified as "bubble map"
- **String Matching**: Resolved substring matching conflicts in diagram type detection
- **Application Naming**: Eliminated all references to old application name "D3.js_Dify"

### 🔮 Future Roadmap

#### Planned Features for Version 2.4.0
- **Enhanced Testing**: Comprehensive unit and integration tests for diagram classification
- **Performance Monitoring**: Advanced performance metrics for LLM response times
- **User Interface Improvements**: Enhanced debug interface with better error reporting
- **Multi-language Enhancement**: Improved support for additional languages

---

## [2.3.0] - 2025-01-27

### 🚀 Major Improvements

#### Bridge Map Enhancement
- **Bridge Map Vertical Lines**: Made vertical connection lines invisible for cleaner visual presentation
- **Improved Bridge Map Rendering**: Enhanced visual clarity by removing distracting vertical connection lines
- **Better User Experience**: Cleaner bridge map appearance while maintaining all functional elements

### 🔧 Technical Enhancements

#### Rendering Pipeline Optimization
- **Bridge Map Styling**: Updated `renderBridgeMap` function to use transparent stroke for vertical lines
- **Visual Consistency**: Maintained horizontal main line, triangle separators, and analogy text visibility
- **Code Quality**: Improved bridge map rendering code for better maintainability

### 📋 Documentation Updates

#### User Documentation
- **Bridge Map Guide**: Updated documentation to reflect the enhanced bridge map visualization
- **Version Update**: Updated project version to 2.3.0 across all documentation files

## [2.2.0] - 2025-01-27

### 🚀 Major Improvements

#### Team Update
- **MindSpring Team**: Updated all documentation to reflect the MindSpring Team as the project maintainers
- **Branding Consistency**: Updated package.json, README.md, and all documentation files with new team information

#### Enhanced Circle Map Layout
- **New Circle Map Design**: Implemented outer boundary circle with central topic and perimeter context circles
- **Precise Geometric Positioning**: Replaced force simulation with trigonometric positioning for exact circle placement
- **Optimized Spacing**: Configurable spacing between topic and context circles (half circle size gap)
- **Improved Visual Hierarchy**: Clear visual separation between outer boundary, context circles, and central topic
- **Enhanced D3.js Renderer**: Complete `renderCircleMap` function with proper SVG structure and theming

#### Bubble Map Enhancements
- **Refined Bubble Map Layout**: Central topic positioning with 360-degree attribute distribution
- **Improved Connecting Lines**: Clean lines from topic edge to attribute edges for better visual clarity
- **Enhanced Rendering Pipeline**: Consistent high-quality output for both web interface and PNG generation
- **Better Attribute Distribution**: Even spacing of attributes around the central topic

#### Bridge Map Implementation
- **New Bridge Map Support**: Complete implementation of analogical relationship visualization
- **Relating Factor Display**: Clear presentation of the connecting concept between analogy pairs
- **Educational Focus**: Designed specifically for teaching analogical thinking skills
- **D3.js Renderer**: Full `renderBridgeMap` function with bridge structure and analogy pairs

### 🔧 Technical Enhancements

#### D3.js Renderer Improvements
- **Unified Rendering Pipeline**: All diagram types now use consistent, high-quality D3.js renderers
- **Enhanced Theming**: Comprehensive theme support for all new diagram types
- **Responsive Design**: All new diagrams adapt to different screen sizes and export dimensions
- **Export Compatibility**: PNG generation works seamlessly with all new diagram types

#### DeepSeek Agent Enhancements
- **Bridge Map Templates**: Added comprehensive development prompt templates for bridge maps
- **Educational Prompts**: Enhanced templates focus on educational value and learning outcomes
- **Multi-language Support**: All new templates available in both English and Chinese
- **Structured Output**: Consistent JSON format generation for all diagram types

#### Code Quality & Architecture
- **Modular Design**: Clean separation between different diagram renderers
- **Validation Support**: Comprehensive validation for all new diagram specifications
- **Error Handling**: Robust error handling for new diagram types
- **Documentation**: Complete inline documentation for all new functions

### 📋 Documentation Updates

#### User Documentation
- **Thinking Maps® Guide**: Updated documentation to include all supported Thinking Maps
- **Circle Map Guide**: Comprehensive guide for the new circle map layout and usage
- **Bridge Map Guide**: Complete documentation for bridge map functionality
- **API Documentation**: Updated API documentation to include new endpoints

#### Technical Documentation
- **Renderer Documentation**: Detailed documentation of all D3.js renderer functions
- **Template Documentation**: Complete documentation of development prompt templates
- **Validation Guide**: Enhanced validation documentation for all diagram types

### 🛡️ Security & Stability

#### Rendering Stability
- **Consistent Output**: All new diagram types produce consistent, high-quality output
- **Error Recovery**: Improved error handling and recovery for new diagram types
- **Validation**: Enhanced validation ensures data integrity for all diagram specifications

## [2.1.0] - 2025-01-27

### 🚀 Major Improvements

#### Enhanced Bubble Map Rendering
- **Fixed Bubble Map Layout**: Topic now positioned exactly in the center with attributes spread 360 degrees around it
- **Improved Connecting Lines**: Clean lines from topic edge to attribute edges for better visual clarity
- **Enhanced D3.js Renderer**: Updated PNG generation route to use the correct, full-featured D3.js renderer
- **Consistent Rendering Pipeline**: Both web interface and PNG generation now use the same high-quality renderer

#### Rendering Pipeline Optimization
- **Unified D3.js Renderers**: Eliminated duplicate renderer code by using the correct renderer from `static/js/d3-renderers.js`
- **Enhanced Agent JSON Generation**: Improved bubble map specification generation for better visual output
- **Comprehensive Validation**: Added validation tests to ensure bubble map pipeline works correctly
- **Multi-language Support**: Bubble map generation works with both Chinese and English prompts

### 🔧 Technical Enhancements

#### Code Quality & Architecture
- **Renderer Consistency**: Fixed inconsistency between web and PNG generation routes
- **Layout Algorithm**: Improved circular layout algorithm for better attribute distribution
- **Error Handling**: Enhanced error handling in bubble map rendering pipeline
- **Code Organization**: Cleaner separation between different renderer implementations

### 📋 Documentation Updates

#### Technical Documentation
- **Bubble Map Guide**: Updated documentation to reflect the improved layout and rendering
- **Pipeline Documentation**: Enhanced documentation of the complete rendering pipeline
- **Validation Guide**: Added documentation for bubble map specification validation

### 🛡️ Security & Stability

#### Rendering Stability
- **Consistent Output**: Both web and PNG generation now produce identical high-quality output
- **Error Recovery**: Improved error handling in rendering pipeline
- **Validation**: Enhanced validation of bubble map specifications

## [2.0.0] - 2025-07-26

### 🚀 Major Improvements

#### Enhanced Startup Sequence
- **Comprehensive Dependency Validation**: Added thorough validation of all required Python packages, API configurations, and system requirements
- **Professional Console Output**: Implemented clean, emoji-enhanced logging with clear status indicators
- **Cross-Platform Compatibility**: Fixed Windows timeout issues by replacing Unix-specific signal handling with threading
- **ASCII Art Banner**: Added professional MindSpring ASCII art logo during startup
- **Automatic Browser Opening**: Smart browser opening with server readiness detection

#### Configuration Management
- **Dynamic Environment Loading**: Property-based configuration access for real-time environment variable updates
- **Enhanced Validation**: Comprehensive validation of API keys, URLs, and numeric configuration values
- **Centralized Configuration**: All settings now managed through the `config.py` module
- **Professional Configuration Summary**: Clean display of all application settings during startup

#### Code Quality & Architecture
- **Comprehensive Inline Documentation**: Added detailed docstrings and comments throughout the codebase
- **Improved Error Handling**: Enhanced exception handling with user-friendly error messages
- **Better Logging**: Structured logging with different levels and file output
- **Code Organization**: Clear separation of concerns with well-defined sections

### 🔧 Technical Enhancements

#### Dependency Management
- **Package Validation**: Real-time checking of all required Python packages
- **Import Name Mapping**: Correct handling of package import names (e.g., Pillow → PIL)
- **Playwright Integration**: Automatic browser installation and validation
- **Version Requirements**: Updated to Python 3.8+ and Flask 3.0+

#### API Integration
- **Qwen API**: Required for core functionality with comprehensive validation
- **DeepSeek API**: Optional for enhanced features with graceful fallback
- **Request Formatting**: Clean API request formatting methods
- **Timeout Handling**: Improved timeout management for API calls

#### Docker Support
- **Enhanced Dockerfile**: Updated with version 2.1.0 and comprehensive environment configuration
- **Docker Compose**: Improved configuration with health checks and resource limits
- **Production Ready**: Optimized for production deployment with proper logging

### 📋 Documentation Updates

#### Code Documentation
- **Comprehensive Headers**: Added detailed module headers with version information
- **Inline Comments**: Enhanced inline comments explaining functionality
- **Function Documentation**: Complete docstrings for all functions and methods
- **Configuration Documentation**: Detailed explanation of all configuration options

#### User Documentation
- **README.md**: Updated with version 2.1.0 features and improved installation instructions
- **Requirements.txt**: Enhanced with detailed dependency information
- **Environment Configuration**: Clear documentation of required and optional settings

### 🛡️ Security & Stability

#### Error Handling
- **Graceful Degradation**: Application continues running even if optional features are unavailable
- **Input Validation**: Enhanced validation of all configuration values
- **Exception Logging**: Comprehensive logging of errors with context information

#### Production Readiness
- **Health Checks**: Application health monitoring endpoints
- **Resource Management**: Proper resource limits and monitoring
- **Logging**: Structured logging for production environments

### 🔄 Migration Guide

#### From Version 1.x to 2.1.0

1. **Environment Variables**: Ensure your `.env` file includes all required variables
   ```bash
   QWEN_API_KEY=your_qwen_api_key
   DEEPSEEK_API_KEY=your_deepseek_api_key  # Optional
   ```

2. **Dependencies**: Update Python dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**: The application now uses property-based configuration access
   - All configuration is automatically loaded from environment variables
   - No code changes required for existing configurations

4. **Docker**: Update Docker deployment
   ```bash
   docker build -t mindgraph:2.1.0 .
   docker-compose up -d
   ```

### 📦 Files Changed

#### Core Application Files
- `app.py` - Complete rewrite with enhanced startup sequence and dependency validation
- `config.py` - Property-based configuration management with comprehensive validation
- `requirements.txt` - Updated dependencies with version 2.1.0 header

#### Docker Files
- `docker/Dockerfile` - Enhanced with version 2.1.0 and comprehensive environment configuration
- `docker/docker-compose.yml` - Improved with health checks and resource management

#### Documentation
- `README.md` - Updated with version 2.0.0 features and improved instructions
- `CHANGELOG.md` - This file (new)

#### Utility Files
- `dependency_checker/check_dependencies.py` - Updated to match app.py validation logic

### 🎯 Breaking Changes

- **Python Version**: Now requires Python 3.8 or higher
- **Flask Version**: Updated to Flask 3.0+
- **Configuration Access**: Configuration values are now accessed as properties instead of class attributes
- **Startup Sequence**: Application startup now includes comprehensive validation

### 🐛 Bug Fixes

- **Windows Compatibility**: Fixed timeout issues on Windows systems
- **Environment Loading**: Resolved issues with `.env` file loading
- **Dependency Validation**: Fixed missing package detection
- **API Integration**: Corrected function calls and return value handling

### 🔮 Future Roadmap

#### Planned Features for Version 2.1.0
- **Enhanced Testing**: Comprehensive unit and integration tests
- **Performance Monitoring**: Advanced performance metrics and monitoring
- **API Rate Limiting**: Improved rate limiting and API usage tracking
- **User Authentication**: Optional user authentication system

#### Planned Features for Version 2.2.0
- **Database Integration**: Persistent storage for generated graphs
- **User Management**: User accounts and graph sharing
- **Advanced Export Options**: Additional export formats and customization
- **Plugin System**: Extensible architecture for custom chart types

---

## [1.0.0] - 2024-12-01

### 🎉 Initial Release

- **AI-Powered Graph Generation**: Integration with Qwen and DeepSeek LLMs
- **D3.js Visualization**: Interactive charts and graphs
- **PNG Export**: High-quality image export functionality
- **Multi-language Support**: English and Chinese language support
- **Docker Support**: Containerized deployment
- **RESTful API**: Comprehensive API for graph generation
- **Web Interface**: User-friendly web application

---

## Version History

- **2.0.0** (2025-07-26) - Major improvements with enhanced startup sequence and configuration management
- **1.0.0** (2024-12-01) - Initial release with core functionality

---

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 