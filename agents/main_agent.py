"""
Main Agent Module for MindGraph

This module contains the core agent functionality for generating custom graph content 
using the Qwen LLM. It supports 10+ diagram types including bubble maps, flow maps,
tree maps, concept maps, mind maps, and more through intelligent LLM-based classification.

Features:
- Semantic diagram type detection using LLM classification
- Support for 10+ thinking map and concept map types  
- Thread-safe statistics tracking
- Centralized error handling and validation
- Modular agent architecture with specialized diagram generators

The agent uses LLM-based prompt analysis to classify the user's intent and
generates the appropriate JSON specification for D3.js rendering.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
import logging
import re
import time
import traceback
from dotenv import load_dotenv
load_dotenv()

# Use standard logging like other modules
logger = logging.getLogger(__name__)

from langchain_core.prompts import PromptTemplate
import yaml
from config.settings import config
import json
from prompts import get_prompt

# Late imports to avoid circular dependencies
def _get_concept_map_agent():
    """Lazy import to avoid circular dependencies."""
    from agents.concept_maps.concept_map_agent import ConceptMapAgent
    return ConceptMapAgent

def create_error_response(message: str, error_type: str = "generation", context: dict = None) -> dict:
    """
    Create standardized error response format.
    
    Args:
        message: Error message
        error_type: Type of error (generation, validation, classification, etc.)
        context: Additional context information
        
    Returns:
        dict: Standardized error response
    """
    error_response = {
        "error": message,
        "error_type": error_type,
        "timestamp": time.time()
    }
    
    if context:
        error_response["context"] = context
    
    return error_response

def validate_inputs(user_prompt: str, language: str) -> None:
    """
    Validate input parameters for agent functions.
    
    Args:
        user_prompt: User input prompt
        language: Language code
        
    Raises:
        ValueError: If inputs are invalid
    """
    if not user_prompt or not isinstance(user_prompt, str) or not user_prompt.strip():
        raise ValueError("User prompt cannot be empty or None")
    
    if len(user_prompt.strip()) > 10000:  # Reasonable limit
        raise ValueError("User prompt too long (max 10,000 characters)")
    
    if not language or language not in ['zh', 'en']:
        raise ValueError("Language must be 'zh' or 'en'")

def extract_central_topic_llm(user_prompt: str, language: str = 'zh') -> str:
    """
    Extract central topic using LLM instead of hardcoded string manipulation.
    This provides better semantic understanding and context preservation.
    """
    try:
        if language == 'zh':
            prompt = f"从以下用户输入中提取核心主题，只返回主题内容，不要其他文字：\n{user_prompt}"
        else:
            prompt = f"Extract the central topic from this user input, return only the topic:\n{user_prompt}"
        
        result = llm_classification._call(prompt)
        # Clean up the result - remove any extra whitespace or formatting
        central_topic = result.strip()
        
        # Fallback to original prompt if extraction fails
        if not central_topic or len(central_topic) < 2:
            logger.warning(f"LLM topic extraction failed, using original prompt: {user_prompt}")
            central_topic = user_prompt.strip()
            
        return central_topic
        
    except Exception as e:
        logger.error(f"LLM topic extraction error: {e}, using original prompt")
        return user_prompt.strip()

async def extract_double_bubble_topics_llm(user_prompt: str, language: str = 'zh', model: str = 'qwen') -> str:
    """
    Extract two topics for double bubble map comparison using LLM.
    This is specialized for double bubble maps that need two separate topics.
    Fully async - no event loop wrappers.
    """
    from services.llm_service import llm_service
    
    try:
        if language == 'zh':
            prompt = f"""从以下用户输入中提取两个要比较的主题，只返回两个主题，用"和"连接，不要其他文字：
{user_prompt}

重要：忽略动作词如"生成"、"创建"、"比较"、"制作"等，只提取实际要比较的两个主题。

示例：
输入："生成速度和加速度的双气泡图" → 输出："速度和加速度"
输入："比较苹果和橙子" → 输出："苹果和橙子"
输入："创建关于猫和狗的比较图" → 输出："猫和狗"
输入："制作一个关于太阳和月亮的对比图" → 输出："太阳和月亮"

你的输出："""
        else:
            prompt = f"""Extract two topics for comparison from this user input, return only the two topics separated by "and", no other text:
{user_prompt}

Examples:
Input: "generate a double bubble map about speed and acceleration" → Output: "speed and acceleration"
Input: "compare apples and oranges" → Output: "apples and oranges"
Input: "create a comparison chart about cats and dogs" → Output: "cats and dogs"

Your output:"""
        
        result = await llm_service.chat(
            prompt=prompt,
            model=model,
            max_tokens=100,
            temperature=0.3
        )
        
        # Clean up the result - remove any extra whitespace or formatting
        topics = result.strip()
        
        # Fallback to original prompt if extraction fails
        if not topics or len(topics) < 3:
            logger.warning(f"LLM double bubble topic extraction failed, using original prompt: {user_prompt}")
            topics = user_prompt.strip()
            
        return topics
        
    except Exception as e:
        logger.error(f"LLM double bubble topic extraction error: {e}, using original prompt")
        return user_prompt.strip()

def extract_topics_and_styles_from_prompt_qwen(user_prompt: str, language: str = 'en') -> dict:
    """
    Simple replacement for the removed complex style extraction function.
    Returns minimal data structure that existing code expects.
    Now uses LLM-based topic extraction instead of hardcoded string manipulation.
    """
    # Use LLM-based topic extraction
    central_topic = extract_central_topic_llm(user_prompt, language)
    
    return {
        "topics": [central_topic] if central_topic else [],
        "style_preferences": {},
        "diagram_type": "bubble_map",  # Default
        "suggested_diagram_type": "concept_map"
    }

def _salvage_json_string(raw: str) -> str:
    """Attempt to salvage a JSON object from messy LLM output."""
    if not raw:
        return ""
    s = raw.strip().strip('`')
    # Remove code fences if present
    if s.startswith('```'):
        fence_end = s.rfind('```')
        if fence_end > 3:
            s = s[3:fence_end]
    # Find first '{' and balance braces outside strings
    start = s.find('{')
    if start == -1:
        return ""
    buf = []
    depth = 0
    in_str = False
    esc = False
    for ch in s[start:]:
        buf.append(ch)
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    break
    candidate = ''.join(buf)
    while depth > 0:
        candidate += '}'
        depth -= 1
    # Remove trailing commas before } or ]
    candidate = re.sub(r',\s*(\]|\})', r'\1', candidate)
    return candidate.strip()

import threading

class LLMTimingStats:
    """Thread-safe LLM timing statistics tracker."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._total_calls = 0
        self._total_time = 0.0
        self._call_times = []
        self._last_call_time = 0.0
    
    def add_call_time(self, call_time: float):
        """Add a new call time to statistics."""
        with self._lock:
            self._total_calls += 1
            self._total_time += call_time
            self._last_call_time = call_time
            self._call_times.append(call_time)
            
            # Keep only last 100 call times to prevent memory bloat
            if len(self._call_times) > 100:
                self._call_times = self._call_times[-100:]
    
    def get_stats(self) -> dict:
        """Get current timing statistics."""
        with self._lock:
            avg_time = self._total_time / self._total_calls if self._total_calls > 0 else 0.0
            return {
                'total_calls': self._total_calls,
                'total_time': self._total_time,
                'average_time': avg_time,
                'last_call_time': self._last_call_time,
                'call_times': self._call_times[-10:]
            }

# Thread-safe global timing tracker
llm_timing_stats = LLMTimingStats()

def get_llm_timing_stats():
    """Get current LLM timing statistics."""
    return llm_timing_stats.get_stats()


# ----------------------------------------------------------------------------
# LLM Client Implementation (Phase 5 - Using LLM Service Middleware)
# ----------------------------------------------------------------------------
# All agents now use llm_service directly from services/llm_service.py
# This provides centralized error handling, retries, rate limiting, and metrics
# The old LLMServiceWrapper has been removed for cleaner architecture

# Temporary stub for backward compatibility with legacy concept map functions
# Updated to use LLM Service (Phase 5 migration)
class _LegacyLLMStub:
    """Stub for old concept map functions - uses LLM Service"""
    def _call(self, prompt):
        import asyncio
        from services.llm_service import llm_service
        
        async def _async_call():
            return await llm_service.chat(
                prompt=prompt,
                model='qwen',
                timeout=30.0
            )
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(_async_call())

# Legacy stubs for old concept map code - now using LLM Service
llm_classification = _LegacyLLMStub()
llm_generation = _LegacyLLMStub()
llm = _LegacyLLMStub()


class QwenLLM:
    """
    Backward-compatible sync wrapper for learning agents that haven't been migrated to async yet.
    
    Now uses LLM Service instead of direct client (Phase 5 migration).
    Used by: LearningAgent, LearningAgentV3, and qwen_langchain.py
    """
    def __init__(self, model_type='generation'):
        """
        Initialize QwenLLM wrapper.
        
        Args:
            model_type: 'generation' or 'classification' (uses qwen model from LLM Service)
        """
        self.model_type = model_type
    
    def _call(self, prompt: str, stop=None):
        """
        Synchronous wrapper for async LLM Service call.
        
        Args:
            prompt: The prompt to send to the LLM
            stop: Stop sequences (not used, kept for compatibility)
            
        Returns:
            str: The LLM response content
        """
        import asyncio
        from services.llm_service import llm_service
        
        async def _async_call():
            return await llm_service.chat(
                prompt=prompt,
                model='qwen',
                timeout=30.0
            )
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(_async_call())


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


# ============================================================================
# LANGCHAIN CHAINS
# ============================================================================

def create_topic_extraction_chain(language='zh'):
    """
    Create a simple chain for topic extraction
    Args:
        language (str): Language for the prompt ('zh' or 'en')
    Returns:
        function: Function that can be called with user_prompt
    """
    prompt = topic_extraction_prompt_zh if language == 'zh' else topic_extraction_prompt_en
    
    def extract_topics(user_prompt):
        """Extract topics using the classification model"""
        return llm_classification._call(prompt.format(user_prompt=user_prompt))
    
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
    
    def generate_characteristics(topic1, topic2):
        """Generate characteristics using the generation model"""
        return llm_generation._call(prompt.format(topic1=topic1, topic2=topic2))
    
    return generate_characteristics


# ============================================================================
# AGENT WORKFLOW FUNCTIONS
# ============================================================================

def extract_yaml_from_code_block(text):
    """Extract content from fenced code blocks, robust to minor formatting.

    - Handles ```json, ```yaml, ```yml, ```js, or bare ```
    - Closing fence may or may not be preceded by a newline
    - If multiple blocks exist, returns the first
    - If no fences are found, returns stripped text
    """
    s = (text or "").strip()
    # Regex-based extraction first
    match = re.search(r"```(?:json|yaml|yml|javascript|js)?\s*\r?\n([\s\S]*?)\r?\n?```", s, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: manual slicing if starts with a fence but regex failed
    if s.startswith("```"):
        # Drop first line (```lang)
        first_nl = s.find("\n")
        content = s[first_nl + 1:] if first_nl != -1 else s[3:]
        last_fence = content.rfind("```")
        if last_fence != -1:
            content = content[:last_fence]
        return content.strip()

    return s

# Legacy function removed - using extract_topics_and_styles_from_prompt_qwen instead


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
            logger.error(f"No prompt found for graph type: {graph_type}")
            return create_error_response(f"No prompt template found for {graph_type}", "template", {"graph_type": graph_type})
        
        # Sanitize template to ensure only {user_prompt} is a variable; all other braces become literal
        def _sanitize_prompt_template_for_langchain(template: str) -> str:
            placeholder = "<<USER_PROMPT_PLACEHOLDER>>"
            temp = template.replace("{user_prompt}", placeholder)
            temp = temp.replace("{", "{{").replace("}", "}}")
            return temp.replace(placeholder, "{user_prompt}")

        safe_template = _sanitize_prompt_template_for_langchain(prompt_text)
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=safe_template
        )
        # Use generation model for graph specification generation (high quality)
        yaml_text = llm_generation._call(prompt.format(user_prompt=user_prompt))
        # Some LLM clients return dict-like objects; ensure string
        try:
            raw_text = yaml_text if isinstance(yaml_text, str) else str(yaml_text)
        except Exception:
            raw_text = f"{yaml_text}"
        yaml_text_clean = extract_yaml_from_code_block(raw_text)
        
        # Debug logging
        logger.debug(f"Raw LLM response for {graph_type}: {yaml_text}")
        logger.debug(f"Cleaned response: {yaml_text_clean}")
        
        try:
            # Try JSON first, then YAML; if that fails, attempt to salvage JSON by stripping trailing backticks
            try:
                spec = json.loads(yaml_text_clean)
            except json.JSONDecodeError:
                # Try to remove accidental trailing fences in the cleaned text
                cleaned = yaml_text_clean.strip().rstrip('`').strip()
                try:
                    spec = json.loads(cleaned)
                except Exception:
                    # Attempt to salvage a JSON object from messy output
                    salvaged = _salvage_json_string(raw_text)
                    if salvaged:
                        try:
                            spec = json.loads(salvaged)
                        except Exception:
                            spec = yaml.safe_load(yaml_text_clean)
                    else:
                        spec = yaml.safe_load(yaml_text_clean)
        
            if not spec:
                raise Exception("JSON/YAML parse failed")
            
            # Note: Agent validation is now handled by specialized agents, not here
            
            logger.info(f"{graph_type} specification generated successfully")
            return spec
            
        except Exception as e:
            logger.error(f"{graph_type} JSON generation failed: {e}")
            return create_error_response(f"Failed to generate valid {graph_type} JSON", "generation", {"graph_type": graph_type})
            
    except ImportError:
        logger.error("Failed to import centralized prompt registry")
        return create_error_response("Prompt registry not available", "import", {"graph_type": graph_type})
    except Exception as e:
        logger.error(f"Unexpected error in generate_graph_spec: {e}")
        return create_error_response(f"Unexpected error generating {graph_type}", "unexpected", {"graph_type": graph_type})


# Legacy function removed - using agent_graph_workflow_with_styles instead


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
        # Test LLM connection using classification model (fast/cheap)
        test_prompt = "Test"
        llm_classification._call(test_prompt)
        logger.info("LLM connection validation completed successfully")
        return True
    except TimeoutError:
        logger.error("LLM validation timed out")
        return False
    except Exception as e:
        logger.error(f"LLM connection failed: {e}")
        return False
    finally:
        timer.cancel() 



async def _detect_diagram_type_from_prompt(
    user_prompt: str, 
    language: str, 
    model: str = 'qwen',
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type='diagram_generation',
    endpoint_path=None
) -> dict:
    """
    LLM-based diagram type detection using semantic understanding.
    
    Args:
        user_prompt: User's input prompt
        language: Language ('zh' or 'en')
        model: LLM model to use ('qwen', 'deepseek', 'kimi', 'doubao')
    
    Returns:
        dict: {'diagram_type': str, 'clarity': str, 'has_topic': bool}
              clarity can be 'clear', 'unclear', or 'very_unclear'
    """
    try:
        # Validate inputs
        validate_inputs(user_prompt, language)
        
        # Check if prompt is too vague or complex (basic heuristics before LLM)
        prompt_words = user_prompt.strip().split()
        is_too_short = len(prompt_words) < 2
        is_too_long = len(prompt_words) > 100
        
        # Get classification prompt from centralized system
        classification_prompt = get_prompt("classification", language, "generation")
        classification_prompt = classification_prompt.format(user_prompt=user_prompt)
        
        # Use middleware directly - clean and efficient!
        from services.llm_service import llm_service
        response = await llm_service.chat(
            prompt=classification_prompt,
            model=model,
            max_tokens=50,
            temperature=0.3,
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path
        )
        
        # Extract diagram type from response
        detected_type = response.strip().lower()
        
        # Validate the detected type - only include working diagram types
        # 8 thinking maps + 1 mindmap (concept_map and thinking tools are work in progress)
        valid_types = {
            'circle_map', 'bubble_map', 'double_bubble_map', 
            'brace_map', 'bridge_map', 'tree_map', 
            'flow_map', 'multi_flow_map', 
            'mind_map'
        }
        
        # Determine clarity based on LLM response and heuristics
        clarity = 'clear'
        has_topic = True
        
        # Check if LLM explicitly returned "unclear"
        if detected_type == 'unclear':
            clarity = 'very_unclear'
            has_topic = False
            detected_type = 'mind_map'  # Default fallback
            logger.warning(f"LLM explicitly returned 'unclear' for prompt: '{user_prompt}'")
        elif detected_type not in valid_types:
            # LLM returned something invalid
            clarity = 'very_unclear'
            has_topic = False
            detected_type = 'mind_map'  # Default fallback
            logger.warning(f"LLM returned invalid type '{detected_type}', prompt may be too complex: '{user_prompt}'")
        elif is_too_short or is_too_long:
            # Prompt length is suspicious
            clarity = 'unclear'
            logger.debug(f"Prompt length is suspicious (words: {len(prompt_words)})")
        
        result = {
            'diagram_type': detected_type,
            'clarity': clarity,
            'has_topic': has_topic
        }
        
        logger.debug(f"LLM classification: '{user_prompt}' → {detected_type} (clarity: {clarity})")
        return result
            
    except ValueError as e:
        logger.error(f"Input validation failed: {e}")
        return {'diagram_type': 'mind_map', 'clarity': 'very_unclear', 'has_topic': False}
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return {'diagram_type': 'mind_map', 'clarity': 'very_unclear', 'has_topic': False}





def _invoke_llm_prompt(prompt_template: str, variables: dict) -> str:
    """Invoke LLM with a specific prompt template and variables, and return raw string."""
    safe_template = prompt_template
    # Sanitize braces except for placeholders present in variables
    for k in variables.keys():
        placeholder = f"<<{k.upper()}>>"
        safe_template = safe_template.replace(f"{{{k}}}", placeholder)
    safe_template = safe_template.replace("{", "{{").replace("}", "}}")
    for k in variables.keys():
        placeholder = f"<<{k.upper()}>>"
        safe_template = safe_template.replace(placeholder, f"{{{k}}}")
    # Use generation model for concept map generation tasks (high quality)
    # Format the template with variables and call the LLM directly
    formatted_prompt = safe_template
    for key, value in variables.items():
        formatted_prompt = formatted_prompt.replace(f"{{{key}}}", str(value))
    
    raw = llm_generation._call(formatted_prompt)
    return raw if isinstance(raw, str) else str(raw)


def _salvage_truncated_json(text: str) -> str:
    """Aggressively salvage truncated JSON by completing incomplete strings and structures."""
    try:
        # Find the last complete relationship entry
        lines = text.split('\n')
        salvaged_lines = []
        in_relationships = False
        brace_count = 0
        
        for line in lines:
            if '"relationships"' in line:
                in_relationships = True
                salvaged_lines.append(line)
                continue
                
            if in_relationships:
                # Count braces to track structure
                brace_count += line.count('{') - line.count('}')
                
                # Check if this line is complete (ends with } or ,)
                if line.strip().endswith('},') or line.strip().endswith('}'):
                    salvaged_lines.append(line)
                elif line.strip().endswith(','):
                    salvaged_lines.append(line)
                elif '"from"' in line and '"to"' in line and '"label"' in line:
                    # This looks like a complete relationship, add it
                    if not line.strip().endswith(','):
                        line = line.rstrip() + ','
                    salvaged_lines.append(line)
                elif line.strip().startswith('"from"') or line.strip().startswith('"to"') or line.strip().startswith('"label"'):
                    # This is part of a relationship, try to complete it
                    if '"from"' in line and '"to"' in line and '"label"' in line:
                        # Looks complete, add comma if needed
                        if not line.strip().endswith(','):
                            line = line.rstrip() + ','
                        salvaged_lines.append(line)
                    else:
                        # Incomplete, skip this line
                        continue
                else:
                    salvaged_lines.append(line)
            else:
                salvaged_lines.append(line)
        
        # Close the relationships array and main object
        if in_relationships:
            # Remove trailing comma from last relationship
            if salvaged_lines and salvaged_lines[-1].strip().endswith(','):
                salvaged_lines[-1] = salvaged_lines[-1].rstrip(',')
            
            # Add closing brackets
            salvaged_lines.append('  ]')
            salvaged_lines.append('}')
        
        salvaged_text = '\n'.join(salvaged_lines)
        
        # Validate the salvaged JSON
        json.loads(salvaged_text)
        return salvaged_text
        
    except Exception as e:
        logger.error(f"JSON salvage failed: {e}")
        return None


def _parse_strict_json(text: str) -> dict:
    """Parse JSON with robust extraction and salvage; raise on failure."""
    cleaned = extract_yaml_from_code_block(text)
    # Normalize unicode quotes and remove non-JSON noise
    cleaned = cleaned.strip().strip('`')
    # Replace smart quotes with ASCII equivalents
    cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    cleaned = cleaned.replace('"', '"').replace('"', '"').replace('"', '"').replace('"', '"')
    # Remove zero-width and control characters
    cleaned = re.sub(r"[\u200B-\u200D\uFEFF]", "", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", cleaned)
    # Remove JS-style comments if present
    cleaned = re.sub(r"//.*?$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    # Remove trailing commas before ] or }
    cleaned = re.sub(r",\s*(\]|\})", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # Try salvage
        candidate = _salvage_json_string(cleaned)
        if candidate:
            candidate = re.sub(r",\s*(\]|\})", r"\1", candidate)
            return json.loads(candidate)
        raise


def generate_concept_map_two_stage(user_prompt: str, language: str) -> dict:
    """Deterministic two-stage generation for concept maps (no fallback parsing errors)."""
    # Stage 1: keys
    key_prompt = get_prompt('concept_map_keys', language, 'generation')
    raw_keys = _invoke_llm_prompt(key_prompt, { 'user_prompt': user_prompt })
    
    # Use improved parsing for better error handling
    try:
        from .concept_maps import ConceptMapAgent
        agent = ConceptMapAgent()
        keys_obj = agent._parse_json_response(raw_keys)
        logger.debug("Used ConceptMapAgent improved parsing for keys generation")
    except Exception as e:
        logger.warning(f"ConceptMapAgent parsing failed for keys, falling back to strict parsing: {e}")
        # Fallback to strict parsing if ConceptMapAgent is not available
        keys_obj = _parse_strict_json(raw_keys)
        logger.debug("Used strict parsing fallback for keys generation")
    topic = (keys_obj.get('topic') or user_prompt).strip()
    keys_raw = keys_obj.get('keys') or []
    keys = []
    seen_keys = set()
    for k in keys_raw:
        name = k.get('name') if isinstance(k, dict) else k
        if isinstance(name, str):
            name = name.strip()
            if name and name.lower() not in seen_keys:
                keys.append(name)
                seen_keys.add(name.lower())
    # Cap keys to 4–8 for readability
    max_keys = 8
    min_keys = 4
    keys = keys[:max_keys]
    if len(keys) < min_keys and len(keys_raw) > 0:
        # Best-effort: keep as is; downstream will handle layout even with fewer keys
        pass

    # Stage 2: parts for each key
    from concurrent.futures import ThreadPoolExecutor, as_completed
    parts_prompt = get_prompt('concept_map_parts', language, 'generation')

    # Budget total concepts <= 30
    max_concepts_total = 30
    remaining_budget = max(0, max_concepts_total - len(keys))
    per_key_cap = max(2, remaining_budget // max(1, len(keys))) if keys else 0

    def fetch_parts(k: str) -> tuple:
        try:
            raw = _invoke_llm_prompt(parts_prompt, { 'topic': topic, 'key': k })
            
            # Use improved parsing for better error handling
            try:
                from .concept_maps import ConceptMapAgent
                agent = ConceptMapAgent()
                obj = agent._parse_json_response(raw)
                logger.debug(f"Used ConceptMapAgent improved parsing for parts of key '{k}'")
            except Exception as e:
                logger.debug(f"ConceptMapAgent parsing failed for parts of key '{k}', using strict parsing fallback")
                # Fallback to strict parsing if ConceptMapAgent is not available
                obj = _parse_strict_json(raw)
            plist = obj.get('parts') or []
            parts_collected = []
            seen = set()
            for p in plist:
                name = p.get('name') if isinstance(p, dict) else p
                label = p.get('label') if isinstance(p, dict) else None
                if isinstance(name, str):
                    name = name.strip()
                    if name and name.lower() not in seen:
                        parts_collected.append({'name': name, 'label': (label or '').strip()[:60]})
                        seen.add(name.lower())
                if len(parts_collected) >= per_key_cap:
                    break
            return (k, parts_collected)
        except Exception:
            return (k, [])

    parts_results = { k: [] for k in keys }
    # Run in parallel to save time
    max_workers = min(6, len(keys)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_parts, k) for k in keys]
    for fut in as_completed(futures):
            k, plist = fut.result()
            parts_results[k] = plist

    # Merge into standard concept map spec
    concepts = []
    seen_concepts = set()
    for name in keys + [p.get('name') for arr in parts_results.values() for p in arr]:
        low = name.lower()
        if low not in seen_concepts and len(concepts) < max_concepts_total:
            concepts.append(name)
            seen_concepts.add(low)
    relationships = []
    # topic -> key relationships (use label if present)
    for k in (keys_obj.get('keys') or []):
        name = k.get('name') if isinstance(k, dict) else None
        label = k.get('label') if isinstance(k, dict) else 'related to'
        if isinstance(name, str) and name.strip():
            if name in concepts:
                relationships.append({ 'from': topic, 'to': name, 'label': label or 'related to' })
    # key -> part relationships
    for key, plist in parts_results.items():
        for p in plist:
            if p.get('name') in concepts:
                relationships.append({ 'from': key, 'to': p.get('name'), 'label': (p.get('label') or 'includes') })

    # Final trim to satisfy validator (<= 30 concepts)
    if len(concepts) > max_concepts_total:
        concepts = concepts[:max_concepts_total]
    allowed = set(concepts)
    relationships = [r for r in relationships if r.get('from') in allowed.union({topic}) and r.get('to') in allowed.union({topic})]
    # Prune keys and parts to allowed concepts
    keys = [k for k in keys if k in allowed]
    parts_results = { k: [p for p in (parts_results.get(k, []) or []) if p.get('name') in allowed] for k in keys }

    # Include keys and parts for sector layout
    spec = { 'topic': topic, 'concepts': concepts, 'relationships': relationships, 'keys': [{'name': k} for k in keys], 'key_parts': { k: parts_results.get(k, []) for k in keys } }
    return spec


def generate_concept_map_unified(user_prompt: str, language: str) -> dict:
    """One-shot concept map generation with keys, parts, and relationships together."""
    prompt_key = 'concept_map_unified_generation_zh' if language == 'zh' else 'concept_map_unified_generation_en'
    unified_prompt = get_prompt('concept_map_unified', language, 'generation')
    raw = _invoke_llm_prompt(unified_prompt, { 'user_prompt': user_prompt })
    
    # Use the improved ConceptMapAgent parsing for better error handling
    try:
        from .concept_maps import ConceptMapAgent
        agent = ConceptMapAgent()
        obj = agent._parse_json_response(raw)
        logger.debug("Used ConceptMapAgent improved parsing for unified generation")
    except Exception as e:
        logger.warning(f"ConceptMapAgent parsing failed, falling back to strict parsing: {e}")
        # Fallback to strict parsing if ConceptMapAgent is not available
        try:
            obj = _parse_strict_json(raw)
            logger.debug("Used strict parsing fallback for unified generation")
        except Exception as e2:
            logger.error(f"All parsing methods failed for unified generation: {e2}")
            return { 'error': f'Concept map parsing failed: {e2}' }
    # Extract - prioritize concepts from ConceptMapAgent parsing
    topic = (obj.get('topic') or user_prompt).strip()
    concepts_raw = obj.get('concepts') or []
    keys_raw = obj.get('keys') or []
    key_parts_raw = obj.get('key_parts') or {}
    rels_raw = obj.get('relationships') or []
    
    # First, use concepts if they were successfully extracted
    if concepts_raw and isinstance(concepts_raw, list):
        concepts = []
        seen_all = set()
        for concept in concepts_raw:
            if isinstance(concept, str) and concept.strip():
                name = concept.strip()
                low = name.lower()
                if low not in seen_all and len(concepts) < 30:
                    concepts.append(name)
                    seen_all.add(low)
        allowed = set(concepts)
        logger.debug(f"Using concepts extracted by ConceptMapAgent: {concepts}")
    else:
        # Fallback: build concepts from keys and parts (original logic)
        # Normalize keys
        keys = []
        seen_k = set()
        for k in keys_raw:
            name = k.get('name') if isinstance(k, dict) else k
            if isinstance(name, str):
                name = name.strip()
                if name and name.lower() not in seen_k:
                    keys.append(name)
                    seen_k.add(name.lower())
        # Normalize parts
        parts_results = {}
        seen_parts_global = set()
        for k in keys:
            plist = key_parts_raw.get(k) or []
            out = []
            seen_local = set()
            for p in plist:
                name = p.get('name') if isinstance(k, dict) else p
                if isinstance(name, str):
                    name = name.strip()
                    low = name.lower()
                    if name and low not in seen_local and low not in seen_parts_global:
                        out.append(name)
                        seen_local.add(low)
                        seen_parts_global.add(low)
            parts_results[k] = out
        # Build concepts within cap
        max_concepts_total = 30
        concepts = []
        seen_all = set()
        for name in keys + [p for arr in parts_results.values() for p in arr]:
            low = name.lower()
            if low not in seen_all and len(concepts) < max_concepts_total:
                concepts.append(name)
                seen_all.add(low)
        allowed = set(concepts)
        logger.debug(f"Built concepts from keys/parts: {concepts}")
    # Relationships
    relationships = []
    pair_seen = set()
    def add_rel(frm, to, label):
        if not isinstance(frm, str) or not isinstance(to, str):
            return
        if frm == to:
            return
        if frm not in allowed and frm != topic:
            return
        if to not in allowed and to != topic:
            return
        key = tuple(sorted((frm.lower(), to.lower())))
        if key in pair_seen:
            return
        pair_seen.add(key)
        relationships.append({ 'from': frm, 'to': to, 'label': (label or 'related to')[:60] })
    # Add mandatory topic->key and key->part
    for k in keys_raw:
        name = k.get('name') if isinstance(k, dict) else None
        label = (k.get('label') if isinstance(k, dict) else 'related to')
        if isinstance(name, str) and name.strip() and name in allowed:
            add_rel(topic, name, label)
    for key, plist in parts_results.items():
        for p in plist:
            add_rel(key, p, 'includes')
    # Add extra from rels_raw (deduped, within allowed)
    for r in rels_raw:
        add_rel(r.get('from'), r.get('to'), r.get('label'))
    return {
        'topic': topic,
        'concepts': list(allowed),
        'relationships': relationships,
        'keys': [{'name': k} for k in keys if k in allowed],
        'key_parts': { k: [{'name': p} for p in parts_results.get(k, []) if p in allowed] for k in keys if k in allowed }
    }


def generate_concept_map_enhanced_30(user_prompt: str, language: str) -> dict:
    """
    Enhanced concept map generation that produces exactly 30 concepts.
    
    This integrates with existing topic extraction and uses optimized prompts
    to generate exactly 30 concepts + relationships, matching the desired workflow.
    """
    try:
        # Use LLM-based topic extraction instead of hardcoded string manipulation
        central_topic = extract_central_topic_llm(user_prompt, language)
        
        if isinstance(central_topic, list):
            central_topic = ' '.join(central_topic)
        
        logger.debug(f"Using central topic for 30-concept generation: {central_topic}")
        
        # Generate exactly 30 concepts using centralized prompts
        from prompts import get_prompt
        
        # Get appropriate prompt for language
        concept_prompt = get_prompt("concept_30", language, "generation")
        if concept_prompt:
            concept_prompt = concept_prompt.format(central_topic=central_topic)
        else:
            # Fallback if prompt not found
            logger.warning("Concept 30 generation prompt not found in centralized system, using fallback")
            if language == 'zh':
                concept_prompt = f"为主题{central_topic}生成30个相关概念，输出JSON格式"
            else:
                concept_prompt = f"Generate 30 related concepts for topic {central_topic}, output JSON format"

        # Get concepts from LLM
        concepts_response = _invoke_llm_prompt(concept_prompt, {'central_topic': central_topic})
        
        if not concepts_response:
            raise ValueError("No response from LLM for concept generation")
        
        # Parse concepts response
        try:
            import json
            concepts_data = json.loads(concepts_response.strip())
        except json.JSONDecodeError:
            try:
                from .concept_maps import ConceptMapAgent
                agent = ConceptMapAgent()
                concepts_data = agent._parse_json_response(concepts_response)
                logger.debug("Used ConceptMapAgent improved parsing for concepts")
            except Exception as e:
                logger.warning(f"ConceptMapAgent parsing failed for concepts: {e}")
                concepts_data = _parse_strict_json(concepts_response)
                logger.debug("Used strict parsing for concepts")
        
        # Handle both dict and list formats
        if isinstance(concepts_data, dict):
            concepts = concepts_data.get('concepts', [])
        elif isinstance(concepts_data, list):
            concepts = concepts_data
        else:
            concepts = []
        
        # Ensure exactly 30 concepts
        if len(concepts) != 30:
            if len(concepts) > 30:
                concepts = concepts[:30]  # Take first 30
                logger.debug(f"Trimmed concepts from {len(concepts)} to 30")
            else:
                # Pad with generic concepts if less than 30
                while len(concepts) < 30:
                    concepts.append(f"Related aspect {len(concepts) + 1}")
                logger.debug(f"Padded concepts from {len(concepts)} to 30")
        
        if not concepts:
            raise ValueError("No concepts generated")
        
        # Generate relationships using systematic approach
        if language == 'zh':
            rel_prompt = f"""
现在为主题"{central_topic}"和这30个概念生成关系：

概念列表：
{', '.join(concepts)}

关系生成策略：
1. 主题-概念关系：为每个概念与主题创建有意义的关系
2. 概念间关系：寻找概念之间的逻辑连接
3. 分类关系：同类概念之间的关系
4. 因果关系：存在因果链的概念
5. 依赖关系：有依赖性的概念

输出JSON格式：
{{
  "relationships": [
    {{"from": "{{central_topic}}", "to": "概念1", "label": "包含"}},
    {{"from": "概念A", "to": "概念B", "label": "导致"}},
    ...
  ]
}}

要求：
- 每个概念至少与主题有一个关系
- 总共生成40-60个关系
- 关系标签简洁（1-3个字）
- 关系逻辑合理
- 避免重复关系
"""
        else:
            rel_prompt = f"""
Generate relationships for topic "{central_topic}" and these 30 concepts:

Concepts:
{', '.join(concepts)}

Relationship Strategy:
1. Topic-Concept relationships: Create meaningful connections between each concept and the topic
2. Inter-concept relationships: Find logical connections between concepts
3. Category relationships: Connect concepts within same categories
4. Causal relationships: Identify cause-effect chains between concepts
5. Dependency relationships: Connect concepts with dependencies

Output JSON format:
{{
  "relationships": [
    {{"from": "{{central_topic}}", "to": "concept1", "label": "contains"}},
    {{"from": "conceptA", "to": "conceptB", "label": "causes"}},
    ...
  ]
}}

Requirements:
- Each concept should have at least one relationship with the topic
- Generate 40-60 total relationships
- Relationship labels should be concise (1-3 words)
- Relationships should be logical
- Avoid duplicate relationships
"""

        # Get relationships from LLM
        relationships_response = _invoke_llm_prompt(rel_prompt, {'central_topic': central_topic, 'concepts': concepts})
        
        if not relationships_response:
            raise ValueError("No response from LLM for relationship generation")
        
        # Parse relationships response
        try:
            import json
            rel_data = json.loads(relationships_response.strip())
        except json.JSONDecodeError:
            try:
                from .concept_maps import ConceptMapAgent
                agent = ConceptMapAgent()
                rel_data = agent._parse_json_response(relationships_response)
                logger.debug("Used ConceptMapAgent improved parsing for relationships")
            except Exception as e:
                logger.warning(f"ConceptMapAgent parsing failed for relationships: {e}")
                rel_data = _parse_strict_json(relationships_response)
                logger.debug("Used strict parsing for relationships")
        
        relationships = rel_data.get('relationships', [])
        
        if not relationships:
            raise ValueError("No relationships generated")
        
        # Build the final specification
        spec = {
            'topic': central_topic,
            'concepts': concepts,  # Exactly 30 concepts
            'relationships': relationships,
            '_method': 'enhanced_30',  # Mark for identification
            '_concept_count': len(concepts),
            '_stage_info': {
                'original_prompt': user_prompt,
                'extracted_topic': central_topic,
                'concept_count': len(concepts),
                'relationship_count': len(relationships)
            }
        }
        
        logger.debug(f"Enhanced 30-concept generation completed successfully with {len(concepts)} concepts and {len(relationships)} relationships")
        return spec
        
    except Exception as e:
        logger.error(f"Enhanced 30-concept generation failed: {e}")
        logger.error(f"Stack trace: {traceback.format_exc()}")
        
        # Fallback to original method
        return generate_concept_map_unified(user_prompt, language)


def generate_concept_map_robust(user_prompt: str, language: str, method: str = 'auto') -> dict:
    """Robust concept map generation with multiple approaches.
    
    Args:
        user_prompt: User's input prompt
        language: Language for processing
        method: Generation method ('auto', 'unified', 'two_stage', 'network_first', 'three_stage')
    
    Returns:
        dict: Concept map specification
    """
    # NEW: Try the enhanced concept-first method (RECOMMENDED)
    if method in ['auto', 'three_stage']:
        try:
            # Use existing topic extraction + enhanced 30-concept generation
            return generate_concept_map_enhanced_30(user_prompt, language)
        except Exception as e:
            logger.warning(f"Enhanced 30-concept generation failed: {e}")
            # Try with fewer concepts as fallback
            try:
                logger.debug("Attempting fallback with simplified two-stage generation...")
                from .concept_maps import ConceptMapAgent
                agent = ConceptMapAgent()
                result = agent.generate_simplified_two_stage(user_prompt, llm_generation, language)
                if isinstance(result, dict) and result.get('success'):
                    return result.get('spec', {})
                else:
                    logger.warning(f"Simplified two-stage generation failed: {result.get('error')}")
                    raise ValueError("All concept map generation methods failed")
            except Exception as fallback_error:
                logger.warning(f"Simplified two-stage fallback also failed: {fallback_error}")
    
    # If method is specified, try that first
    if method == 'network_first':
        try:
            from .concept_maps import ConceptMapAgent
            agent = ConceptMapAgent()
            # Use the global LLM client
            result = agent.generate_network_first(user_prompt, llm, language)
            if isinstance(result, dict) and result.get('success'):
                return result.get('spec', {})
            else:
                logger.warning(f"Network-first generation failed: {result.get('error')}")
        except Exception as e:
            logger.warning(f"Network-first generation failed: {e}")
    
    # With increased token limits, the enhanced method should work
    # If it fails, there's a deeper issue that needs investigation
    logger.error("Enhanced concept map generation failed despite increased token limits")
    logger.error("This indicates a configuration or API issue that needs investigation")
    raise ValueError("All concept map generation methods failed - check LLM configuration")


async def _generate_spec_with_agent(
    user_prompt: str, 
    diagram_type: str, 
    language: str, 
    dimension_preference: str = None, 
    model: str = 'qwen',
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type='diagram_generation',
    endpoint_path=None,
    diagram_type_for_tracking=None,
    # Bridge map specific
    existing_analogies=None,
    fixed_dimension=None,
    # Tree map and brace map: dimension-only mode (user has dimension but no topic)
    dimension_only_mode=None
) -> dict:
    """
    Generate specification using the appropriate specialized agent.
    
    Args:
        user_prompt: User's input prompt
        diagram_type: Type of diagram to generate
        language: Language for processing
        dimension_preference: Optional dimension preference for brace maps (decomposition), tree maps (classification), and bridge maps (analogy pattern)
        model: LLM model to use ('qwen', 'deepseek', 'kimi'). Passed to agent for LLM client selection.
        existing_analogies: For bridge map auto-complete - existing pairs to preserve [{left, right}, ...]
        fixed_dimension: For bridge map auto-complete - user-specified relationship pattern that should NOT be changed
    
    Returns:
        dict: Generated specification
    """
    try:
        # Import and instantiate the appropriate agent with model
        if diagram_type == 'bubble_map':
            from .thinking_maps.bubble_map_agent import BubbleMapAgent
            agent = BubbleMapAgent(model=model)
        elif diagram_type == 'bridge_map':
            logger.debug("Bridge map agent selection started")
            from .thinking_maps.bridge_map_agent import BridgeMapAgent
            agent = BridgeMapAgent(model=model)
            logger.debug("BridgeMapAgent imported and instantiated successfully")
        elif diagram_type == 'tree_map':
            from .thinking_maps.tree_map_agent import TreeMapAgent
            agent = TreeMapAgent(model=model)
        elif diagram_type == 'circle_map':
            from .thinking_maps.circle_map_agent import CircleMapAgent
            agent = CircleMapAgent(model=model)
        elif diagram_type == 'double_bubble_map':
            from .thinking_maps.double_bubble_map_agent import DoubleBubbleMapAgent
            agent = DoubleBubbleMapAgent(model=model)
        elif diagram_type == 'flow_map':
            from .thinking_maps.flow_map_agent import FlowMapAgent
            agent = FlowMapAgent(model=model)
        elif diagram_type == 'brace_map':
            from .thinking_maps.brace_map_agent import BraceMapAgent
            agent = BraceMapAgent(model=model)
        elif diagram_type == 'multi_flow_map':
            from .thinking_maps.multi_flow_map_agent import MultiFlowMapAgent
            agent = MultiFlowMapAgent(model=model)
        elif diagram_type == 'mind_map' or diagram_type == 'mindmap':
            from .mind_maps.mind_map_agent import MindMapAgent
            agent = MindMapAgent(model=model)
        elif diagram_type == 'concept_map':
            from .concept_maps.concept_map_agent import ConceptMapAgent
            agent = ConceptMapAgent(model=model)
        # Thinking Tools
        elif diagram_type == 'factor_analysis':
            from .thinking_tools.factor_analysis_agent import FactorAnalysisAgent
            agent = FactorAnalysisAgent(model=model)
        elif diagram_type == 'three_position_analysis':
            from .thinking_tools.three_position_analysis_agent import ThreePositionAnalysisAgent
            agent = ThreePositionAnalysisAgent(model=model)
        elif diagram_type == 'perspective_analysis':
            from .thinking_tools.perspective_analysis_agent import PerspectiveAnalysisAgent
            agent = PerspectiveAnalysisAgent(model=model)
        elif diagram_type == 'goal_analysis':
            from .thinking_tools.goal_analysis_agent import GoalAnalysisAgent
            agent = GoalAnalysisAgent(model=model)
        elif diagram_type == 'possibility_analysis':
            from .thinking_tools.possibility_analysis_agent import PossibilityAnalysisAgent
            agent = PossibilityAnalysisAgent(model=model)
        elif diagram_type == 'result_analysis':
            from .thinking_tools.result_analysis_agent import ResultAnalysisAgent
            agent = ResultAnalysisAgent(model=model)
        elif diagram_type == 'five_w_one_h':
            from .thinking_tools.five_w_one_h_agent import FiveWOneHAgent
            agent = FiveWOneHAgent(model=model)
        elif diagram_type == 'whwm_analysis':
            from .thinking_tools.whwm_analysis_agent import WHWMAnalysisAgent
            agent = WHWMAnalysisAgent(model=model)
        elif diagram_type == 'four_quadrant':
            from .thinking_tools.four_quadrant_agent import FourQuadrantAgent
            agent = FourQuadrantAgent(model=model)
        else:
            # Fallback to bubble map
            from .thinking_maps.bubble_map_agent import BubbleMapAgent
            agent = BubbleMapAgent(model=model)
        
        # Generate using the agent
        logger.debug(f"Calling {diagram_type} agent")
        logger.debug(f"User prompt: {user_prompt}")
        logger.debug(f"Language: {language}")
        
        # Bridge map special handling - Three template system:
        # Mode 1: Only pairs provided → identify relationship
        # Mode 2: Pairs + relationship provided → keep as-is  
        # Mode 3: Only relationship provided → generate pairs
        if diagram_type == 'bridge_map' and existing_analogies:
            # Mode 1 or 2: Has existing pairs
            if fixed_dimension:
                logger.debug(f"Bridge map Mode 2: Pairs + Relationship - preserving {len(existing_analogies)} pairs with FIXED dimension '{fixed_dimension}'")
            else:
                logger.debug(f"Bridge map Mode 1: Only pairs - will identify relationship from {len(existing_analogies)} pairs")
            result = await agent.generate_graph(
                user_prompt, 
                language, 
                dimension_preference,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                # Bridge map specific: existing pairs to preserve and fixed dimension
                existing_analogies=existing_analogies,
                fixed_dimension=fixed_dimension
            )
        # Bridge map Mode 3: Relationship-only mode (no pairs, but has fixed dimension)
        elif diagram_type == 'bridge_map' and fixed_dimension and not existing_analogies:
            logger.debug(f"Bridge map Mode 3: Relationship-only - generating pairs for '{fixed_dimension}'")
            result = await agent.generate_graph(
                user_prompt, 
                language, 
                dimension_preference,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                # Bridge map specific: no existing pairs, but fixed dimension for relationship-only mode
                existing_analogies=None,
                fixed_dimension=fixed_dimension
            )
        # Tree map and brace map: Three-scenario system (similar to bridge_map)
        # Scenario 1: Topic only → handled by standard generation below
        # Scenario 2: Topic + dimension → fixed_dimension mode (topic exists)
        # Scenario 3: Dimension only (no topic) → dimension_only_mode
        elif (diagram_type == 'tree_map' or diagram_type == 'brace_map') and fixed_dimension:
            if dimension_only_mode:
                # Scenario 3: Dimension-only mode - user has dimension but no topic
                logger.debug(f"{diagram_type} dimension-only mode: generating topic and children for dimension '{fixed_dimension}'")
                result = await agent.generate_graph(
                    user_prompt, 
                    language, 
                    fixed_dimension,  # Use fixed_dimension as the dimension_preference
                    # Token tracking parameters
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                    # Pass fixed_dimension flag and dimension_only_mode
                    fixed_dimension=fixed_dimension,
                    dimension_only_mode=True
                )
            else:
                # Scenario 2: Topic + dimension mode
                logger.debug(f"{diagram_type} auto-complete mode with FIXED dimension '{fixed_dimension}' (topic exists)")
                result = await agent.generate_graph(
                    user_prompt, 
                    language, 
                    fixed_dimension,  # Use fixed_dimension as the dimension_preference
                    # Token tracking parameters
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                    # Pass fixed_dimension flag
                    fixed_dimension=fixed_dimension
                )
        # For brace maps, tree maps, and bridge maps (without fixed dimension), pass dimension_preference if available
        elif (diagram_type == 'brace_map' or diagram_type == 'tree_map' or diagram_type == 'bridge_map') and dimension_preference:
            if diagram_type == 'brace_map':
                logger.debug(f"Passing decomposition dimension preference to brace map agent: {dimension_preference}")
            elif diagram_type == 'tree_map':
                logger.debug(f"Passing classification dimension preference to tree map agent: {dimension_preference}")
            elif diagram_type == 'bridge_map':
                logger.debug(f"Passing analogy relationship pattern preference to bridge map agent: {dimension_preference}")
            result = await agent.generate_graph(
                user_prompt, 
                language, 
                dimension_preference,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
        else:
            result = await agent.generate_graph(
                user_prompt, 
                language,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
        
        logger.debug(f"Agent result type: {type(result)}")
        logger.debug(f"Agent result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        # Extract spec from agent result if wrapped
        if isinstance(result, dict):
            if 'spec' in result:
                logger.debug("Result contains 'spec' key, returning spec")
                return result['spec']
            elif 'error' not in result:
                logger.debug("Result contains no error, returning as-is")
                return result
            else:
                logger.error(f"Result contains error: {result.get('error')}")
        
        logger.debug("Returning raw result")
        return result
        
    except Exception as e:
        logger.error(f"Agent instantiation/generation failed for {diagram_type}: {e}")
        return {'error': f'Failed to generate {diagram_type}: {str(e)}'}


# REMOVED: _add_basic_styling function - was only creating empty objects
# Style manager provides complete themes, no backend theme generation needed


def _detect_learning_sheet_from_prompt(user_prompt: str, language: str) -> bool:
    """
    Detect if the prompt is requesting a learning sheet.
    
    Args:
        user_prompt: User's input prompt
        language: Language ('zh' or 'en')
    
    Returns:
        bool: True if learning sheet keywords detected
    """
    learning_sheet_keywords = ['半成品', '学习单']
    is_learning_sheet = any(keyword in user_prompt for keyword in learning_sheet_keywords)
    
    if is_learning_sheet:
        logger.debug(f"Learning sheet detected in prompt: '{user_prompt}'")
    
    return is_learning_sheet


def _clean_prompt_for_learning_sheet(user_prompt: str) -> str:
    """
    Remove learning sheet keywords from prompt so LLM generates actual content.
    
    When user asks for "生成鸦片战争的半成品流程图" or "生成鸦片战争的流程图半成品", 
    we want the LLM to generate content about "生成鸦片战争的流程图" (the actual topic), 
    not meta-content about how to create learning sheets.
    
    Args:
        user_prompt: Original user prompt
        
    Returns:
        str: Cleaned prompt with learning sheet keywords removed
    """
    learning_sheet_keywords = ['半成品', '学习单']
    
    cleaned_prompt = user_prompt
    for keyword in learning_sheet_keywords:
        cleaned_prompt = cleaned_prompt.replace(keyword, '').strip()
    
    # Clean up any extra whitespace or punctuation left behind
    import re
    cleaned_prompt = re.sub(r'\s+', ' ', cleaned_prompt)  # Multiple spaces -> single space
    cleaned_prompt = re.sub(r'的图+$', '的', cleaned_prompt)  # "的图" at end -> "的" (for cases like "流程图的半成品图" -> "流程图的")
    cleaned_prompt = re.sub(r'的+$', '', cleaned_prompt)  # Remove trailing "的"
    cleaned_prompt = cleaned_prompt.strip()
    
    logger.debug(f"Cleaned prompt: '{user_prompt}' -> '{cleaned_prompt}'")
    return cleaned_prompt


async def agent_graph_workflow_with_styles(
    user_prompt, 
    language='zh', 
    forced_diagram_type=None, 
    dimension_preference=None, 
    model='qwen',
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type='diagram_generation',
    endpoint_path=None,
    # Bridge map specific: existing pairs for auto-complete mode
    existing_analogies=None,
    # Bridge map specific: fixed dimension/relationship that user has already specified
    fixed_dimension=None,
    # Tree map and brace map: dimension-only mode (user has dimension but no topic)
    dimension_only_mode=None
):
    """
    Simplified agent workflow that directly calls specialized agents.
    
    Args:
        user_prompt (str): User's input prompt
        language (str): Language for processing ('zh' or 'en')
        forced_diagram_type (str, optional): Force a specific diagram type instead of auto-detection.
                                            Used for auto-complete to preserve current diagram type.
        dimension_preference (str, optional): User-specified dimension for brace maps (decomposition) and tree maps (classification).
        model (str): LLM model to use ('qwen', 'deepseek', 'kimi'). Passed through call chain to avoid race conditions.
        existing_analogies (list, optional): For bridge map auto-complete - existing pairs to preserve [{left, right}, ...]
        fixed_dimension (str, optional): For bridge map auto-complete - user-specified relationship pattern that should NOT be changed
        dimension_only_mode (bool, optional): For tree_map/brace_map auto-complete - user has dimension but no topic (generate topic and children)
    
    Returns:
        dict: JSON specification with integrated styles for D3.js rendering
    """
    logger.debug("Starting simplified graph workflow")
    workflow_start_time = time.time()
    
    # Initialize timing variables
    detection_time = 0.0
    topic_time = 0.0
    generation_time = 0.0
    
    try:
        # Validate inputs
        validate_inputs(user_prompt, language)
        
        # Use forced diagram type if provided, otherwise detect from prompt
        if forced_diagram_type:
            diagram_type = forced_diagram_type
            detection_result = {'diagram_type': diagram_type, 'clarity': 'clear', 'has_topic': True}
            logger.debug(f"Using forced diagram type: {diagram_type}")
        else:
            # LLM-based diagram type detection for semantic understanding
            detection_start = time.time()
            detection_result = await _detect_diagram_type_from_prompt(
                user_prompt, 
                language, 
                model,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            detection_time = time.time() - detection_start
            diagram_type = detection_result['diagram_type']
            logger.info(f"Diagram type detection completed in {detection_time:.2f}s: {diagram_type} (clarity: {detection_result['clarity']})")
            
            # Check if prompt is too complex/unclear and should show guidance modal
            if detection_result['clarity'] == 'very_unclear' and not detection_result['has_topic']:
                logger.warning(f"Prompt is too complex or unclear: '{user_prompt}'")
                return {
                    'success': False,
                    'error_type': 'prompt_too_complex',
                    'error': 'Unable to understand the request',
                    'spec': create_error_response(
                        'Prompt is too complex or unclear', 
                        'prompt_too_complex',
                        {'user_prompt': user_prompt}
                    ),
                    'diagram_type': 'mind_map',
                    'topics': [],
                    'style_preferences': {},
                    'language': language,
                    'show_guidance': True
                }
        
        # Extract main topic from prompt using LLM (only if not forced diagram type)
        if not forced_diagram_type:
            # Prompt-based generation: just extract topic, let frontend use default template
            from services.llm_service import llm_service
            
            # Use centralized topic extraction prompt
            topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")
            topic_extraction_prompt = topic_extraction_prompt.format(user_prompt=user_prompt)
            
            topic_start = time.time()
            main_topic = await llm_service.chat(
                prompt=topic_extraction_prompt,
                model=model,
                max_tokens=50,
                temperature=0.1,  # Lower temperature for more deterministic extraction
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            topic_time = time.time() - topic_start
            main_topic = main_topic.strip().strip('"\'')
            logger.info(f"Topic extraction completed in {topic_time:.2f}s: '{main_topic}'")
            
            # Return just the topic and diagram type - frontend will load default template
            total_time = time.time() - workflow_start_time
            logger.info(f"Prompt-based workflow completed in {total_time:.2f}s (detection={detection_time:.2f}s, topic={topic_time:.2f}s)")
            return {
                'success': True,
                'diagram_type': diagram_type,
                'extracted_topic': main_topic,  # Just the topic, no spec
                'language': language,
                'use_default_template': True  # Signal to frontend to use default template + trigger auto-complete
            }
        
        # For forced diagram type (manual generation), use full agent workflow
        # Add learning sheet detection
        is_learning_sheet = _detect_learning_sheet_from_prompt(user_prompt, language)
        logger.debug(f"Learning sheet detected: {is_learning_sheet}")
        
        # Clean the prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(user_prompt) if is_learning_sheet else user_prompt
        if is_learning_sheet:
            logger.debug(f"Using cleaned prompt for generation: '{generation_prompt}'")
        
        # Generate specification using the appropriate agent
        generation_start = time.time()
        spec = await _generate_spec_with_agent(
            generation_prompt, 
            diagram_type, 
            language, 
            dimension_preference, 
            model,
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path,
            diagram_type_for_tracking=diagram_type,
            # Bridge map specific
            existing_analogies=existing_analogies,
            fixed_dimension=fixed_dimension,
            # Tree map and brace map: dimension-only mode
            dimension_only_mode=dimension_only_mode
        )
        generation_time = time.time() - generation_start
        logger.info(f"Diagram generation completed in {generation_time:.2f}s for {diagram_type}")
        
        if not spec or (isinstance(spec, dict) and spec.get('error')):
            logger.error(f"Failed to generate spec for {diagram_type}")
            return {
                'success': False,
                'spec': spec or create_error_response('Failed to generate specification', 'generation', {'diagram_type': diagram_type}),
                'diagram_type': diagram_type,
                'topics': [],
                'style_preferences': {},
                'language': language,
                'is_learning_sheet': is_learning_sheet,
                'hidden_node_percentage': 0
            }
        
        # Calculate hidden percentage for learning sheets (20%)
        hidden_percentage = 0.2 if is_learning_sheet else 0
        
        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            spec['is_learning_sheet'] = is_learning_sheet
            spec['hidden_node_percentage'] = hidden_percentage
            logger.debug(f"Added learning sheet metadata to spec: is_learning_sheet={is_learning_sheet}, hidden_percentage={hidden_percentage}")
        
        # Add metadata to the result
        result = {
            'success': True,
            'spec': spec,
            'diagram_type': diagram_type,
            'topics': [],  # No longer extracted
            'style_preferences': {},  # No longer extracted
            'language': language,
            'is_learning_sheet': is_learning_sheet,  # NEW
            'hidden_node_percentage': hidden_percentage  # NEW
        }
        
        total_time = time.time() - workflow_start_time
        logger.info(f"Simplified workflow completed successfully in {total_time:.2f}s (breakdown: detection={detection_time:.2f}s, topic={topic_time:.2f}s, generation={generation_time:.2f}s), learning sheet: {is_learning_sheet}")
        return result
        
    except ValueError as e:
        logger.error(f"Input validation failed: {e}")
        return {
            'success': False,
            'spec': create_error_response(f'Invalid input: {str(e)}', 'validation', {'language': language}),
            'diagram_type': 'bubble_map',
            'topics': [],
            'style_preferences': {},
            'language': language
        }
    except Exception as e:
        logger.error(f"Simplified workflow failed: {e}")
        return {
            'success': False,
            'spec': create_error_response(f'Generation failed: {str(e)}', 'workflow', {'language': language}),
            'diagram_type': 'bubble_map',
            'topics': [],
            'style_preferences': {},
            'language': language
        }


# ============================================================================
# MAIN AGENT CLASS (for architectural consistency)
# ============================================================================

class MainAgent:
    """
    Main Agent class that provides the BaseAgent interface for the entry point module.
    
    This class wraps the functional approach used in this module to provide
    architectural consistency with other agents while maintaining the existing
    API that the application depends on.
    """
    
    def __init__(self):
        """Initialize the main agent."""
        self.language = 'zh'  # Default language
        self.logger = logger
    
    def generate_graph(self, user_prompt: str, language: str = "zh") -> dict:
        """
        Generate a graph specification from user prompt.
        
        This method implements the BaseAgent interface by delegating to the
        existing functional API in this module.
        
        Args:
            user_prompt: User's input prompt
            language: Language for processing ('zh' or 'en')
            
        Returns:
            dict: Graph specification with styling and metadata
        """
        try:
            # Use LLM-based topic extraction instead of hardcoded string manipulation
            central_topic = extract_central_topic_llm(user_prompt, language)
            
            if not central_topic.strip():
                return create_error_response("Failed to extract topic from prompt", "extraction")
            
            # Use default diagram type and style preferences
            diagram_type = 'concept_map'
            style_preferences = {}
            
            # Generate the graph specification using the simplified workflow
            ConceptMapAgent = _get_concept_map_agent()
            agent = ConceptMapAgent()
            result = agent.generate_graph(user_prompt, language)
            return result.get('spec', create_error_response("Failed to generate concept map", "generation"))
            
        except Exception as e:
            logger.error(f"MainAgent: Generation error: {e}")
            return create_error_response(f"MainAgent generation failed: {str(e)}", "main_agent")
    
    def set_language(self, language: str):
        """Set the language for this agent."""
        self.language = language
    
    def get_language(self) -> str:
        """Get the current language setting."""
        return self.language