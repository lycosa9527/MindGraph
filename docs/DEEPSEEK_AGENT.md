# DeepSeek Agent Documentation

## Overview

The **DeepSeek Agent** is a development-phase tool for the D3.js_Dify platform that generates enhanced prompt templates for educational diagrams. It is designed to be used by **developers during the development phase** to create better, more focused prompts that can be saved and used with the Qwen agent in production.

### Key Concepts

- **Development Phase Tool**: DeepSeek is used during development, not in production
- **Prompt Template Generator**: Creates enhanced prompts for educational context
- **Educational Focus**: Specializes in Thinking Maps® and educational diagram generation
- **File Saving**: Saves prompt templates for later use with Qwen
- **Optional Choice**: Users can choose between Qwen (default) and DeepSeek+Qwen

## Architecture

```
Development Phase:
User Request → DeepSeek Agent → Development Prompt Template → Save to File

Production Phase:
User Request → Qwen Agent → D3.js JSON (default)
User Request → DeepSeek+Qwen → Enhanced JSON (optional)
```

### Workflow Comparison

| Phase | Agent | Purpose | Output |
|-------|-------|---------|---------|
| **Development** | DeepSeek | Generate prompt templates | Markdown files with enhanced prompts |
| **Production (Default)** | Qwen | Generate JSON directly | D3.js JSON specifications |
| **Production (Optional)** | DeepSeek+Qwen | Enhanced JSON generation | D3.js JSON with educational focus |

## Features

### 🎯 Development Phase Features

- **Prompt Template Generation**: Creates comprehensive prompt templates for different diagram types
- **Educational Context**: Focuses on educational goals and learning objectives
- **File Management**: Saves prompt templates to `development_prompts/` directory
- **Diagram Classification**: Intelligently classifies user intent into appropriate diagram types
- **Multi-language Support**: Supports both English and Chinese

### 🧠 Educational Focus

- **Thinking Maps® Support**: All 8 Thinking Maps with cognitive skill development
- **Educational Goals**: Each prompt template includes specific learning objectives
- **Enhanced Requirements**: Detailed requirements for educational value
- **Usage Instructions**: Clear guidance for developers

### 📊 Supported Diagram Types

#### Thinking Maps® (8 types)
1. **Circle Map** - Define topics in context
2. **Bubble Map** - Describe attributes and characteristics  
3. **Double Bubble Map** - Compare and contrast two topics
4. **Tree Map** - Categorize and classify information
5. **Brace Map** - Show whole/part relationships
6. **Flow Map** - Sequence events and processes
7. **Multi-Flow Map** - Analyze cause and effect relationships
8. **Bridge Map** - Show analogies and similarities

#### Other Diagrams
- **Concept Maps** - Show relationships between concepts
- **Mind Maps** - Organize ideas around a central topic
- **Common Diagrams** - Venn, Fishbone, Flowchart, etc.

## Installation & Configuration

### Prerequisites

- Python 3.8+
- DeepSeek API key
- Required Python packages (see `requirements.txt`)

### Environment Variables

Add to your `.env` file:

```bash
# DeepSeek Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_TEMPERATURE=0.7
DEEPSEEK_MAX_TOKENS=4000
DEEPSEEK_TIMEOUT=30
```

### Configuration Validation

```python
from config import config

# Validate DeepSeek configuration
if config.validate_deepseek_config():
    print("DeepSeek configuration is valid")
else:
    print("DeepSeek configuration is invalid")
```

## Usage

### Development Phase Usage

#### 1. Generate Development Prompt Template

```python
import deepseek_agent

# Generate development prompt template
result = deepseek_agent.development_workflow(
    user_prompt="Compare cats and dogs",
    language="en",
    save_to_file=True
)

print(f"Diagram type: {result['diagram_type']}")
print(f"Development prompt: {result['development_prompt']}")
print(f"Saved to: {result.get('saved_filename')}")
```

#### 2. API Endpoint for Development

```bash
# Generate development prompt template
curl -X POST http://localhost:9527/generate_development_prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare cats and dogs",
    "language": "en",
    "save_to_file": true
  }'
```

Response:
```json
{
  "diagram_type": "double_bubble_map",
  "development_prompt": "# Development Phase Prompt Template...",
  "original_prompt": "Compare cats and dogs",
  "language": "en",
  "workflow_type": "development",
  "saved_filename": "development_prompts/prompt_20241201_143022.md",
  "agent": "deepseek_development"
}
```

### Production Phase Usage

#### Default (Qwen Only)

```bash
# Use Qwen as default agent
curl -X POST http://localhost:9527/generate_graph \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare cats and dogs",
    "language": "zh"
  }'
```

#### Optional (DeepSeek + Qwen)

```bash
# Use DeepSeek for enhancement + Qwen for JSON
curl -X POST http://localhost:9527/generate_graph_deepseek \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Compare cats and dogs",
    "language": "en"
  }'
```

## API Endpoints

### Development Phase

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate_development_prompt` | POST | Generate development prompt template |

### Production Phase

| Endpoint | Method | Description | Default |
|----------|--------|-------------|---------|
| `/generate_graph` | POST | Generate JSON using Qwen | ✅ Yes |
| `/generate_graph_deepseek` | POST | Generate JSON using DeepSeek+Qwen | ❌ No |

## Development Prompt Templates

### Example: Double Bubble Map Template

```markdown
# Development Phase Prompt Template Generator
## Diagram Type: double_bubble_map
## Generated: 2024-12-01 14:30:22

This prompt template is designed for the development phase to generate high-quality educational diagrams.
Developers can save this template and use it with the Qwen agent in production.

# Double Bubble Map - Development Phase Prompt Template

## Original User Request
Compare cats and dogs

## Educational Goal
Through comparative analysis, help students understand the commonalities and differences between two topics, developing critical thinking.

## Enhanced Requirements
- Generate 5 common characteristics (shared by both) - use 2-4 words, avoid complete sentences
- Generate 5 unique characteristics for topic 1 - use 2-4 words, avoid complete sentences
- Generate 5 unique characteristics for topic 2 - use 2-4 words, avoid complete sentences
- Ensure differences are comparable - each difference should represent the same type of attribute
- Use concise keywords, focus on core, essential differences
- Cover diverse dimensions (geographic, economic, cultural, physical, temporal, etc.)
- Highly abstract and condensed, maintain conciseness

## Output Format
{
  "left": "topic1",
  "right": "topic2",
  "similarities": ["feature1", "feature2", "feature3", "feature4", "feature5"],
  "left_differences": ["trait1", "trait2", "trait3", "trait4", "trait5"],
  "right_differences": ["trait1", "trait2", "trait3", "trait4", "trait5"]
}

## Usage Instructions
This prompt template is designed for the development phase to generate high-quality educational double bubble maps.
Please ensure the JSON format is correct, do not include any code block markers.
```

## File Management

### Development Prompts Directory

Generated prompt templates are saved to the `development_prompts/` directory:

```
development_prompts/
├── prompt_20241201_143022.md
├── prompt_20241201_143045.md
├── prompt_20241201_143112.md
└── ...
```

### File Naming Convention

- Format: `prompt_YYYYMMDD_HHMMSS.md`
- Timestamp: When the prompt was generated
- Extension: Markdown for easy reading and editing

## Testing

### Run Test Suite

```bash
python test_deepseek_agent.py
```

### Test Coverage

- ✅ Configuration validation
- ✅ Agent setup and LLM connection
- ✅ Diagram type classification
- ✅ Development prompt generation
- ✅ Development workflow
- ✅ File saving functionality
- ✅ Available diagram types
- ✅ Agent configuration

## Error Handling

### Common Issues

1. **API Key Not Set**
   ```
   Error: DEEPSEEK_API_KEY not found in environment variables
   Solution: Set DEEPSEEK_API_KEY in your .env file
   ```

2. **Invalid API Key**
   ```
   Error: 401 Client Error: Unauthorized
   Solution: Check your DeepSeek API key is valid
   ```

3. **Network Issues**
   ```
   Error: Connection timeout
   Solution: Check internet connection and API endpoint
   ```

### Fallback Behavior

- If DeepSeek is unavailable, the system falls back to basic prompt generation
- If classification fails, it uses keyword-based fallback classification
- If file saving fails, the prompt is still returned but not saved

## Comparison with Qwen Agent

| Feature | DeepSeek Agent | Qwen Agent |
|---------|----------------|------------|
| **Primary Role** | Development tool | Production agent |
| **Usage Phase** | Development | Production |
| **Output** | Prompt templates | JSON specifications |
| **Educational Focus** | High | Medium |
| **File Saving** | Yes | No |
| **Default** | No | Yes |
| **API Endpoints** | `/generate_development_prompt` | `/generate_graph` |

## Best Practices

### For Developers

1. **Use During Development**: Generate prompt templates during development phase
2. **Save Templates**: Save generated templates for reuse
3. **Customize**: Edit saved templates for specific use cases
4. **Test**: Test templates with Qwen agent before production

### For Production

1. **Use Qwen as Default**: Use `/generate_graph` for most cases
2. **Use DeepSeek+Qwen for Education**: Use `/generate_graph_deepseek` for educational content
3. **Monitor Performance**: Track which agent performs better for your use case

## Troubleshooting

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Configuration Check

```python
from deepseek_agent import validate_deepseek_agent_setup

if validate_deepseek_agent_setup():
    print("DeepSeek agent is properly configured")
else:
    print("DeepSeek agent configuration issue detected")
```

## Related Documentation

- [Thinking Maps Guide](docs/THINKING_MAPS_GUIDE.md) - Detailed guide to Thinking Maps® methodology
- [Agent Guide](docs/AGENT.md) - Qwen agent documentation
- [Graph Specs](docs/GRAPH_SPECS.md) - Diagram specification validation
- [API Documentation](docs/API.md) - Complete API reference

## Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review the [error handling section](#error-handling)
3. Run the [test suite](#testing)
4. Check the [configuration](#installation--configuration)

---

**Note**: The DeepSeek agent is designed for development phase use. For production, Qwen is the default agent, with DeepSeek+Qwen as an optional enhancement. 