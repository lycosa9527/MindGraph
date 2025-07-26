"""
LangChain Agent Module for D3.js_Dify

This module contains the core LangChain agent functionality for generating
custom graph content using the Qwen LLM. It supports both double bubble maps
(comparison of two topics) and bubble maps (single topic with characteristics).
The agent uses LLM-based prompt analysis to classify the user's intent and
generates the appropriate JSON spec and D3.js code block for the selected
graph type.
"""

import os
import logging
import re
from dotenv import load_dotenv
load_dotenv()

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/agent.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

from langchain.llms.base import LLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import requests
import yaml
from config import config
from agent_utils import (
    extract_topics_with_agent,
    generate_characteristics_with_agent,
    parse_characteristics_result,
    detect_language
)
# Modular agent for D3.js graph generation
# Provides LLM-based graph type detection and JSON spec generation for D3.js rendering
from graph_specs import (
    validate_double_bubble_map,
    validate_bubble_map,
    validate_circle_map,
    validate_tree_map,
    validate_concept_map,
    validate_mindmap
)
import json
from diagram_styles import parse_style_from_prompt


class QwenLLM(LLM):
    """
    Custom LangChain LLM wrapper for Qwen API
    """
    def _call(self, prompt, stop=None):
        logger.info(f"QwenLLM._call() - Model: {config.QWEN_MODEL}")
        logger.debug(f"Prompt sent to Qwen:\n{prompt[:1000]}{'...' if len(prompt) > 1000 else ''}")

        headers = config.get_qwen_headers()
        data = config.get_qwen_data(prompt)

        logger.info(f"Making request to: {config.QWEN_API_URL}")
        try:
            resp = requests.post(
                config.QWEN_API_URL,
                headers=headers,
                json=data
            )
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"QwenLLM response received - Length: {len(content)} characters")
            logger.debug(f"Qwen Output:\n{content[:1000]}{'...' if len(content) > 1000 else ''}")
            return content
        except Exception as e:
            logger.error(f"QwenLLM API call failed: {e}", exc_info=True)
            raise

    @property
    def _llm_type(self):
        return "qwen"


# Initialize the LLM instance
llm = QwenLLM()


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

# Topic Extraction Prompts
topic_extraction_prompt_en = PromptTemplate(
    input_variables=["user_prompt"],
    template="""
TASK: Extract exactly two topics from the user's request.

User request: {user_prompt}

RULES:
1. Find exactly TWO nouns/concepts that can be compared
2. Ignore words like "compare", "generate", "create", "show", "about", "between"
3. Output ONLY: "topic1 and topic2"
4. NO code blocks, NO explanations, NO additional text

Examples:
Input: "Compare cats and dogs" → Output: "cats and dogs"
Input: "Generate diagram about BMW vs Mercedes" → Output: "BMW and Mercedes"
Input: "Create comparison between apple and orange" → Output: "apple and orange"

Your output (only the two topics):
"""
)

topic_extraction_prompt_zh = PromptTemplate(
    input_variables=["user_prompt"],
    template="""
任务：从用户请求中提取恰好两个主题。

用户请求: {user_prompt}

规则：
1. 找到恰好两个可以比较的名词/概念
2. 忽略"比较"、"生成"、"创建"、"显示"、"关于"、"之间"等词
3. 只输出："主题1和主题2"
4. 不要代码块，不要解释，不要额外文字

示例：
输入："比较猫和狗" → 输出："猫和狗"
输入："生成关于宝马和奔驰的图表" → 输出："宝马和奔驰"
输入："创建苹果和橙子的比较" → 输出："苹果和橙子"

你的输出（只输出两个主题）：
"""
)

# Characteristics Generation Prompts
characteristics_prompt_en = PromptTemplate(
    input_variables=["topic1", "topic2"],
    template="""
Compare {topic1} and {topic2} with concise keywords for similarities and differences.

Goal: Cultivate students’ comparative thinking skills, enabling multi-dimensional analysis of shared traits and unique features.

Requirements:
- 5 common characteristics (shared by both) - use 2-4 words maximum
- 5 unique characteristics for {topic1} - use 2-4 words maximum  
- 5 unique characteristics for {topic2} - use 2-4 words maximum
- CRITICAL: ensure comparability – each difference must represent the same type of attribute directly comparable between {topic1} and {topic2}
- Use single words or very short phrases
- Cover diverse dimensions without repetition
- Focus on core, essential distinctions
- Highly abstract and condensed

Style Guidelines:
- Differences must be parallel: trait 1 for {topic1} matches trait 1 for {topic2}, etc.
- Maximum 4 words per characteristic
- Use nouns, adjectives, or short noun phrases
- Avoid verbs and complex descriptions
- Focus on fundamental, universal traits
- Be concise and memorable


Comparable Categories Examples:
- Geographic: location, terrain, climate
- Economic: industry, economy type, development level
- Cultural: lifestyle, traditions, values
- Physical: size, population, resources
- Temporal: history, age, development stage

Output ONLY the YAML content, no code block markers, no explanations:

similarities:
  - "trait1"
  - "trait2"
  - "trait3"
  - "trait4"
  - "trait5"
left_differences:
  - "feature1"
  - "feature2"
  - "feature3"
  - "feature4"
  - "feature5"
right_differences:
  - "feature1"
  - "feature2"
  - "feature3"
  - "feature4"
  - "feature5"
"""
)

characteristics_prompt_zh = PromptTemplate(
    input_variables=["topic1", "topic2"],
    template="""
对比{topic1}和{topic2}，并用简洁的关键词来概括相同点和不同点。

目的：培养学生的对比思维技能，能够从多个维度分析两个事物的共性与特性。

要求：
- 5个共同特征(两者共有)
- 5个{topic1}的独有特征 
- 5个{topic2}的独有特征
- 关键：使差异具有可比性 - 每个差异应代表可以在{topic1}和{topic2}之间直接比较的相同类型的特征/属性
- 使用关键词或极短短语，高度概括和抽象，保持简洁性
- 对比的维度要丰富，不要重复
- 专注于核心、本质差异

风格指导：
- 不同点要一一对应，确保差异遵循平行类别，如{topic1}的特征1要与{topic2}的特征1相对应，以此类推。
- 避免复杂描述
- 简洁且易记

可比类别示例：
- 地理：位置、地形、气候
- 经济：产业、经济类型、发展水平
- 文化：生活方式、传统、价值观
- 物理：规模、人口、资源
- 时间：历史、年龄、发展阶段

只输出YAML内容，不要代码块标记，不要解释：

similarities:
  - "特征1"
  - "特征2"
  - "特征3"
  - "特征4"
  - "特征5"
left_differences:
  - "特点1"
  - "特点2"
  - "特点3"
  - "特点4"
  - "特点5"
right_differences:
  - "特点1"
  - "特点2"
  - "特点3"
  - "特点4"
  - "特点5"
"""
)


# ============================================================================
# LANGCHAIN CHAINS
# ============================================================================

def create_topic_extraction_chain(language='zh'):
    """
    Create a LangChain RunnableSequence for topic extraction
    Args:
        language (str): Language for the prompt ('zh' or 'en')
    Returns:
        RunnableSequence: Configured sequence for topic extraction
    """
    prompt = topic_extraction_prompt_zh if language == 'zh' else topic_extraction_prompt_en
    # Return a RunnableSequence (prompt | llm)
    return prompt | llm


def create_characteristics_chain(language='zh'):
    """
    Create a LangChain RunnableSequence for characteristics generation
    Args:
        language (str): Language for the prompt ('zh' or 'en')
    Returns:
        RunnableSequence: Configured sequence for characteristics generation
    """
    prompt = characteristics_prompt_zh if language == 'zh' else characteristics_prompt_en
    # Return a RunnableSequence (prompt | llm)
    return prompt | llm


# ============================================================================
# AGENT WORKFLOW FUNCTIONS
# ============================================================================

def extract_yaml_from_code_block(text):
    """
    Remove code block markers (e.g., ```yaml ... ```) from LLM output before YAML parsing.
    """
    match = re.match(r"^```(?:yaml)?\s*\n(.*?)\n```$", text.strip(), re.DOTALL)
    if match:
        return match.group(1)
    return text.strip()

def classify_graph_type_with_llm(user_prompt: str, language: str = 'zh') -> str:
    """
    Use the LLM to classify the user's intent as 'double_bubble_map', 'bubble_map', or 'circle_map'.
    
    Args:
        user_prompt: The user's input prompt
        language: Language for processing ('zh' or 'en')
    
    Returns:
        str: 'double_bubble_map', 'bubble_map', or 'circle_map'
    """
    # LLM prompt logic for type detection
    if language == 'zh':
        prompt_text = (
            "你是一个图谱类型分类助手。根据用户的需求，判断他们是想要比较两个主题（输出double_bubble_map）、分析一个主题的特征（输出bubble_map），还是想要一个圆圈图（输出circle_map）。\n"
            "\n【规则】\n"
            "- 如果用户想要比较、对比、区分、分析两个不同的主题，请输出 double_bubble_map。\n"
            "- 如果用户只关注一个主题，想要分析其特征、属性、优缺点等，请输出 bubble_map。\n"
            "- 如果用户明确要求圆圈图、circle map、中心大圆、内部小圆等，请输出 circle_map。\n"
            "- 只输出 'double_bubble_map'、'bubble_map' 或 'circle_map'，不要输出其他内容。\n"
            "\n【示例】\n"
            "用户需求：比较猫和狗\n输出：double_bubble_map\n"
            "用户需求：画一个关于绿茶婊的气泡图\n输出：bubble_map\n"
            "用户需求：画一个主题为太阳系的circle map\n输出：circle_map\n"
            "用户需求：中心大圆，内部有小圆，描述苹果的特征\n输出：circle_map\n"
            "\n用户需求：{user_prompt}\n你的输出："
        )
    else:
        prompt_text = (
            "You are a diagram type classifier. Based on the user's request, determine if they want to compare two topics (output double_bubble_map), analyze the characteristics of a single topic (output bubble_map), or want a circle map (output circle_map).\n"
            "\n[Rules]\n"
            "- If the user wants to compare, contrast, distinguish, or analyze two different topics, output double_bubble_map.\n"
            "- If the user is only interested in one topic and wants to analyze its features, attributes, pros/cons, etc., output bubble_map.\n"
            "- If the user explicitly requests a circle map, big circle in the center, small circles inside, etc., output circle_map.\n"
            "- Only output 'double_bubble_map', 'bubble_map', or 'circle_map', nothing else.\n"
            "\n[Examples]\n"
            "User request: Compare cats and dogs\nOutput: double_bubble_map\n"
            "User request: Draw a bubble map about green tea\nOutput: bubble_map\n"
            "User request: Draw a circle map for the solar system\nOutput: circle_map\n"
            "User request: Big circle in the center, small circles inside, describe apple's features\nOutput: circle_map\n"
            "\nUser request: {user_prompt}\nYour output:"
        )
    prompt = PromptTemplate(
        input_variables=["user_prompt"],
        template=prompt_text
    )
    # Refactored: Use RunnableSequence API
    result = (prompt | llm).invoke({"user_prompt": user_prompt}).strip().lower()
    if "circle_map" in result:
        return "circle_map"
    if "bubble_map" in result and "double_bubble_map" not in result:
        return "bubble_map"
    elif "double_bubble_map" in result:
        return "double_bubble_map"
    # fallback: guess by keywords
    if any(word in user_prompt.lower() for word in ["circle map", "中心大圆", "内部小圆", "big circle", "small circles inside"]):
        return "circle_map"
    if any(word in user_prompt.lower() for word in ["compare", "vs", "difference", "区别", "对比"]):
        return "double_bubble_map"
    return "bubble_map"


# Removed duplicate function - using classify_graph_type_with_llm instead


def generate_graph_spec(user_prompt: str, graph_type: str, language: str = 'zh') -> dict:
    """
    Use the LLM to generate a JSON spec for the given graph type.
    
    Args:
        user_prompt: The user's input prompt
        graph_type: Type of graph to generate ('double_bubble_map', 'bubble_map', etc.)
        language: Language for processing ('zh' or 'en')
    
    Returns:
        dict: JSON serializable graph specification
    """
    # LLM prompt logic for each graph type, modularized
    if graph_type == "double_bubble_map":
        prompt_text = (
            "请为以下用户需求生成一个双气泡图的JSON规范。\n"
            "需求：{user_prompt}\n"
            "请输出一个包含以下字段的JSON对象：\n"
            "left: \"主题1\"\n"
            "right: \"主题2\"\n"
            "similarities: [\"特征1\", \"特征2\", \"特征3\", \"特征4\", \"特征5\"]\n"
            "left_differences: [\"特点1\", \"特点2\", \"特点3\", \"特点4\", \"特点5\"]\n"
            "right_differences: [\"特点1\", \"特点2\", \"特点3\", \"特点4\", \"特点5\"]\n"
            "要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。\n"
            "请确保JSON格式正确，不要包含任何代码块标记。\n"
        ) if language == 'zh' else (
            "Please generate a JSON specification for a double bubble map for the following user request.\n"
            "Request: {user_prompt}\n"
            "Please output a JSON object containing the following fields:\n"
            "left: \"Topic1\"\n"
            "right: \"Topic2\"\n"
            "similarities: [\"Feature1\", \"Feature2\", \"Feature3\", \"Feature4\", \"Feature5\"]\n"
            "left_differences: [\"Feature1\", \"Feature2\", \"Feature3\", \"Feature4\", \"Feature5\"]\n"
            "right_differences: [\"Feature1\", \"Feature2\", \"Feature3\", \"Feature4\", \"Feature5\"]\n"
            "Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.\n"
            "Please ensure the JSON format is correct, do not include any code block markers.\n"
        )
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=prompt_text
        )
        yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
        yaml_text_clean = extract_yaml_from_code_block(yaml_text)
        try:
            spec = yaml.safe_load(yaml_text_clean)
            if not spec or "left" not in spec or "right" not in spec or "similarities" not in spec or "left_differences" not in spec or "right_differences" not in spec:
                raise Exception("YAML parse failed or JSON structure incorrect")
            # Optionally use graph_specs.py for schema/validation
            valid, msg = validate_double_bubble_map(spec)
            if not valid:
                raise Exception(f"Generated JSON does not match double bubble map schema: {msg}")
        except Exception as e:
            logger.error(f"Agent: Double bubble map JSON generation failed: {e}")
            spec = {"error": "Failed to generate valid double bubble map JSON"}
        return spec
    elif graph_type == "circle_map":
        prompt_text = (
            "请为以下用户需求生成一个圆圈图的JSON规范。\n"
            "需求：{user_prompt}\n"
            "请输出一个包含以下字段的JSON对象：\n"
            "topic: \"主题\"\n"
            "context: [\"特征1\", \"特征2\", \"特征3\", \"特征4\", \"特征5\", \"特征6\"]\n"
            "要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。\n"
            "请确保JSON格式正确，不要包含任何代码块标记。\n"
        ) if language == 'zh' else (
            "Please generate a JSON specification for a circle map for the following user request.\n"
            "Request: {user_prompt}\n"
            "Please output a JSON object containing the following fields:\n"
            "topic: \"Topic\"\n"
            "context: [\"Feature1\", \"Feature2\", \"Feature3\", \"Feature4\", \"Feature5\", \"Feature6\"]\n"
            "Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.\n"
            "Please ensure the JSON format is correct, do not include any code block markers.\n"
        )
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=prompt_text
        )
        yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
        yaml_text_clean = extract_yaml_from_code_block(yaml_text)
        
        # Debug: Log the raw response
        logger.debug(f"Raw Qwen response for circle_map: {yaml_text}")
        logger.debug(f"Cleaned response: {yaml_text_clean}")
        
        try:
            # Try JSON first, then YAML as fallback
            try:
                spec = json.loads(yaml_text_clean)
            except json.JSONDecodeError:
                spec = yaml.safe_load(yaml_text_clean)
            
            if not spec or "topic" not in spec or "context" not in spec:
                logger.error(f"Generated spec missing required fields: {spec}")
                raise Exception("YAML/JSON parse failed or structure incorrect")
            
            # Optionally use graph_specs.py for schema/validation
            valid, msg = validate_circle_map(spec)
            if not valid:
                raise Exception(f"Generated JSON does not match circle map schema: {msg}")
        except Exception as e:
            logger.error(f"Agent: Circle map JSON generation failed: {e}")
            spec = {"error": "Failed to generate valid circle map JSON"}
        return spec
    elif graph_type == "bubble_map":
        prompt_text = (
            "请为以下用户需求生成一个气泡图的JSON规范。\n"
            "需求：{user_prompt}\n"
            "请输出一个包含以下字段的JSON对象：\n"
            "topic: \"主题\"\n"
            "attributes: [\"特征1\", \"特征2\", \"特征3\", \"特征4\", \"特征5\", \"特征6\", \"特征7\", \"特征8\"]\n"
            "要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。\n"
            "请确保JSON格式正确，不要包含任何代码块标记。\n"
        ) if language == 'zh' else (
            "Please generate a JSON specification for a bubble map for the following user request.\n"
            "Request: {user_prompt}\n"
            "Please output a JSON object containing the following fields:\n"
            "topic: \"Topic\"\n"
            "attributes: [\"Feature1\", \"Feature2\", \"Feature3\", \"Feature4\", \"Feature5\", \"Feature6\", \"Feature7\", \"Feature8\"]\n"
            "Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.\n"
            "Please ensure the JSON format is correct, do not include any code block markers.\n"
        )
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=prompt_text
        )
        yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
        yaml_text_clean = extract_yaml_from_code_block(yaml_text)
        logger.debug(f"Raw Qwen response for bubble_map: {yaml_text}")
        logger.debug(f"Cleaned response: {yaml_text_clean}")
        try:
            # Try JSON first, then YAML as fallback
            try:
                spec = json.loads(yaml_text_clean)
            except json.JSONDecodeError:
                spec = yaml.safe_load(yaml_text_clean)
            if not spec or "topic" not in spec or "attributes" not in spec:
                logger.error(f"Generated spec missing required fields: {spec}")
                raise Exception("YAML/JSON parse failed or structure incorrect")
            # Use graph_specs.py for schema/validation
            valid, msg = validate_bubble_map(spec)
            if not valid:
                raise Exception(f"Generated JSON does not match bubble map schema: {msg}")
        except Exception as e:
            logger.error(f"Agent: Bubble map JSON generation failed: {e}")
            spec = {"error": "Failed to generate valid bubble map JSON"}
        return spec
    elif graph_type == "tree_map":
        prompt_text = (
            "请为以下用户需求生成一个树形图的JSON规范。\n"
            "需求：{user_prompt}\n"
            "请输出一个包含以下字段的JSON对象：\n"
            "topic: \"主题\"\n"
            "children: [{\"name\": \"子主题1\", \"children\": [{\"name\": \"子主题1.1\"}]}]\n"
            "请确保JSON格式正确，不要包含任何代码块标记。\n"
        ) if language == 'zh' else (
            "Please generate a JSON specification for a tree map for the following user request.\n"
            "Request: {user_prompt}\n"
            "Please output a JSON object containing the following fields:\n"
            "topic: \"Topic\"\n"
            "children: [{\"name\": \"Subtopic1\", \"children\": [{\"name\": \"Subtopic1.1\"}]}]\n"
            "Please ensure the JSON format is correct, do not include any code block markers.\n"
        )
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=prompt_text
        )
        yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
        yaml_text_clean = extract_yaml_from_code_block(yaml_text)
        try:
            spec = yaml.safe_load(yaml_text_clean)
            if not spec or "topic" not in spec or "children" not in spec:
                raise Exception("YAML parse failed or JSON structure incorrect")
            # Optionally use graph_specs.py for schema/validation
            valid, msg = validate_tree_map(spec)
            if not valid:
                raise Exception(f"Generated JSON does not match tree map schema: {msg}")
        except Exception as e:
            logger.error(f"Agent: Tree map JSON generation failed: {e}")
            spec = {"error": "Failed to generate valid tree map JSON"}
        return spec
    elif graph_type == "concept_map":
        prompt_text = (
            "请为以下用户需求生成一个概念图的JSON规范。\n"
            "需求：{user_prompt}\n"
            "请输出一个包含以下字段的JSON对象：\n"
            "topic: \"主题\"\n"
            "concepts: [{\"name\": \"概念1\", \"children\": [{\"name\": \"概念1.1\"}]}]\n"
            "请确保JSON格式正确，不要包含任何代码块标记。\n"
        ) if language == 'zh' else (
            "Please generate a JSON specification for a concept map for the following user request.\n"
            "Request: {user_prompt}\n"
            "Please output a JSON object containing the following fields:\n"
            "topic: \"Topic\"\n"
            "concepts: [{\"name\": \"Concept1\", \"children\": [{\"name\": \"Concept1.1\"}]}]\n"
            "Please ensure the JSON format is correct, do not include any code block markers.\n"
        )
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=prompt_text
        )
        yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
        yaml_text_clean = extract_yaml_from_code_block(yaml_text)
        try:
            spec = yaml.safe_load(yaml_text_clean)
            if not spec or "topic" not in spec or "concepts" not in spec:
                raise Exception("YAML parse failed or JSON structure incorrect")
            # Optionally use graph_specs.py for schema/validation
            valid, msg = validate_concept_map(spec)
            if not valid:
                raise Exception(f"Generated JSON does not match concept map schema: {msg}")
        except Exception as e:
            logger.error(f"Agent: Concept map JSON generation failed: {e}")
            spec = {"error": "Failed to generate valid concept map JSON"}
        return spec
    elif graph_type == "mindmap":
        prompt_text = (
            "请为以下用户需求生成一个思维导图的JSON规范。\n"
            "需求：{user_prompt}\n"
            "请输出一个包含以下字段的JSON对象：\n"
            "topic: \"主题\"\n"
            "children: [{\"name\": \"子主题1\", \"children\": [{\"name\": \"子主题1.1\"}]}]\n"
            "请确保JSON格式正确，不要包含任何代码块标记。\n"
        ) if language == 'zh' else (
            "Please generate a JSON specification for a mind map for the following user request.\n"
            "Request: {user_prompt}\n"
            "Please output a JSON object containing the following fields:\n"
            "topic: \"Topic\"\n"
            "children: [{\"name\": \"Subtopic1\", \"children\": [{\"name\": \"Subtopic1.1\"}]}]\n"
            "Please ensure the JSON format is correct, do not include any code block markers.\n"
        )
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=prompt_text
        )
        yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
        yaml_text_clean = extract_yaml_from_code_block(yaml_text)
        try:
            spec = yaml.safe_load(yaml_text_clean)
            if not spec or "topic" not in spec or "children" not in spec:
                raise Exception("YAML parse failed or JSON structure incorrect")
            # Optionally use graph_specs.py for schema/validation
            valid, msg = validate_mindmap(spec)
            if not valid:
                raise Exception(f"Generated JSON does not match mind map schema: {msg}")
        except Exception as e:
            logger.error(f"Agent: Mind map JSON generation failed: {e}")
            spec = {"error": "Failed to generate valid mind map JSON"}
        return spec
    else:
        return {"error": f"Unsupported graph type: {graph_type}"}


def agent_graph_workflow(user_prompt, language='zh'):
    """
    Main agent workflow for graph generation (bubble, double bubble, or circle map)
    Args:
        user_prompt (str): User's input prompt
        language (str): Language for processing ('zh' or 'en')
    Returns:
        dict: JSON specification for D3.js rendering
    """
    logger.info(f"Agent: Starting graph workflow for: {user_prompt}")
    try:
        graph_type = classify_graph_type_with_llm(user_prompt, language)
        logger.info(f"Agent: Classified graph type: {graph_type}")
        if graph_type == "double_bubble_map":
            # Step 1: Extract topics using agent
            topic1, topic2 = extract_topics_with_agent(user_prompt, language)
            logger.info(f"Agent: Extracted topics: {topic1} vs {topic2}")
            # Step 2: Generate characteristics using agent
            spec = generate_characteristics_with_agent(topic1, topic2, language)
            logger.info(f"Agent: Generated characteristics: {spec}")
            final_spec = {
                "left": topic1,
                "right": topic2,
                "similarities": spec.get("similarities", []),
                "left_differences": spec.get("left_differences", []),
                "right_differences": spec.get("right_differences", [])
            }
            # Return JSON specification for D3.js rendering
            result = final_spec
            logger.info(f"Agent: Double bubble workflow completed successfully")
            return result
        elif graph_type == "circle_map":
            # circle_map: extract topic and characteristics
            from langchain.prompts import PromptTemplate
            prompt_text = (
                "请从以下用户需求中提取主题，并列出6-10个最重要的特征（可以是名词或形容词，描述主题的性质、组成或状态），输出YAML格式：\n"
                "topic: <主题>\ncharacteristics:\n  - <特征1>\n  - <特征2>\n  - <特征3>\n  - <特征4>\n  - <特征5>\n  - <特征6>\n用户需求：{user_prompt}\n示例：\n用户需求：画一个关于太阳系的circle map\ntopic: 太阳系\ncharacteristics:\n  - 太阳\n  - 行星\n  - 卫星\n  - 小行星\n  - 彗星\n  - 星云"
            ) if language == 'zh' else (
                "Extract the main topic and list 6-10 most important characteristics (nouns or adjectives describing the topic's qualities, components, or states). Output in YAML format:\n"
                "topic: <topic>\ncharacteristics:\n  - <characteristic1>\n  - <characteristic2>\n  - <characteristic3>\n  - <characteristic4>\n  - <characteristic5>\n  - <characteristic6>\nUser request: {user_prompt}\nExample:\nUser request: Draw a circle map for the solar system\ntopic: Solar System\ncharacteristics:\n  - Sun\n  - Planets\n  - Moons\n  - Asteroids\n  - Comets\n  - Nebula"
            )
            prompt = PromptTemplate(
                input_variables=["user_prompt"],
                template=prompt_text
            )
            yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
            yaml_text_clean = extract_yaml_from_code_block(yaml_text)
            try:
                spec = yaml.safe_load(yaml_text_clean)
                if not spec or "topic" not in spec or "characteristics" not in spec:
                    raise Exception("YAML parse failed")
            except Exception as e:
                logger.error(f"Agent: Circle map YAML parse failed: {e}")
                spec = {"topic": "主题", "characteristics": ["特征1", "特征2", "特征3", "特征4", "特征5"]}
            # Return JSON specification for D3.js rendering
            result = spec
            logger.info(f"Agent: Circle map workflow completed successfully")
            return result
        else:
            # bubble_map: extract topic and characteristics
            from langchain.prompts import PromptTemplate
            prompt_text = (
                "请从以下用户需求中提取主题，并列出6或8个最重要的特征（必须是形容词，描述主题的性质或状态），均匀分为左右两组，每组3或4个，输出YAML格式：\n"
                "topic: <主题>\nleft:\n  - <左侧形容词1>\n  - <左侧形容词2>\n  - <左侧形容词3>\n  - <左侧形容词4>\nright:\n  - <右侧形容词1>\n  - <右侧形容词2>\n  - <右侧形容词3>\n  - <右侧形容词4>\n用户需求：{user_prompt}\n示例：\n用户需求：描述一所顶尖大学的气泡图\ntopic: 顶尖大学\nleft:\n  - 国际化\n  - 创新性\n  - 多元化\n  - 竞争激烈\nright:\n  - 学术卓越\n  - 资源丰富\n  - 师资雄厚\n  - 环境优美"
            ) if language == 'zh' else (
                "Extract the main topic and list 6 or 8 most important characteristics (they must be adjectives describing the topic's qualities or states), evenly distributed into left and right groups (3 or 4 each). Output in YAML format:\n"
                "topic: <topic>\nleft:\n  - <left_adjective1>\n  - <left_adjective2>\n  - <left_adjective3>\n  - <left_adjective4>\nright:\n  - <right_adjective1>\n  - <right_adjective2>\n  - <right_adjective3>\n  - <right_adjective4>\nUser request: {user_prompt}\nExample:\nUser request: Bubble map for a top university\ntopic: Top University\nleft:\n  - international\n  - innovative\n  - diverse\n  - competitive\nright:\n  - excellent\n  - resourceful\n  - prestigious\n  - beautiful"
            )
            prompt = PromptTemplate(
                input_variables=["user_prompt"],
                template=prompt_text
            )
            yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
            yaml_text_clean = extract_yaml_from_code_block(yaml_text)
            try:
                spec = yaml.safe_load(yaml_text_clean)
                if not spec or "topic" not in spec or "left" not in spec or "right" not in spec:
                    raise Exception("YAML parse failed")
            except Exception as e:
                logger.error(f"Agent: Bubble map YAML parse failed: {e}")
                spec = {"topic": "主题", "left": ["特征1", "特征2", "特征3", "特征4"], "right": ["特征5", "特征6", "特征7", "特征8"]}
            # Return JSON specification for D3.js rendering
            result = spec
            logger.info(f"Agent: Bubble map workflow completed successfully")
            return result
    except Exception as e:
        logger.error(f"Agent: Workflow failed: {e}")
        # Return JSON specification for D3.js rendering
        result = {"topic": "主题", "characteristics": ["特征1", "特征2", "特征3", "特征4", "特征5"]}
        return result


# ============================================================================
# AGENT CONFIGURATION
# ============================================================================

def get_agent_config():
    """
    Get current agent configuration
    
    Returns:
        dict: Agent configuration
    """
    return {
        "llm_model": config.QWEN_MODEL,
        "llm_url": config.QWEN_API_URL,
        "temperature": config.QWEN_TEMPERATURE,
        "max_tokens": config.QWEN_MAX_TOKENS,
        "default_language": config.GRAPH_LANGUAGE
    }


import threading
import time

def validate_agent_setup():
    """
    Validate that the agent is properly configured with cross-platform timeout
    
    Returns:
        bool: True if agent is ready, False otherwise
    """
    def timeout_handler():
        raise TimeoutError("LLM validation timed out")
    
    timer = threading.Timer(config.QWEN_TIMEOUT, timeout_handler)
    timer.start()
    
    try:
        # Test LLM connection
        test_prompt = "Test"
        llm._call(test_prompt)
        logger.info("Agent: LLM connection validated")
        return True
    except TimeoutError:
        logger.error("Agent: LLM validation timed out")
        return False
    except Exception as e:
        logger.error(f"Agent: LLM connection failed: {e}")
        return False
    finally:
        timer.cancel() 


def extract_topics_and_styles_from_prompt_qwen(user_prompt: str, language: str = 'en') -> dict:
    """
    Use Qwen to extract both topics and style preferences from user prompt in a single pass.
    Fallback to hardcoded parser if extraction fails.
    Returns a dict with 'topics', 'style_preferences', and 'diagram_type'.
    """
    from langchain.prompts import PromptTemplate
    def get_default_result():
        return {
            "topics": [],
            "style_preferences": {},
            "diagram_type": "bubble_map"
        }
    def clean_llm_response(result):
        cleaned = result.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        return cleaned.strip()
    def validate_and_parse_json(json_str):
        try:
            parsed = json.loads(json_str)
            if not isinstance(parsed, dict):
                return None
            return parsed
        except (json.JSONDecodeError, TypeError):
            return None
    # Input validation
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        return get_default_result()
    if language not in ['zh', 'en']:
        language = 'en'
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
- bridge_map: 显示类比和相似性
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
        cleaned_result = clean_llm_response(result)
        parsed_result = validate_and_parse_json(cleaned_result)
        if not parsed_result:
            return get_default_result()
        style_prefs = parsed_result.get("style_preferences", {})
        if not isinstance(style_prefs, dict):
            style_prefs = {}
        validated_result = {
            "topics": parsed_result.get("topics", []),
            "style_preferences": style_prefs,
            "diagram_type": parsed_result.get("diagram_type", "bubble_map")
        }
        return validated_result
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.error(f"JSON parsing failed in enhanced extraction: {e}")
        return get_default_result()
    except Exception as e:
        logger.error(f"Unexpected error in enhanced extraction: {e}")
        return get_default_result() 