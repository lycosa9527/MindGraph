"""
DeepSeek Agent Module for MindGraph - Development Phase Tool

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
# ENHANCED TOPIC AND STYLE EXTRACTION
# ============================================================================

def extract_topics_and_styles_from_prompt(user_prompt: str, language: str = 'en') -> dict:
    """
    Use DeepSeek to extract both topics and style preferences from user prompt in a single pass.
    This is more efficient than separate hardcoded parsing.
    
    Args:
        user_prompt: The user's input prompt
        language: Language for processing ('en' or 'zh')
    
    Returns:
        dict: Contains 'topics', 'style_preferences', and 'diagram_type'
    """
    
    if language == 'zh':
        prompt_text = f"""
你是一个智能图表助手，用于从用户需求中同时提取主题内容和样式偏好。

请分析以下用户需求，并提取：
1. 主要主题和子主题
2. 样式偏好（颜色、字体、布局等）
3. 最适合的图表类型

可用图表类型：
- double_bubble_map: 比较和对比两个主题
- bubble_map: 描述单个主题的特征
- circle_map: 在上下文中定义主题
- flow_map: 序列事件或过程
- brace_map: 显示整体/部分关系
- tree_map: 分类和归类信息
- multi_flow_map: 显示因果关系
- bridge_map: 桥形图 - 显示类比和相似性
- mindmap: 围绕中心主题组织想法
- concept_map: 显示概念之间的关系

样式偏好包括：
- 颜色主题：classic, innovation, nature, corporate, vibrant, pastel, monochrome
- 颜色名称：red, blue, green, yellow, purple, orange, pink, brown, gray, black, white
- 字体大小：small, medium, large, extra-large
- 重要性：center, main, sub
- 背景：dark, light
- 边框：bold, thin

请以JSON格式输出：
{{{{
    "topics": ["主题1", "主题2", ...],
    "style_preferences": {{{{
        "color_theme": "主题名称",
        "primary_color": "颜色名称",
        "font_size": "字体大小",
        "importance": "重要性级别",
        "background": "背景偏好",
        "stroke": "边框样式"
    }}}},
    "diagram_type": "图表类型"
}}}}

用户需求：{user_prompt}
你的输出：
"""
    else:
        prompt_text = f"""
You are an intelligent diagram assistant that extracts both topics and style preferences from user requests in a single pass.

Please analyze the following user request and extract:
1. Main topics and subtopics
2. Style preferences (colors, fonts, layout, etc.)
3. Most suitable diagram type

Available diagram types:
- double_bubble_map: Compare and contrast two topics
- bubble_map: Describe attributes of a single topic
- circle_map: Define a topic in context
- flow_map: Sequence events or processes
- brace_map: Show whole/part relationships
- tree_map: Categorize and classify information
- multi_flow_map: Show cause and effect relationships
- bridge_map: Show analogies and similarities
- mindmap: Organize ideas around a central topic
- concept_map: Show relationships between concepts

Style preferences include:
- Color themes: classic, innovation, nature, corporate, vibrant, pastel, monochrome
- Color names: red, blue, green, yellow, purple, orange, pink, brown, gray, black, white
- Font sizes: small, medium, large, extra-large
- Importance levels: center, main, sub
- Backgrounds: dark, light
- Strokes: bold, thin

Please output in JSON format:
{{{{
    "topics": ["topic1", "topic2", ...],
    "style_preferences": {{{{
        "color_theme": "theme_name",
        "primary_color": "color_name",
        "font_size": "font_size",
        "importance": "importance_level",
        "background": "background_preference",
        "stroke": "stroke_style"
    }}}},
    "diagram_type": "diagram_type"
}}}}

User request: {user_prompt}
Your output:
"""
    
    prompt = PromptTemplate(
        input_variables=["user_prompt"],
        template=prompt_text
    )
    
    try:
        result = (prompt | llm).invoke({"user_prompt": user_prompt}).strip()
        
        # Try to parse JSON response
        try:
            # Clean the result - remove markdown code blocks if present
            cleaned_result = result.strip()
            if cleaned_result.startswith('```json'):
                cleaned_result = cleaned_result[7:]  # Remove ```json
            if cleaned_result.startswith('```'):
                cleaned_result = cleaned_result[3:]  # Remove ```
            if cleaned_result.endswith('```'):
                cleaned_result = cleaned_result[:-3]  # Remove trailing ```
            cleaned_result = cleaned_result.strip()
            
            parsed_result = json.loads(cleaned_result)
            
            # Validate and clean the result
            validated_result = {
                "topics": parsed_result.get("topics", []),
                "style_preferences": parsed_result.get("style_preferences", {}),
                "diagram_type": parsed_result.get("diagram_type", "bubble_map")
            }
            
            # Ensure diagram_type is valid
            available_types = get_available_diagram_types()
            if validated_result["diagram_type"] not in available_types:
                validated_result["diagram_type"] = "bubble_map"  # Default fallback
            
            logger.info(f"Successfully extracted topics and styles: {validated_result}")
            return validated_result
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON response: {result}")
            # Fallback to basic extraction
            return extract_topics_and_styles_fallback(user_prompt, language)
            
    except Exception as e:
        logger.error(f"DeepSeek extraction failed: {e}")
        return extract_topics_and_styles_fallback(user_prompt, language)


def extract_topics_and_styles_fallback(user_prompt: str, language: str = 'en') -> dict:
    """
    Fallback method for extracting topics and styles when AI extraction fails.
    Uses basic keyword matching and the existing hardcoded parser.
    """
    from diagram_styles import parse_style_from_prompt
    
    # Extract topics using basic keyword matching
    topics = []
    prompt_lower = user_prompt.lower()
    
    # Simple topic extraction based on common patterns
    if "compare" in prompt_lower or "vs" in prompt_lower or "对比" in prompt_lower:
        # Extract comparison topics
        words = user_prompt.split()
        for i, word in enumerate(words):
            if word.lower() in ["compare", "vs", "对比", "比较"] and i + 1 < len(words):
                if i + 2 < len(words):
                    topics = [words[i+1], words[i+2]]
                    break
    
    # Extract style preferences using the existing parser
    style_preferences = parse_style_from_prompt(user_prompt)
    
    # Determine diagram type
    diagram_type = classify_diagram_type_for_development(user_prompt, language)
    
    return {
        "topics": topics,
        "style_preferences": style_preferences,
        "diagram_type": diagram_type
    }


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
        },
        
        "bridge_map": {
            "zh": f"""
# 桥形图 - 开发阶段提示模板

## 原始用户需求
{user_prompt}

## 教育目标
通过类比推理，帮助学生理解概念之间的相似关系和模式，培养类比思维能力。

## 增强要求
- 生成4-6个类比关系对，格式为 a:b, c:d, e:f 等
- 每个类比对应该展示相同的关联因子
- 关联因子固定为 "as" (标准桥形图格式)
- 类比对应该具有教育价值和学习意义
- 使用尽可能少的词汇 - 仅使用单个词汇或极短短语
- 避免完整句子、长描述，或在单个词汇足够时使用多个词汇
- 确保类比关系逻辑清晰，易于理解
- 涵盖不同领域和概念，展示跨学科联系
- 每个类比都应该有一个从0开始的唯一id

## 输出格式
{{
  "relating_factor": "关系词或短语",
  "analogies": [
    {{
      "left": "类比对中的第一项",
      "right": "类比对中的第二项",
      "id": 0
    }},
    {{
      "left": "类比对中的第一项",
      "right": "类比对中的第二项",
      "id": 1
    }}
  ]
}}

## 使用说明
此提示模板专为开发阶段设计，用于生成高质量的教育性桥形图。
请确保JSON格式正确，不要包含任何代码块标记。
""",
            "en": f"""
# Bridge Map - Development Phase Prompt Template

## Original User Request
{user_prompt}

## Educational Goal
Through analogical reasoning, help students understand similar relationships and patterns between concepts, developing analogical thinking skills.

## Enhanced Requirements
- Generate 4-6 analogy pairs in the format a:b, c:d, e:f, etc.
- Each analogy pair should demonstrate the same relating factor
- The relating factor is fixed as "as" (standard bridge map format)
- Analogy pairs should have educational value and learning significance
- Use AT LEAST WORDS AS POSSIBLE - single words or very short phrases only
- Avoid complete sentences, long descriptions, or multiple words when one word suffices
- Ensure analogy relationships are logically clear and easy to understand
- Cover diverse fields and concepts, showing interdisciplinary connections
- Each analogy should have a unique id starting from 0

## Output Format
{{
  "relating_factor": "relationship word or phrase",
  "analogies": [
    {{
      "left": "First item in analogy pair",
      "right": "Second item in analogy pair",
      "id": 0
    }},
    {{
      "left": "First item in analogy pair",
      "right": "Second item in analogy pair",
      "id": 1
    }}
  ]
}}

## Usage Instructions
This prompt template is designed for the development phase to generate high-quality educational bridge maps.
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

重要区分：
- 比较/对比 (compare/contrast): 使用 double_bubble_map
- 类比 (analogy): 使用 bridge_map

        示例：
        用户需求：比较猫和狗 → 输出：double_bubble_map
        用户需求：生成一幅关于风电和水电的双气泡图 → 输出：double_bubble_map
        用户需求：制作双气泡图比较城市和乡村 → 输出：double_bubble_map
        用户需求：双气泡图：比较传统能源和可再生能源 → 输出：double_bubble_map
        用户需求：类比：手之于人，如同轮子之于车 → 输出：bridge_map
        用户需求：用桥形图类比光合作用和呼吸作用 → 输出：bridge_map
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

Important distinction:
- Compare/contrast: use double_bubble_map
- Analogy: use bridge_map

Examples:
User request: Compare cats and dogs → Output: double_bubble_map
User request: Generate a double bubble map about wind power and hydropower → Output: double_bubble_map
User request: Create double bubble map comparing cities and rural areas → Output: double_bubble_map
User request: Double bubble map: compare traditional and renewable energy → Output: double_bubble_map
User request: Analogy: hand is to person as wheel is to car → Output: bridge_map
User request: Use bridge map to analogize photosynthesis and respiration → Output: bridge_map
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
        
        # Enhanced LLM response parsing
        logger.info(f"DeepSeek classification response: '{result}'")
        
        # First, try exact match with available types
        for diagram_type in available_types:
            if diagram_type == result:
                logger.info(f"DeepSeek classified as: {diagram_type}")
                return diagram_type
        
        # If no exact match, try to extract from common variations
        result_clean = result.replace(" ", "_").replace("-", "_")
        for diagram_type in available_types:
            if diagram_type == result_clean:
                logger.info(f"DeepSeek classified as (cleaned): {diagram_type}")
                return diagram_type
        
        # If still no match, try to infer from the response content
        if "double" in result and "bubble" in result:
            logger.info("DeepSeek response suggests double_bubble_map")
            return "double_bubble_map"
        elif "bubble" in result:
            logger.info("DeepSeek response suggests bubble_map")
            return "bubble_map"
        elif "bridge" in result:
            logger.info("DeepSeek response suggests bridge_map")
            return "bridge_map"
        elif "circle" in result:
            logger.info("DeepSeek response suggests circle_map")
            return "circle_map"
        elif "flow" in result:
            logger.info("DeepSeek response suggests flow_map")
            return "flow_map"
        elif "tree" in result:
            logger.info("DeepSeek response suggests tree_map")
            return "tree_map"
        elif "multi" in result and "flow" in result:
            logger.info("DeepSeek response suggests multi_flow_map")
            return "multi_flow_map"
        elif "brace" in result:
            logger.info("DeepSeek response suggests brace_map")
            return "brace_map"
        elif "concept" in result:
            logger.info("DeepSeek response suggests concept_map")
            return "concept_map"
        elif "mind" in result:
            logger.info("DeepSeek response suggests mindmap")
            return "mindmap"
        
        # Only if LLM completely fails, use fallback logic
        logger.warning(f"DeepSeek classification failed to match any type, using fallback logic")
        if any(word in user_prompt.lower() for word in ["analogy", "analogize", "类比", "桥形图", "桥接图"]):
            return "bridge_map"
        elif any(word in user_prompt.lower() for word in ["compare", "vs", "difference", "对比", "比较", "双气泡图", "双泡图"]):
            return "double_bubble_map"
        elif any(word in user_prompt.lower() for word in ["describe", "characteristics", "特征", "描述", "气泡图", "单气泡图"]):
            return "bubble_map"
        elif any(word in user_prompt.lower() for word in ["process", "steps", "流程", "步骤"]):
            return "flow_map"
        elif any(word in user_prompt.lower() for word in ["cause", "effect", "原因", "影响"]):
            return "multi_flow_map"
        else:
            return "bubble_map"  # Default fallback
            
    except Exception as e:
        logger.error(f"DeepSeek classification failed: {e}")
        logger.info("Using fallback classification due to DeepSeek error")
        # Fallback classification - only used when LLM completely fails
        if any(word in user_prompt.lower() for word in ["analogy", "analogize", "类比", "桥形图", "桥接图"]):
            return "bridge_map"
        elif any(word in user_prompt.lower() for word in ["compare", "vs", "difference", "对比", "比较", "双气泡图", "双泡图"]):
            return "double_bubble_map"
        elif any(word in user_prompt.lower() for word in ["describe", "characteristics", "特征", "描述", "气泡图", "单气泡图"]):
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


def enhanced_development_workflow(user_prompt: str, language: str = 'en', save_to_file: bool = True) -> dict:
    """
    Enhanced development phase workflow that extracts topics and styles in a single AI pass.
    More efficient than the traditional workflow.
    
    Args:
        user_prompt: The user's input prompt
        language: Language for processing ('en' or 'zh')
        save_to_file: Whether to save the prompt to a file
    
    Returns:
        dict: Contains extracted topics, styles, diagram_type, and development_prompt
    """
    logger.info(f"DeepSeek Enhanced Development: Starting workflow for: {user_prompt}")
    
    try:
        # Step 1: Extract topics and styles in a single AI pass
        extraction_result = extract_topics_and_styles_from_prompt(user_prompt, language)
        logger.info(f"DeepSeek Enhanced Development: Extracted topics and styles: {extraction_result}")
        
        # Step 2: Generate development prompt template with extracted information
        diagram_type = extraction_result["diagram_type"]
        topics = extraction_result["topics"]
        style_preferences = extraction_result["style_preferences"]
        
        # Create enhanced prompt with extracted information
        enhanced_prompt = create_enhanced_development_prompt(
            user_prompt, diagram_type, topics, style_preferences, language
        )
        
        result = {
            "diagram_type": diagram_type,
            "topics": topics,
            "style_preferences": style_preferences,
            "development_prompt": enhanced_prompt,
            "original_prompt": user_prompt,
            "language": language,
            "workflow_type": "enhanced_development",
            "extraction_method": "ai_combined"
        }
        
        # Step 3: Save to file if requested
        if save_to_file:
            filename = save_enhanced_development_prompt_to_file(
                enhanced_prompt, topics, style_preferences, diagram_type
            )
            if filename:
                result["saved_filename"] = filename
        
        return result
        
    except Exception as e:
        logger.error(f"DeepSeek Enhanced Development: Workflow failed: {e}")
        # Fallback to traditional workflow
        return development_workflow(user_prompt, language, save_to_file)


def create_enhanced_development_prompt(user_prompt: str, diagram_type: str, 
                                     topics: list, style_preferences: dict, language: str = 'en') -> str:
    """
    Create an enhanced development prompt that includes extracted topics and style preferences.
    """
    
    if language == 'zh':
        header = f"""
# 增强开发阶段提示模板
## 图表类型: {diagram_type}
## 提取的主题: {', '.join(topics) if topics else '未指定'}
## 样式偏好: {style_preferences}
## 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

此提示模板使用AI智能提取的主题和样式偏好，专为开发阶段设计。
开发者可以将此模板保存并在生产环境中使用Qwen代理。

## 原始用户需求
{user_prompt}

## AI提取的主题
{topics}

## AI提取的样式偏好
{style_preferences}

## 增强要求
基于提取的主题和样式偏好，生成高质量的JSON图表规范。
确保样式偏好得到正确应用。
"""
    else:
        header = f"""
# Enhanced Development Phase Prompt Template
## Diagram Type: {diagram_type}
## Extracted Topics: {', '.join(topics) if topics else 'Not specified'}
## Style Preferences: {style_preferences}
## Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This prompt template uses AI-extracted topics and style preferences, designed for the development phase.
Developers can save this template and use it with the Qwen agent in production.

## Original User Request
{user_prompt}

## AI-Extracted Topics
{topics}

## AI-Extracted Style Preferences
{style_preferences}

## Enhanced Requirements
Based on the extracted topics and style preferences, generate a high-quality JSON diagram specification.
Ensure style preferences are correctly applied.
"""
    
    # Add the base development prompt template
    base_prompt = create_development_prompt_template(diagram_type, user_prompt, language)
    
    return header + "\n" + base_prompt


def save_enhanced_development_prompt_to_file(prompt: str, topics: list, 
                                           style_preferences: dict, diagram_type: str, 
                                           filename: str = None) -> str:
    """
    Save enhanced development prompt to a file with metadata.
    """
    if not filename:
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"development_prompts/enhanced_prompt_{diagram_type}_{timestamp}.md"
    
    # Create directory if it doesn't exist
    os.makedirs("development_prompts", exist_ok=True)
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(prompt)
            
            # Add metadata as comments
            f.write(f"\n\n<!--\n")
            f.write(f"Metadata:\n")
            f.write(f"- Diagram Type: {diagram_type}\n")
            f.write(f"- Topics: {topics}\n")
            f.write(f"- Style Preferences: {style_preferences}\n")
            f.write(f"- Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-->\n")
            
        logger.info(f"Enhanced development prompt saved to: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save enhanced development prompt: {e}")
        return None


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