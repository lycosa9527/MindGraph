"""
Prompt templates and chain creation functions.

This module provides prompt templates for topic extraction and characteristics
generation, along with LangChain chain creation functions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from langchain_core.prompts import PromptTemplate

from agents.core.llm_clients import llm_classification, llm_generation


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
2. 忽略"比较"、"创建"、"显示"、"关于"、"之间"等词
3. 只输出："主题1和主题2"
4. 不要代码块，不要解释，不要额外文字

示例：
输入："比较猫和狗" → 输出："猫和狗"
输入："生成关于宝马和奔驰的图表" → 输出："生成关于宝马和奔驰"
输入："创建苹果和橙子的比较" → 输出："苹果和橙子"

你的输出（只输出两个主题）：
"""
)

# Characteristics Generation Prompts
characteristics_prompt_en = PromptTemplate(
    input_variables=["topic1", "topic2"],
    template="""
Compare {topic1} and {topic2} with concise keywords for similarities and differences.

Goal: Cultivate students' comparative thinking skills, enabling multi-dimensional analysis of shared traits and unique features.

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


def create_topic_extraction_chain(language='zh'):
    """
    Create a simple chain for topic extraction
    Args:
        language (str): Language for the prompt ('zh' or 'en')
    Returns:
        function: Function that can be called with user_prompt
    """
    prompt = topic_extraction_prompt_zh if language == 'zh' else topic_extraction_prompt_en

    def extract_topics(user_prompt: str) -> str:
        """Extract topics using the classification model"""
        formatted_prompt = prompt.format(user_prompt=user_prompt)
        result = llm_classification.invoke(formatted_prompt)
        if not isinstance(result, str):
            return str(result)
        return result

    return extract_topics


def create_characteristics_chain(language='zh'):
    """
    Create a simple chain for characteristics generation
    Args:
        language (str): Language for the prompt ('zh' or 'en')
    Returns:
        function: Function that can be called with topic1 and topic2
    """
    prompt = characteristics_prompt_zh if language == 'zh' else characteristics_prompt_en

    def generate_characteristics(topic1: str, topic2: str) -> str:
        """Generate characteristics using the generation model"""
        formatted_prompt = prompt.format(topic1=topic1, topic2=topic2)
        result = llm_generation.invoke(formatted_prompt)
        if not isinstance(result, str):
            return str(result)
        return result

    return generate_characteristics
