"""
LangChain Agent Module for MindGraph

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
    Use the LLM to classify the user's intent into the appropriate diagram type.
    
    Args:
        user_prompt: The user's input prompt
        language: Language for processing ('zh' or 'en')
    
    Returns:
        str: Diagram type from available types
    """
    # Get available diagram types
    from prompts import get_available_diagram_types
    available_types = get_available_diagram_types()
    
    # LLM prompt logic for type detection
    if language == 'zh':
        prompt_text = (
            "你是一个图谱类型分类助手。根据用户的需求，判断他们想要创建哪种类型的图表。\n"
            "\n【可用图表类型】\n"
            "# 思维导图 (Thinking Maps)\n"
            "- double_bubble_map: 比较和对比两个主题\n"
            "- bubble_map: 描述单个主题的特征\n"
            "- circle_map: 在上下文中定义主题\n"
            "- flow_map: 序列事件或过程\n"
            "- brace_map: 显示整体/部分关系\n"
            "- tree_map: 分类和归类信息\n"
            "- multi_flow_map: 显示因果关系\n"
            "- bridge_map: 桥形图 - 显示类比和相似性\n"
            "\n"
            "# 概念图 (Concept Maps)\n"
            "- concept_map: 显示概念之间的关系\n"
            "- semantic_web: 创建相关概念的网络\n"
            "\n"
            "# 思维导图 (Mind Maps)\n"
            "- mindmap: 围绕中心主题组织想法\n"
            "- radial_mindmap: 创建径向思维导图结构\n"
            "\n"
            "# 常用图表 (Common Diagrams)\n"
            "- venn_diagram: 显示重叠集合\n"
            "- fishbone_diagram: 分析因果关系\n"
            "- flowchart: 显示流程过程\n"
            "- org_chart: 显示组织结构\n"
            "- timeline: 显示时间顺序事件\n"
            "\n【重要区分】\n"
            "- 比较/对比 (compare/contrast): 使用 double_bubble_map\n"
            "- 类比 (analogy): 使用 bridge_map\n"
            "- 概念关系 (concept relationships): 使用 concept_map\n"
            "- 思维组织 (idea organization): 使用 mindmap\n"
            "\n【规则】\n"
            "- 仔细分析用户的需求和意图\n"
            "- 选择最适合的图表类型\n"
            "- 只输出图表类型名称，不要其他内容\n"
            "- 必须使用下划线格式，如：double_bubble_map, bubble_map, bridge_map\n"
            "- 不要使用空格或连字符，如：不要写 'double bubble map' 或 'double-bubble-map'\n"
            "\n【示例】\n"
            "用户需求：比较猫和狗\n输出：double_bubble_map\n"
            "用户需求：生成一幅关于风电和水电的双气泡图\n输出：double_bubble_map\n"
            "用户需求：制作双气泡图比较城市和乡村\n输出：double_bubble_map\n"
            "用户需求：双气泡图：比较传统能源和可再生能源\n输出：double_bubble_map\n"
            "用户需求：类比：手之于人，如同轮子之于车\n输出：bridge_map\n"
            "用户需求：用桥形图类比光合作用和呼吸作用\n输出：bridge_map\n"
            "用户需求：描述太阳系的特征\n输出：bubble_map\n"
            "用户需求：展示水循环过程\n输出：flow_map\n"
            "用户需求：分析全球变暖的原因和影响\n输出：multi_flow_map\n"
            "用户需求：创建概念图显示生态系统\n输出：concept_map\n"
            "用户需求：制作思维导图整理学习内容\n输出：mindmap\n"
            "用户需求：绘制维恩图比较三个集合\n输出：venn_diagram\n"
            "用户需求：制作鱼骨图分析问题原因\n输出：fishbone_diagram\n"
            "用户需求：绘制流程图说明操作步骤\n输出：flowchart\n"
            "用户需求：创建组织架构图\n输出：org_chart\n"
            "用户需求：制作时间线显示历史事件\n输出：timeline\n"
            "\n用户需求：{user_prompt}\n你的输出："
        )
    else:
        prompt_text = (
            "You are a diagram type classifier. Based on the user's request, determine which type of diagram they want to create.\n"
            "\n[Available Diagram Types]\n"
            "# Thinking Maps\n"
            "- double_bubble_map: Compare and contrast two topics\n"
            "- bubble_map: Describe attributes of a single topic\n"
            "- circle_map: Define a topic in context\n"
            "- flow_map: Sequence events or processes\n"
            "- brace_map: Show whole/part relationships\n"
            "- tree_map: Categorize and classify information\n"
            "- multi_flow_map: Show cause and effect relationships\n"
            "- bridge_map: Show analogies and similarities\n"
            "\n"
            "# Concept Maps\n"
            "- concept_map: Show relationships between concepts\n"
            "- semantic_web: Create a web of related concepts\n"
            "\n"
            "# Mind Maps\n"
            "- mindmap: Organize ideas around a central topic\n"
            "- radial_mindmap: Create a radial mind map structure\n"
            "\n"
            "# Common Diagrams\n"
            "- venn_diagram: Show overlapping sets\n"
            "- fishbone_diagram: Analyze cause and effect\n"
            "- flowchart: Show process flow\n"
            "- org_chart: Show organizational structure\n"
            "- timeline: Show chronological events\n"
            "\n[Important Distinctions]\n"
            "- Compare/contrast: use double_bubble_map\n"
            "- Analogy: use bridge_map\n"
            "- Concept relationships: use concept_map\n"
            "- Idea organization: use mindmap\n"
            "\n[Rules]\n"
            "- Carefully analyze the user's needs and intent\n"
            "- Choose the most appropriate diagram type\n"
            "- Output only the diagram type name, nothing else\n"
            "- Must use underscore format, e.g.: double_bubble_map, bubble_map, bridge_map\n"
            "- Do not use spaces or hyphens, e.g.: do not write 'double bubble map' or 'double-bubble-map'\n"
            "\n[Examples]\n"
            "User request: Compare cats and dogs\nOutput: double_bubble_map\n"
            "User request: Generate a double bubble map about wind power and hydropower\nOutput: double_bubble_map\n"
            "User request: Create double bubble map comparing cities and rural areas\nOutput: double_bubble_map\n"
            "User request: Double bubble map: compare traditional and renewable energy\nOutput: double_bubble_map\n"
            "User request: Analogy: hand is to person as wheel is to car\nOutput: bridge_map\n"
            "User request: Use bridge map to analogize photosynthesis and respiration\nOutput: bridge_map\n"
            "User request: Describe characteristics of solar system\nOutput: bubble_map\n"
            "User request: Show water cycle process\nOutput: flow_map\n"
            "User request: Analyze causes and effects of global warming\nOutput: multi_flow_map\n"
            "User request: Create concept map showing ecosystem relationships\nOutput: concept_map\n"
            "User request: Make mind map to organize study content\nOutput: mindmap\n"
            "User request: Draw Venn diagram comparing three sets\nOutput: venn_diagram\n"
            "User request: Create fishbone diagram to analyze problem causes\nOutput: fishbone_diagram\n"
            "User request: Draw flowchart showing operation steps\nOutput: flowchart\n"
            "User request: Create organizational chart\nOutput: org_chart\n"
            "User request: Make timeline showing historical events\nOutput: timeline\n"
            "\nUser request: {user_prompt}\nYour output:"
        )
    
    prompt = PromptTemplate(
        input_variables=["user_prompt"],
        template=prompt_text
    )
    
    try:
        # Refactored: Use RunnableSequence API
        result = (prompt | llm).invoke({"user_prompt": user_prompt}).strip().lower()
        
        logger.info(f"LLM classification response: '{result}'")
        
        # First, try exact match with available types
        for diagram_type in available_types:
            if diagram_type == result:
                logger.info(f"LLM classified as: {diagram_type}")
                return diagram_type
        
        # If no exact match, try to extract from common variations
        result_clean = result.replace(" ", "_").replace("-", "_")
        for diagram_type in available_types:
            if diagram_type == result_clean:
                logger.info(f"LLM classified as (cleaned): {diagram_type}")
                return diagram_type
        
        # If still no match, try to infer from the response content
        if "double" in result and "bubble" in result:
            logger.info("LLM response suggests double_bubble_map")
            return "double_bubble_map"
        elif "bubble" in result:
            logger.info("LLM response suggests bubble_map")
            return "bubble_map"
        elif "bridge" in result:
            logger.info("LLM response suggests bridge_map")
            return "bridge_map"
        elif "circle" in result:
            logger.info("LLM response suggests circle_map")
            return "circle_map"
        elif "flow" in result:
            logger.info("LLM response suggests flow_map")
            return "flow_map"
        elif "tree" in result:
            logger.info("LLM response suggests tree_map")
            return "tree_map"
        elif "multi" in result and "flow" in result:
            logger.info("LLM response suggests multi_flow_map")
            return "multi_flow_map"
        elif "brace" in result:
            logger.info("LLM response suggests brace_map")
            return "brace_map"
        elif "concept" in result:
            logger.info("LLM response suggests concept_map")
            return "concept_map"
        elif "mind" in result:
            logger.info("LLM response suggests mindmap")
            return "mindmap"
        
        # Only if LLM completely fails, use fallback logic
        logger.warning(f"LLM classification failed to match any type, using fallback logic")
        if any(word in user_prompt.lower() for word in ["analogy", "analogize", "类比", "桥形图", "桥接图"]):
            return "bridge_map"
        elif any(word in user_prompt.lower() for word in ["compare", "vs", "difference", "对比", "比较", "双气泡图", "双泡图"]):
            return "double_bubble_map"
        elif any(word in user_prompt.lower() for word in ["describe", "characteristics", "特征", "描述", "气泡图", "单气泡图"]):
            return "bubble_map"
        elif any(word in user_prompt.lower() for word in ["define", "context", "定义", "上下文"]):
            return "circle_map"
        elif any(word in user_prompt.lower() for word in ["process", "steps", "流程", "步骤", "sequence"]):
            return "flow_map"
        elif any(word in user_prompt.lower() for word in ["whole", "part", "整体", "部分", "组成"]):
            return "brace_map"
        elif any(word in user_prompt.lower() for word in ["categorize", "classify", "分类", "归类"]):
            return "tree_map"
        elif any(word in user_prompt.lower() for word in ["cause", "effect", "原因", "影响", "因果"]):
            return "multi_flow_map"
        elif any(word in user_prompt.lower() for word in ["concept", "relationship", "概念", "关系"]):
            return "concept_map"
        elif any(word in user_prompt.lower() for word in ["semantic", "web", "语义", "网络"]):
            return "semantic_web"
        elif any(word in user_prompt.lower() for word in ["mind", "organize", "思维", "组织", "整理"]):
            return "mindmap"
        elif any(word in user_prompt.lower() for word in ["radial", "径向"]):
            return "radial_mindmap"
        elif any(word in user_prompt.lower() for word in ["venn", "overlap", "维恩", "重叠"]):
            return "venn_diagram"
        elif any(word in user_prompt.lower() for word in ["fishbone", "ishikawa", "鱼骨", "石川"]):
            return "fishbone_diagram"
        elif any(word in user_prompt.lower() for word in ["flowchart", "flow chart", "流程图"]):
            return "flowchart"
        elif any(word in user_prompt.lower() for word in ["org", "organization", "组织", "架构"]):
            return "org_chart"
        elif any(word in user_prompt.lower() for word in ["timeline", "time line", "时间线", "时间线"]):
            return "timeline"
        else:
            return "bubble_map"  # Default fallback
            
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        logger.info("Using fallback classification due to LLM error")
        # Fallback classification - only used when LLM completely fails
        if any(word in user_prompt.lower() for word in ["analogy", "analogize", "类比", "桥形图", "桥接图"]):
            return "bridge_map"
        elif any(word in user_prompt.lower() for word in ["compare", "vs", "difference", "对比", "比较", "双气泡图", "双泡图"]):
            return "double_bubble_map"
        elif any(word in user_prompt.lower() for word in ["describe", "characteristics", "特征", "描述", "气泡图", "单气泡图"]):
            return "bubble_map"
        elif any(word in user_prompt.lower() for word in ["define", "context", "定义", "上下文"]):
            return "circle_map"
        elif any(word in user_prompt.lower() for word in ["process", "steps", "流程", "步骤", "sequence"]):
            return "flow_map"
        elif any(word in user_prompt.lower() for word in ["whole", "part", "整体", "部分", "组成"]):
            return "brace_map"
        elif any(word in user_prompt.lower() for word in ["categorize", "classify", "分类", "归类"]):
            return "tree_map"
        elif any(word in user_prompt.lower() for word in ["cause", "effect", "原因", "影响", "因果"]):
            return "multi_flow_map"
        elif any(word in user_prompt.lower() for word in ["concept", "relationship", "概念", "关系"]):
            return "concept_map"
        elif any(word in user_prompt.lower() for word in ["semantic", "web", "语义", "网络"]):
            return "semantic_web"
        elif any(word in user_prompt.lower() for word in ["mind", "organize", "思维", "组织", "整理"]):
            return "mindmap"
        elif any(word in user_prompt.lower() for word in ["radial", "径向"]):
            return "radial_mindmap"
        elif any(word in user_prompt.lower() for word in ["venn", "overlap", "维恩", "重叠"]):
            return "venn_diagram"
        elif any(word in user_prompt.lower() for word in ["fishbone", "ishikawa", "鱼骨", "石川"]):
            return "fishbone_diagram"
        elif any(word in user_prompt.lower() for word in ["flowchart", "flow chart", "流程图"]):
            return "flowchart"
        elif any(word in user_prompt.lower() for word in ["org", "organization", "组织", "架构"]):
            return "org_chart"
        elif any(word in user_prompt.lower() for word in ["timeline", "time line", "时间线", "时间线"]):
            return "timeline"
        else:
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
    # Use centralized prompt registry
    try:
        from prompts import get_prompt
        
        # Get the appropriate prompt template
        prompt_text = get_prompt(graph_type, language, 'generation')
        
        if not prompt_text:
            logger.error(f"Agent: No prompt found for graph type: {graph_type}")
            return {"error": f"No prompt template found for {graph_type}"}
        
        # Create prompt template and generate response
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=prompt_text
        )
        
        yaml_text = (prompt | llm).invoke({"user_prompt": user_prompt})
        yaml_text_clean = extract_yaml_from_code_block(yaml_text)
        
        # Debug logging
        logger.debug(f"Raw LLM response for {graph_type}: {yaml_text}")
        logger.debug(f"Cleaned response: {yaml_text_clean}")
        
        try:
            # Try JSON first, then YAML as fallback
            try:
                spec = json.loads(yaml_text_clean)
            except json.JSONDecodeError:
                spec = yaml.safe_load(yaml_text_clean)
            
            if not spec:
                raise Exception("JSON/YAML parse failed")
            
            # Validate the generated spec
            from graph_specs import DIAGRAM_VALIDATORS
            if graph_type in DIAGRAM_VALIDATORS:
                validator = DIAGRAM_VALIDATORS[graph_type]
                valid, msg = validator(spec)
                if not valid:
                    raise Exception(f"Generated JSON does not match {graph_type} schema: {msg}")
            
            logger.info(f"Agent: Successfully generated {graph_type} specification")
            return spec
            
        except Exception as e:
            logger.error(f"Agent: {graph_type} JSON generation failed: {e}")
            return {"error": f"Failed to generate valid {graph_type} JSON"}
            
    except ImportError:
        logger.error("Agent: Failed to import centralized prompt registry")
        return {"error": "Prompt registry not available"}
    except Exception as e:
        logger.error(f"Agent: Unexpected error in generate_graph_spec: {e}")
        return {"error": f"Unexpected error generating {graph_type}"}


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
- tree_map: 层次结构图
- mindmap: 思维导图
- concept_map: 概念图
- flowchart: 流程图
- venn_diagram: 维恩图

样式偏好包括：
- colorTheme: 颜色主题 (classic, innovation, colorful, monochromatic, dark, light, print, display)
- primaryColor: 主色调 (颜色名称或十六进制)
- fontSize: 字体大小
- importance: 重要性级别 (center, main, sub, detail)
- backgroundTheme: 背景主题 (dark, light)

请以JSON格式输出：
{{{{
    "topics": ["主题1", "主题2"],
    "style_preferences": {{{{
        "colorTheme": "主题名称",
        "primaryColor": "颜色",
        "fontSize": 数字,
        "importance": "重要性级别",
        "backgroundTheme": "背景主题"
    }}}},
    "diagram_type": "图表类型"
}}}}

用户需求：{{user_prompt}}
"""
    else:
        prompt_text = f"""
You are an intelligent diagram assistant that extracts both topic content and style preferences from user requirements.
Please analyze the following user request and extract:
1. Main topics and subtopics
2. Style preferences (colors, fonts, layout, etc.)
3. Most suitable diagram type

Available diagram types:
- double_bubble_map: Compare and contrast two topics
- bubble_map: Describe characteristics of a single topic
- circle_map: Define topic in context
- tree_map: Hierarchical structure
- mindmap: Mind mapping
- concept_map: Concept mapping
- flowchart: Process flow
- venn_diagram: Set relationships

Style preferences include:
- colorTheme: Color theme (classic, innovation, colorful, monochromatic, dark, light, print, display)
- primaryColor: Primary color (color name or hex)
- fontSize: Font size
- importance: Importance level (center, main, sub, detail)
- backgroundTheme: Background theme (dark, light)

Please output in JSON format:
{{{{
    "topics": ["topic1", "topic2"],
    "style_preferences": {{{{
        "colorTheme": "theme_name",
        "primaryColor": "color",
        "fontSize": number,
        "importance": "importance_level",
        "backgroundTheme": "background_theme"
    }}}},
    "diagram_type": "diagram_type"
}}}}

User request: {{user_prompt}}
"""
    
    prompt = PromptTemplate(
        input_variables=["user_prompt"],
        template=prompt_text
    )
    
    try:
        result = (prompt | llm).invoke({"user_prompt": user_prompt})
        cleaned_result = clean_llm_response(result)
        parsed_result = validate_and_parse_json(cleaned_result)
        
        if parsed_result:
            # Validate and sanitize the parsed result
            topics = parsed_result.get('topics', [])
            if not isinstance(topics, list):
                topics = []
            
            style_preferences = parsed_result.get('style_preferences', {})
            if not isinstance(style_preferences, dict):
                style_preferences = {}
            
            diagram_type = parsed_result.get('diagram_type', 'bubble_map')
            if not isinstance(diagram_type, str):
                diagram_type = 'bubble_map'
            
            return {
                "topics": topics,
                "style_preferences": style_preferences,
                "diagram_type": diagram_type
            }
    except Exception as e:
        logger.error(f"Qwen style extraction failed: {e}")
    
    # Fallback to hardcoded parser
    try:
        from diagram_styles import parse_style_from_prompt
        style_preferences = parse_style_from_prompt(user_prompt)
        
        # Simple topic extraction fallback
        topics = []
        if "vs" in user_prompt.lower() or "compare" in user_prompt.lower() or "对比" in user_prompt:
            diagram_type = "double_bubble_map"
        elif "mind" in user_prompt.lower() or "思维" in user_prompt:
            diagram_type = "mindmap"
        elif "tree" in user_prompt.lower() or "树" in user_prompt:
            diagram_type = "tree_map"
        elif "concept" in user_prompt.lower() or "概念" in user_prompt:
            diagram_type = "concept_map"
        elif "flow" in user_prompt.lower() or "流程" in user_prompt:
            diagram_type = "flowchart"
        elif "venn" in user_prompt.lower() or "维恩" in user_prompt:
            diagram_type = "venn_diagram"
        else:
            diagram_type = "bubble_map"
        
        return {
            "topics": topics,
            "style_preferences": style_preferences,
            "diagram_type": diagram_type
        }
    except Exception as e:
        logger.error(f"Fallback style extraction failed: {e}")
        return get_default_result()


def generate_graph_spec_with_styles(user_prompt: str, graph_type: str, language: str = 'zh', style_preferences: dict = None) -> dict:
    """
    Generate graph specification with integrated style system.
    
    Args:
        user_prompt: User's input prompt
        graph_type: Type of diagram to generate
        language: Language for processing
        style_preferences: User's style preferences
    
    Returns:
        dict: JSON specification with integrated styles for D3.js rendering
    """
    logger.info(f"Agent: Generating graph spec with styles for type: {graph_type}")
    
    # Generate the base specification
    spec = generate_graph_spec(user_prompt, graph_type, language)
    
    if not spec or isinstance(spec, dict) and spec.get('error'):
        logger.error(f"Agent: Failed to generate base spec for {graph_type}")
        return spec
    
    # Integrate style system
    try:
        from diagram_styles import get_style, parse_style_from_prompt
        
        # Parse additional styles from prompt if not provided
        if not style_preferences:
            style_preferences = parse_style_from_prompt(user_prompt)
        
        # Get the complete style configuration
        color_theme = style_preferences.get('colorTheme', 'classic')
        variation = 'colorful'  # Default variation
        if 'dark' in style_preferences.get('backgroundTheme', '').lower():
            variation = 'dark'
        elif 'light' in style_preferences.get('backgroundTheme', '').lower():
            variation = 'light'
        
        complete_style = get_style(graph_type, style_preferences, color_theme, variation)
        
        # Add style information to the spec
        spec['_style'] = complete_style
        spec['_style_metadata'] = {
            'color_theme': color_theme,
            'variation': variation,
            'user_preferences': style_preferences
        }
        
        logger.info(f"Agent: Successfully integrated styles for {graph_type}")
        
    except Exception as e:
        logger.error(f"Agent: Style integration failed: {e}")
        # Continue without styles if integration fails
        spec['_style'] = {}
        spec['_style_metadata'] = {}
    
    return spec


def agent_graph_workflow_with_styles(user_prompt, language='zh'):
    """
    Enhanced agent workflow with integrated style system.
    
    Args:
        user_prompt (str): User's input prompt
        language (str): Language for processing ('zh' or 'en')
    
    Returns:
        dict: JSON specification with integrated styles for D3.js rendering
    """
    logger.info(f"Agent: Starting enhanced graph workflow for: {user_prompt}")
    
    try:
        # Extract topics, styles, and diagram type
        extraction = extract_topics_and_styles_from_prompt_qwen(user_prompt, language)
        topics = extraction.get('topics', [])
        style_preferences = extraction.get('style_preferences', {})
        diagram_type = extraction.get('diagram_type', 'bubble_map')
        
        logger.info(f"Agent: Extracted - topics: {topics}, diagram_type: {diagram_type}")
        logger.info(f"Agent: Style preferences: {style_preferences}")
        
        # Generate specification with integrated styles
        spec = generate_graph_spec_with_styles(user_prompt, diagram_type, language, style_preferences)
        
        # Add metadata to the result
        result = {
            'spec': spec,
            'diagram_type': diagram_type,
            'topics': topics,
            'style_preferences': style_preferences,
            'language': language
        }
        
        logger.info(f"Agent: Enhanced workflow completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Agent: Enhanced workflow failed: {e}")
        # Return fallback result
        return {
            'spec': {"topic": "主题", "characteristics": ["特征1", "特征2", "特征3", "特征4", "特征5"]},
            'diagram_type': 'bubble_map',
            'topics': [],
            'style_preferences': {},
            'language': language
        } 