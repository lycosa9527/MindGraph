"""
DeepSeek Agent Module for D3.js_Dify - Development Phase Tool

This module contains the DeepSeek LLM functionality for generating enhanced prompts
during the development phase. DeepSeek is used by developers to create better prompts
that can be used by the Qwen agent in production.

DeepSeek focuses on educational context and map usage to create better prompts
that developers can save and use with the Qwen agent.
"""

import os
import logging
import re
import json
from dotenv import load_dotenv
load_dotenv()

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/deepseek_agent.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

from langchain.llms.base import LLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import requests
import yaml
from config import config
from graph_specs import (
    DIAGRAM_VALIDATORS,
    get_available_diagram_types,
    validate_diagram_spec
)


class DeepSeekLLM(LLM):
    """
    Custom LangChain LLM wrapper for DeepSeek API
    """
    def _call(self, prompt, stop=None):
        logger.info(f"DeepSeekLLM._call() - Model: {config.DEEPSEEK_MODEL}")
        logger.debug(f"Prompt sent to DeepSeek:\n{prompt[:1000]}{'...' if len(prompt) > 1000 else ''}")

        headers = config.get_deepseek_headers()
        data = config.get_deepseek_data(prompt)

        logger.info(f"Making request to: {config.DEEPSEEK_API_URL}")
        try:
            resp = requests.post(
                config.DEEPSEEK_API_URL,
                headers=headers,
                json=data
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"DeepSeekLLM response received - Length: {len(content)} characters")
            logger.debug(f"DeepSeek Output:\n{content[:1000]}{'...' if len(content) > 1000 else ''}")
            return content
        except Exception as e:
            logger.error(f"DeepSeekLLM API call failed: {e}", exc_info=True)
            raise

    @property
    def _llm_type(self):
        return "deepseek"


# Initialize the LLM instance
llm = DeepSeekLLM()


# ============================================================================
# DEVELOPMENT PHASE PROMPT GENERATION
# ============================================================================

def create_development_prompt_template(diagram_type: str, user_prompt: str, language='en'):
    """Create enhanced prompt templates for development phase."""
    
    development_prompts = {
        "double_bubble_map": {
            "zh": f"""
# 双气泡图 - 开发阶段提示模板

## 原始用户需求
{user_prompt}

## 教育目标
通过对比分析，帮助学生理解两个主题的共性和差异，培养批判性思维。

## 增强要求
- 生成5个共同特征（两者共有）- 使用2-4个词，避免完整句子
- 生成5个主题1的独有特征 - 使用2-4个词，避免完整句子
- 生成5个主题2的独有特征 - 使用2-4个词，避免完整句子
- 确保差异具有可比性 - 每个差异应代表相同类型的属性
- 使用简洁的关键词，专注于核心、本质差异
- 涵盖不同维度（地理、经济、文化、物理、时间等）
- 高度抽象和概括，保持简洁性

## 输出格式
{{
  "left": "主题1",
  "right": "主题2", 
  "similarities": ["特征1", "特征2", "特征3", "特征4", "特征5"],
  "left_differences": ["特点1", "特点2", "特点3", "特点4", "特点5"],
  "right_differences": ["特点1", "特点2", "特点3", "特点4", "特点5"]
}}

## 使用说明
此提示模板专为开发阶段设计，用于生成高质量的教育性双气泡图。
请确保JSON格式正确，不要包含任何代码块标记。
""",
            "en": f"""
# Double Bubble Map - Development Phase Prompt Template

## Original User Request
{user_prompt}

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
{{
  "left": "topic1",
  "right": "topic2",
  "similarities": ["feature1", "feature2", "feature3", "feature4", "feature5"],
  "left_differences": ["trait1", "trait2", "trait3", "trait4", "trait5"],
  "right_differences": ["trait1", "trait2", "trait3", "trait4", "trait5"]
}}

## Usage Instructions
This prompt template is designed for the development phase to generate high-quality educational double bubble maps.
Please ensure the JSON format is correct, do not include any code block markers.
"""
        },
        
        "bubble_map": {
            "zh": f"""
# 气泡图 - 开发阶段提示模板

## 原始用户需求
{user_prompt}

## 教育目标
通过属性分析，帮助学生深入理解单个主题的特征和性质。

## 增强要求
- 生成6-8个描述性特征（形容词或名词短语）
- 特征应该涵盖不同维度（物理、功能、价值、文化等）
- 使用简洁的关键词，避免完整句子
- 专注于核心、重要特征
- 确保特征具有教育价值和学习意义

## 输出格式
{{
  "topic": "主题",
  "attributes": ["特征1", "特征2", "特征3", "特征4", "特征5", "特征6"]
}}

## 使用说明
此提示模板专为开发阶段设计，用于生成高质量的教育性气泡图。
请确保JSON格式正确，不要包含任何代码块标记。
""",
            "en": f"""
# Bubble Map - Development Phase Prompt Template

## Original User Request
{user_prompt}

## Educational Goal
Through attribute analysis, help students deeply understand the characteristics and properties of a single topic.

## Enhanced Requirements
- Generate 6-8 descriptive characteristics (adjectives or noun phrases)
- Characteristics should cover different dimensions (physical, functional, value, cultural, etc.)
- Use concise keywords, avoid complete sentences
- Focus on core, important characteristics
- Ensure characteristics have educational value and learning significance

## Output Format
{{
  "topic": "topic",
  "attributes": ["characteristic1", "characteristic2", "characteristic3", "characteristic4", "characteristic5", "characteristic6"]
}}

## Usage Instructions
This prompt template is designed for the development phase to generate high-quality educational bubble maps.
Please ensure the JSON format is correct, do not include any code block markers.
"""
        },
        
        "circle_map": {
            "zh": f"""
# 圆圈图 - 开发阶段提示模板

## 原始用户需求
{user_prompt}

## 教育目标
通过在上下文中定义主题，帮助学生理解主题的背景和环境。

## 增强要求
- 生成6-10个上下文特征
- 特征应该描述主题的环境、背景、相关因素
- 使用简洁的关键词，避免完整句子
- 专注于提供全面的上下文理解
- 确保上下文特征有助于学生理解主题的完整图景

## 输出格式
{{
  "topic": "主题",
  "context": ["上下文1", "上下文2", "上下文3", "上下文4", "上下文5", "上下文6"]
}}

## 使用说明
此提示模板专为开发阶段设计，用于生成高质量的教育性圆圈图。
请确保JSON格式正确，不要包含任何代码块标记。
""",
            "en": f"""
# Circle Map - Development Phase Prompt Template

## Original User Request
{user_prompt}

## Educational Goal
By defining a topic in context, help students understand the topic's background and environment.

## Enhanced Requirements
- Generate 6-10 contextual characteristics
- Characteristics should describe the topic's environment, background, related factors
- Use concise keywords, avoid complete sentences
- Focus on providing comprehensive contextual understanding
- Ensure contextual characteristics help students understand the complete picture of the topic

## Output Format
{{
  "topic": "topic",
  "context": ["context1", "context2", "context3", "context4", "context5", "context6"]
}}

## Usage Instructions
This prompt template is designed for the development phase to generate high-quality educational circle maps.
Please ensure the JSON format is correct, do not include any code block markers.
"""
        }
    }
    
    if diagram_type in development_prompts:
        return development_prompts[diagram_type][language]
    else:
        # Generic development prompt for other diagram types
        return f"""
# {diagram_type.replace('_', ' ').title()} - Development Phase Prompt Template

## Original User Request
{user_prompt}

## Educational Focus
Ensure the diagram helps students understand and organize information effectively.

## Enhanced Requirements
- Focus on educational usage and clear understanding
- Generate appropriate JSON structure for D3.js rendering
- Maintain educational value and learning significance

## Output Format
Generate appropriate JSON structure for {diagram_type}

## Usage Instructions
This prompt template is designed for the development phase to generate high-quality educational {diagram_type} diagrams.
Please ensure the JSON format is correct, do not include any code block markers.
"""


def generate_development_prompt(user_prompt: str, diagram_type: str, language: str = 'en') -> str:
    """
    Generate development phase prompt template for the given diagram type.
    
    Args:
        user_prompt: The user's original input prompt
        diagram_type: Type of diagram to generate
        language: Language for processing ('en' or 'zh')
    
    Returns:
        str: Development phase prompt template
    """
    try:
        # Generate development prompt template
        development_prompt = create_development_prompt_template(diagram_type, user_prompt, language)
        
        # Add development phase context
        if language == 'zh':
            header = f"""
# 开发阶段提示模板生成器
## 图表类型: {diagram_type}
## 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

此提示模板专为开发阶段设计，用于生成高质量的教育性图表。
开发者可以将此模板保存并在生产环境中使用Qwen代理。
"""
        else:
            header = f"""
# Development Phase Prompt Template Generator
## Diagram Type: {diagram_type}
## Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This prompt template is designed for the development phase to generate high-quality educational diagrams.
Developers can save this template and use it with the Qwen agent in production.
"""
        
        return header + "\n" + development_prompt
        
    except Exception as e:
        logger.error(f"DeepSeek agent: Development prompt generation failed: {e}")
        # Fallback to basic prompt
        return f"Generate a JSON specification for a {diagram_type} for: {user_prompt}"


def save_development_prompt_to_file(prompt: str, filename: str = None):
    """
    Save development prompt to a file for later use.
    
    Args:
        prompt: The development prompt to save
        filename: Optional filename, will generate one if not provided
    """
    if not filename:
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"development_prompts/prompt_{timestamp}.md"
    
    # Create directory if it doesn't exist
    os.makedirs("development_prompts", exist_ok=True)
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(prompt)
        logger.info(f"Development prompt saved to: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save development prompt: {e}")
        return None


# ============================================================================
# DIAGRAM TYPE CLASSIFICATION (for development phase)
# ============================================================================

def classify_diagram_type_for_development(user_prompt: str, language: str = 'en') -> str:
    """
    Use DeepSeek to classify the user's intent into a specific diagram type for development.
    
    Args:
        user_prompt: The user's input prompt
        language: Language for processing ('en' or 'zh')
    
    Returns:
        str: Diagram type from available types
    """
    available_types = get_available_diagram_types()
    type_descriptions = {
        # Thinking Maps
        "double_bubble_map": "Compare and contrast two topics",
        "bubble_map": "Describe attributes of a single topic", 
        "circle_map": "Define a topic in context",
        "flow_map": "Sequence events or processes",
        "brace_map": "Show whole/part relationships",
        "tree_map": "Categorize and classify information",
        "multi_flow_map": "Show cause and effect relationships",
        "bridge_map": "Show analogies and similarities",
        
        # Concept Maps
        "concept_map": "Show relationships between concepts",
        "semantic_web": "Create a web of related concepts",
        
        # Mind Maps
        "mindmap": "Organize ideas around a central topic",
        "radial_mindmap": "Create a radial mind map structure",
        
        # Common Diagrams
        "venn_diagram": "Show overlapping sets",
        "fishbone_diagram": "Analyze cause and effect",
        "flowchart": "Show process flow",
        "org_chart": "Show organizational structure",
        "timeline": "Show chronological events"
    }
    
    if language == 'zh':
        prompt_text = f"""
你是一个图表类型分类助手，用于开发阶段。根据用户的需求，判断他们想要创建哪种类型的图表。

可用的图表类型：
{chr(10).join([f"- {k}: {v}" for k, v in type_descriptions.items()])}

规则：
- 仔细分析用户的需求和意图
- 选择最适合的图表类型
- 只输出图表类型名称，不要其他内容

示例：
用户需求：比较猫和狗 → 输出：double_bubble_map
用户需求：描述太阳系的特征 → 输出：bubble_map
用户需求：展示水循环过程 → 输出：flow_map
用户需求：分析全球变暖的原因和影响 → 输出：multi_flow_map

用户需求：{{user_prompt}}
你的输出：
"""
    else:
        prompt_text = f"""
You are a diagram type classifier for the development phase. Based on the user's request, determine which type of diagram they want to create.

Available diagram types:
{chr(10).join([f"- {k}: {v}" for k, v in type_descriptions.items()])}

Rules:
- Carefully analyze the user's needs and intent
- Choose the most appropriate diagram type
- Output only the diagram type name, nothing else

Examples:
User request: Compare cats and dogs → Output: double_bubble_map
User request: Describe characteristics of solar system → Output: bubble_map
User request: Show water cycle process → Output: flow_map
User request: Analyze causes and effects of global warming → Output: multi_flow_map

User request: {{user_prompt}}
Your output:
"""
    
    prompt = PromptTemplate(
        input_variables=["user_prompt"],
        template=prompt_text
    )
    
    try:
        result = (prompt | llm).invoke({"user_prompt": user_prompt}).strip().lower()
        
        # Extract the diagram type from the response
        for diagram_type in available_types:
            if diagram_type in result:
                return diagram_type
        
        # Fallback to default types based on keywords
        if any(word in user_prompt.lower() for word in ["compare", "vs", "difference", "对比", "比较"]):
            return "double_bubble_map"
        elif any(word in user_prompt.lower() for word in ["describe", "characteristics", "特征", "描述"]):
            return "bubble_map"
        elif any(word in user_prompt.lower() for word in ["process", "steps", "流程", "步骤"]):
            return "flow_map"
        elif any(word in user_prompt.lower() for word in ["cause", "effect", "原因", "影响"]):
            return "multi_flow_map"
        else:
            return "bubble_map"  # Default fallback
            
    except Exception as e:
        logger.error(f"DeepSeek classification failed: {e}")
        # Fallback classification
        if any(word in user_prompt.lower() for word in ["compare", "vs", "difference", "对比", "比较"]):
            return "double_bubble_map"
        elif any(word in user_prompt.lower() for word in ["describe", "characteristics", "特征", "描述"]):
            return "bubble_map"
        else:
            return "bubble_map"


# ============================================================================
# DEVELOPMENT WORKFLOW FUNCTIONS
# ============================================================================

def development_workflow(user_prompt: str, language: str = 'en', save_to_file: bool = True) -> dict:
    """
    Development phase workflow for generating enhanced prompts.
    
    Args:
        user_prompt: The user's input prompt
        language: Language for processing ('en' or 'zh')
        save_to_file: Whether to save the prompt to a file
    
    Returns:
        dict: Contains diagram_type, development_prompt, and optional filename
    """
    logger.info(f"DeepSeek Development: Starting workflow for: {user_prompt}")
    
    try:
        # Step 1: Classify the diagram type
        diagram_type = classify_diagram_type_for_development(user_prompt, language)
        logger.info(f"DeepSeek Development: Classified diagram type: {diagram_type}")
        
        # Step 2: Generate development prompt template
        development_prompt = generate_development_prompt(user_prompt, diagram_type, language)
        logger.info(f"DeepSeek Development: Generated development prompt for {diagram_type}")
        
        result = {
            "diagram_type": diagram_type,
            "development_prompt": development_prompt,
            "original_prompt": user_prompt,
            "language": language,
            "workflow_type": "development"
        }
        
        # Step 3: Save to file if requested
        if save_to_file:
            filename = save_development_prompt_to_file(development_prompt)
            if filename:
                result["saved_filename"] = filename
        
        return result
        
    except Exception as e:
        logger.error(f"DeepSeek Development: Workflow failed: {e}")
        return {
            "error": f"Development workflow failed: {str(e)}",
            "diagram_type": "bubble_map",  # Fallback
            "development_prompt": f"Generate a JSON specification for bubble_map for: {user_prompt}",
            "original_prompt": user_prompt,
            "language": language,
            "workflow_type": "development"
        }


# ============================================================================
# AGENT CONFIGURATION
# ============================================================================

def get_deepseek_agent_config():
    """
    Get current DeepSeek agent configuration
    
    Returns:
        dict: Agent configuration
    """
    return {
        "llm_model": config.DEEPSEEK_MODEL,
        "llm_url": config.DEEPSEEK_API_URL,
        "temperature": config.DEEPSEEK_TEMPERATURE,
        "max_tokens": config.DEEPSEEK_MAX_TOKENS,
        "default_language": config.GRAPH_LANGUAGE,
        "role": "development_tool",  # Updated role description
        "workflow_type": "development_phase"
    }


def validate_deepseek_agent_setup():
    """
    Validate that the DeepSeek agent is properly configured
    
    Returns:
        bool: True if agent is ready, False otherwise
    """
    try:
        # Test LLM connection
        test_prompt = "Test"
        llm._call(test_prompt)
        logger.info("DeepSeek Development Agent: LLM connection validated")
        return True
    except Exception as e:
        logger.error(f"DeepSeek Development Agent: LLM connection failed: {e}")
        return False 