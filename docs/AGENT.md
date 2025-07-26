# LangChain Agent Module Documentation (D3.js Version)

## Overview

The `agent.py` module is focused on LangChain agent functionality for generating graph specs for D3.js rendering. It provides a clean, modular approach to LLM-powered content generation with proper separation of concerns.

> **Note:** Playwright is now used for headless browser rendering in the backend (for PNG export), replacing Pyppeteer.

## Architecture

### Core Components

1. **QwenLLM Class** - Custom LangChain LLM wrapper for Qwen API
2. **Prompt Templates** - Structured prompts for topic extraction and characteristics generation
3. **LangChain Chains** - Orchestrated workflows for different tasks
4. **Agent Workflow Functions** - High-level functions that coordinate the entire process

### Module Structure

```
agent.py
├── QwenLLM (LangChain LLM wrapper)
├── Prompt Templates
│   ├── topic_extraction_prompt_en/zh
│   └── characteristics_prompt_en/zh
├── LangChain Chains
│   ├── create_topic_extraction_chain()
│   └── create_characteristics_chain()
├── Agent Workflow Functions
│   ├── detect_graph_type()
│   ├── generate_graph_spec()
└── Agent Configuration
    ├── get_agent_config()
    └── validate_agent_setup()
```

## Usage

### Basic Agent Workflow

```python
from agent import detect_graph_type, generate_graph_spec

# Generate a graph spec from a user prompt
user_prompt = "Compare cats and dogs"
language = "en"
graph_type = detect_graph_type(user_prompt, language)
spec = generate_graph_spec(user_prompt, graph_type, language)
print(graph_type, spec)
```

### Individual Agent Steps

```python
from agent import detect_graph_type, generate_graph_spec

graph_type = detect_graph_type("Compare BMW and Mercedes", "en")
spec = generate_graph_spec("Compare BMW and Mercedes", graph_type, "en")
```

### Agent Configuration

```python
from config import config
config.print_config_summary()
```

## LangChain Integration

### Custom LLM Wrapper

The `QwenLLM` class extends LangChain's base LLM class:

```python
from agent import QwenLLM

# Create custom LLM instance
llm = QwenLLM()

# Use with LangChain chains
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

prompt = PromptTemplate(
    input_variables=["input"],
    template="Process this: {input}"
)

chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run("test input")
```

### Chain Creation

The module provides factory functions for creating specialized chains:

```python
from agent import create_topic_extraction_chain, create_characteristics_chain

# Create topic extraction chain
topic_chain = create_topic_extraction_chain("en")
result = topic_chain.run(user_prompt="Compare apples and oranges")

# Create characteristics generation chain
char_chain = create_characteristics_chain("en")
result = char_chain.run(topic1="apples", topic2="oranges")
```

## Prompt Templates

### Topic Extraction Prompts

**English Template:**
```
TASK: Extract exactly two topics from the user's request.

User request: {user_prompt}

RULES:
1. Find exactly TWO nouns/concepts that can be compared
2. Ignore words like "compare", "generate", "create", "show", "about", "between"
3. Output ONLY: "topic1 and topic2"
4. NO code blocks, NO explanations, NO additional text
```

**Chinese Template:**
```
任务：从用户请求中提取恰好两个主题。

用户请求: {user_prompt}

规则：
1. 找到恰好两个可以比较的名词/概念
2. 忽略"比较"、"生成"、"创建"、"显示"、"关于"、"之间"等词
3. 只输出："主题1和主题2"
4. 不要代码块，不要解释，不要额外文字
```

### Characteristics Generation Prompts

Both English and Chinese templates focus on:
- **Conciseness**: 2-4 words maximum per characteristic
- **Generalization**: Core, essential differences
- **Structure**: YAML output format
- **Style**: Nouns, adjectives, or short noun phrases

## Error Handling

The agent module includes comprehensive error handling:

1. **LLM Connection Errors** - Fallback to utility functions
2. **Parsing Errors** - Graceful degradation with fallback content
3. **Validation Errors** - Output validation and correction
4. **Configuration Errors** - Setup validation and diagnostics

### Fallback Strategy

```python
try:
    # Try agent-based approach
    result = extract_topics_with_agent(prompt, language)
except Exception as e:
    # Fallback to utility functions
    from agent_utils import extract_topics_from_prompt
    result = extract_topics_from_prompt(prompt)
```

## Configuration

### Environment Variables

The agent uses configuration from `config.py`:

```python
# LLM Configuration
QWEN_MODEL = "qwen-plus"
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_TEMPERATURE = 0.7
QWEN_MAX_TOKENS = 1000

# Language Configuration
GRAPH_LANGUAGE = "zh"  # Default language
```

### Agent Configuration API

```python
from agent import get_agent_config

config = get_agent_config()
# Returns:
# {
#     "llm_model": "qwen-plus",
#     "llm_url": "https://dashscope.aliyuncs.com/...",
#     "temperature": 0.7,
#     "max_tokens": 1000,
#     "default_language": "zh"
# }
```

## Integration with Utilities

The agent module works closely with `agent_utils.py`:

### Parsing Functions

```python
from agent_utils import parse_topic_extraction_result, parse_characteristics_result

# Parse agent outputs
topics = parse_topic_extraction_result(agent_output, "en")
spec = parse_characteristics_result(agent_output, "topic1", "topic2")
```

### Fallback Functions

```python
from agent_utils import extract_topics_from_prompt, generate_characteristics_fallback

# Fallback when agent fails
topics = extract_topics_from_prompt(user_prompt)
spec = generate_characteristics_fallback(topic1, topic2)
```

## Testing

### Unit Testing

```python
from agent import QwenLLM, create_topic_extraction_chain

# Test LLM wrapper
llm = QwenLLM()
result = llm._call("test prompt")

# Test chain creation
chain = create_topic_extraction_chain("en")
result = chain.run(user_prompt="Compare A and B")
```

### Integration Testing

```python
from agent import agent_graph_workflow

# Test complete workflow
result = agent_graph_workflow("Compare cats and dogs", "en")
assert "double_bubble_map" in result
assert "left: cats" in result
assert "right: dogs" in result
```

## Best Practices

1. **Always use the workflow functions** for production code
2. **Handle exceptions gracefully** with fallback strategies
3. **Validate agent setup** before processing
4. **Use appropriate language settings** for prompts
5. **Monitor agent performance** with logging
6. **Test with various inputs** to ensure robustness

## Future Enhancements

### Planned Features

1. **Multi-step Agents** - More complex reasoning chains
2. **Memory Integration** - Context-aware conversations
3. **Tool Integration** - External data sources
4. **Streaming Responses** - Real-time output
5. **Custom Prompts** - User-defined prompt templates

### Extensibility

The modular design makes it easy to add new agent capabilities:

```python
# Add new prompt template
new_prompt = PromptTemplate(
    input_variables=["input"],
    template="New task: {input}"
)

# Create new chain
new_chain = LLMChain(llm=llm, prompt=new_prompt)

# Integrate into workflow
def new_agent_workflow(input_data):
    result = new_chain.run(input=input_data)
    return process_result(result)
```

This LangChain-focused architecture provides a solid foundation for AI-powered content generation while maintaining clean separation of concerns and extensibility for future enhancements. 