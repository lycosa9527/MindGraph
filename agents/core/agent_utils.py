"""
Agent Utilities Module for MindGraph

This module contains utility functions that support the LangChain agent work,
including parsing functions, fallback logic, and helper functions for
processing agent outputs and handling edge cases.
"""

import re
import json
import yaml
import os
from config.settings import config
import logging
from dotenv import load_dotenv

# Load environment variables for logging configuration
load_dotenv()

logger = logging.getLogger(__name__)


def extract_json_from_response(response_content):
    """
    Extract JSON from LLM response content.
    
    Handles legitimate formatting issues:
    - Markdown code blocks (```json ... ```)
    - Unicode quote characters (smart quotes)
    - Trailing commas (common JSON extension)
    - Basic whitespace/control characters
    
    Does NOT attempt to fix malformed or truncated JSON.
    If JSON is invalid, returns None and logs the error with full context.
    
    Args:
        response_content (str): Raw response content from LLM
        
    Returns:
        dict or None: Extracted JSON data or None if failed
    """
    if not response_content:
        logger.warning("Empty response content provided")
        return None
    
    try:
        content = str(response_content).strip()
        
        # Extract JSON content - try markdown blocks first, then direct content
        json_content = None
        
        # Check for markdown code blocks
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
        else:
            # Try to find JSON object or array in content
            # Look for { ... } or [ ... ] patterns
            obj_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            arr_match = re.search(r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]', content, re.DOTALL)
            
            if obj_match:
                json_content = obj_match.group(0)
            elif arr_match:
                json_content = arr_match.group(0)
            else:
                # Fallback: try greedy match for { ... }
                greedy_match = re.search(r'\{.*\}', content, re.DOTALL)
                if greedy_match:
                    json_content = greedy_match.group(0)
        
        if not json_content:
            # No JSON-like content found
            content_preview = content[:500] + "..." if len(content) > 500 else content
            logger.error(f"Failed to extract JSON: No JSON structure found in response. Content: {content_preview}")
            return None
        
        # Clean legitimate formatting issues (not structural problems)
        cleaned = _clean_json_string(json_content)
        
        # Try to parse - if it fails, that's a real error
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Log the actual error with context
            error_pos = getattr(e, 'pos', None)
            error_msg = str(e)
            content_preview = cleaned[:500] + "..." if len(cleaned) > 500 else cleaned
            
            logger.error(
                f"Failed to parse JSON: {error_msg} "
                f"(position: {error_pos}). "
                f"Content preview: {content_preview}"
            )
            return None
        
    except Exception as e:
        # Unexpected error - log with full context
        content_preview = str(response_content)[:500] + "..." if len(str(response_content)) > 500 else str(response_content)
        logger.error(f"Unexpected error extracting JSON: {e}. Content preview: {content_preview}", exc_info=True)
        return None


def _remove_js_comments_safely(text: str) -> str:
    """
    Remove JavaScript-style comments from JSON, but only outside of string values.
    
    This function respects JSON string boundaries to avoid corrupting URLs,
    file paths, or other string values that contain // or /* */ sequences.
    
    Args:
        text: JSON text that may contain comments
        
    Returns:
        Text with comments removed, but string values preserved
    """
    result = []
    i = 0
    in_string = False
    escape_next = False
    
    while i < len(text):
        char = text[i]
        
        if escape_next:
            # Escaped character - add as-is and reset escape flag
            result.append(char)
            escape_next = False
            i += 1
            continue
        
        if char == '\\':
            # Escape character - next char is escaped
            result.append(char)
            escape_next = True
            i += 1
            continue
        
        if char == '"':
            # Toggle string state
            in_string = not in_string
            result.append(char)
            i += 1
            continue
        
        if in_string:
            # Inside string - add character as-is
            result.append(char)
            i += 1
            continue
        
        # Outside string - check for comments
        if i < len(text) - 1 and text[i:i+2] == '//':
            # Single-line comment - skip until end of line
            while i < len(text) and text[i] != '\n':
                i += 1
            # Keep the newline if present
            if i < len(text) and text[i] == '\n':
                result.append('\n')
                i += 1
        elif i < len(text) - 1 and text[i:i+2] == '/*':
            # Multi-line comment - skip until */
            i += 2
            # Continue until we find */ or reach the end of text
            # Match single-line comment handler pattern: loop until end, always consume chars
            while i < len(text):
                # Check if we can look ahead for */ (need at least 2 chars: current + next)
                # Use i + 1 < len(text) for clarity (equivalent to i < len(text) - 1)
                if i + 1 < len(text) and text[i:i+2] == '*/':
                    i += 2
                    break
                # Always consume current character (even if it's the last one)
                # This ensures we properly skip all characters in unclosed comments
                i += 1
        else:
            # Regular character - add as-is
            result.append(char)
            i += 1
    
    return ''.join(result)


def _clean_json_string(text: str) -> str:
    """
    Clean JSON string by fixing legitimate formatting issues.
    
    Only fixes issues that don't change JSON semantics:
    - Unicode quote normalization
    - Control character removal
    - Trailing comma removal (common JSON extension)
    - JS-style comments (only outside string values)
    
    Does NOT attempt to fix structural problems (truncated JSON, missing brackets, etc.)
    
    Args:
        text: Raw JSON text to clean
        
    Returns:
        Cleaned text
    """
    # Remove markdown code block markers if still present
    text = re.sub(r'```(?:json)?\s*\n?', '', text)
    text = re.sub(r'```\s*\n?', '', text)
    
    # Remove leading/trailing whitespace and backticks
    text = text.strip().strip('`')
    
    # Replace smart quotes with ASCII equivalents (legitimate fix)
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace('"', '"').replace('"', '"')
    
    # Remove zero-width and control characters (legitimate fix)
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    
    # Remove JS-style comments (only outside string values to avoid corrupting URLs/paths)
    text = _remove_js_comments_safely(text)
    
    # Remove trailing commas before ] or } (common JSON extension, legitimate fix)
    text = re.sub(r',\s*(\]|\})', r'\1', text)
    
    return text.strip()


def parse_topic_extraction_result(result, language='zh'):
    """
    Parse the result from topic extraction agent
    
    Args:
        result (str): Raw result from the agent
        language (str): Language context ('zh' or 'en')
    
    Returns:
        tuple: (topic1, topic2) extracted topics
    """
    # Clean up the result
    topics = result.strip()
    
    # Handle case where LLM returns a complete JSON block
    if topics.startswith("```json"):
        # Extract the content between ```json and ```
        json_match = re.search(r'```json\s*\n(.*?)\n```', topics, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
            try:
                data = json.loads(json_content)
                if 'left' in data and 'right' in data:
                    left_topic = data['left'].strip()
                    right_topic = data['right'].strip()
                    if left_topic != "A" and right_topic != "B":
                        return left_topic, right_topic
            except json.JSONDecodeError:
                pass
    
    # Try to extract topics from LLM response
    if language == 'zh':
        # Handle Chinese "和" separator
        if "和" in topics:
            parts = topics.split("和")
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()
    else:
        # Handle English " and " separator
        if " and " in topics:
            parts = topics.split(" and ")
            if len(parts) >= 2:
                return parts[0].strip(), parts[1].strip()
    
    # Try to extract individual words from LLM response
    if language == 'zh':
        # For Chinese, extract Chinese characters
        chinese_words = re.findall(r'[\u4e00-\u9fff]+', topics)
        if len(chinese_words) >= 2:
            return chinese_words[0], chinese_words[1]
    else:
        # For English, extract English words
        words = re.findall(r'\b\w+\b', topics)
        if len(words) >= 2:
            return words[0], words[1]
    
    # If parsing completely failed, use fallback
    logger.debug("Topic extraction parsing failed, using fallback")
    return extract_topics_from_prompt(topics)


def extract_topics_from_prompt(user_prompt):
    """
    Extract two topics from the original user prompt using fallback logic
    
    Args:
        user_prompt (str): User's input prompt
    
    Returns:
        tuple: (topic1, topic2) extracted topics
    """
    is_zh = any('\u4e00' <= ch <= '\u9fff' for ch in user_prompt)
    
    if is_zh:
        # For Chinese prompts
        # Look for specific car brands and other topics
        car_brands = ['宝马', '奔驰', '奥迪', '大众', '丰田', '本田', '福特', '雪佛兰']
        found_brands = []
        for brand in car_brands:
            if brand in user_prompt:
                found_brands.append(brand)
        
        if len(found_brands) >= 2:
            return found_brands[0], found_brands[1]
        
        # For Chinese prompts - use generic character extraction
        # Fallback: extract individual Chinese characters (2-4 characters each)
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,4}', user_prompt)
        if len(chinese_words) >= 2:
            return chinese_words[0], chinese_words[1]
    else:
        # For English prompts - use generic word extraction
        # Fallback: extract any two distinct words, but filter out common verbs and prepositions
        common_words_to_skip = ['compare', 'and', 'or', 'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must', 'shall', 'about', 'with', 'for', 'to', 'of', 'in', 'on', 'at', 'by', 'from', 'up', 'down', 'out', 'off', 'over', 'under', 'between', 'among', 'through', 'during', 'before', 'after', 'since', 'until', 'while', 'when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom', 'whose']
        words = re.findall(r'\b\w+\b', user_prompt.lower())
        filtered_words = [word for word in words if word not in common_words_to_skip and len(word) > 2]
        if len(filtered_words) >= 2:
            return filtered_words[0], filtered_words[1]
    
    # Final fallback
    return "Topic A", "Topic B"


def parse_characteristics_result(result, topic1, topic2):
    """
    Parse the result from characteristics generation agent
    
    Args:
        result (str): Raw result from the agent
        topic1 (str): First topic
        topic2 (str): Second topic
    
    Returns:
        dict: Parsed characteristics specification
    """
    # Extract YAML from the result
    text = result.strip()
    
    # Handle case where LLM returns a complete JSON block
    if text.startswith("```json"):
        # Extract the content between ```json and ```
        json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
            try:
                data = json.loads(json_content)
                # Convert JSON to YAML format for processing
                text = yaml.dump(data, default_flow_style=False, allow_unicode=True)
            except json.JSONDecodeError:
                # Fallback: remove json markers
                text = text.replace("```json", "").replace("```", "").strip()
    else:
        # Remove any code block markers
        if text.startswith("```yaml"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        text = text.strip('`\n ')
    
    # Clean up any remaining template placeholders
    text = text.replace('"trait1"', '"Common trait"')
    text = text.replace('"feature1"', '"Unique feature"')
    text = text.replace('"特征1"', '"共同特征"')
    text = text.replace('"特点1"', '"独特特点"')
    
    # Parse YAML
    try:
        spec = yaml.safe_load(text)
        logger.debug(f"After YAML load, spec type: {type(spec)}, value: {spec}")
        if not isinstance(spec, dict):
            raise yaml.YAMLError("YAML parsing did not return a dict")
        if spec is None:
            raise yaml.YAMLError("YAML parsing returned None")
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}")
        logger.error(f"Raw text: {text}")
        # Try to extract just the lists
        spec = {"similarities": [], "left_differences": [], "right_differences": []}
        lines = text.split('\n')
        current_key = None
        for line in lines:
            line = line.strip()
            if line.startswith('similarities:'):
                current_key = 'similarities'
            elif line.startswith('left_differences:'):
                current_key = 'left_differences'
            elif line.startswith('right_differences:'):
                current_key = 'right_differences'
            elif line.startswith('- ') and current_key:
                item = line[2:].strip().strip('"')
                if item and not item.startswith('trait') and not item.startswith('feature'):
                    spec[current_key].append(item)
    
    # Validate and ensure all required fields exist
    if not spec.get('similarities') or len(spec.get('similarities', [])) < 2:
        spec['similarities'] = ["Comparable"]
    if not spec.get('left_differences') or len(spec.get('left_differences', [])) < 2:
        spec['left_differences'] = ["Unique"]
    if not spec.get('right_differences') or len(spec.get('right_differences', [])) < 2:
        spec['right_differences'] = ["Unique"]
    
    # Check if we got meaningful content (not just template placeholders)
    has_meaningful_content = False
    for key in ['similarities', 'left_differences', 'right_differences']:
        for item in spec.get(key, []):
            if not any(placeholder in str(item).lower() for placeholder in ['trait', 'feature', '特征', '特点', 'comparable', 'unique']):
                has_meaningful_content = True
                break
    
    if not has_meaningful_content:
        raise Exception("No meaningful content generated, using fallback")
    
    return spec


def generate_characteristics_fallback(topic1, topic2):
    """
    Generate fallback characteristics when agent fails
    
    Args:
        topic1 (str): First topic
        topic2 (str): Second topic
    
    Returns:
        dict: Fallback characteristics specification
    """
    # Return general fallback spec based on topics
    if "photosynthesis" in topic1.lower() or "cellular respiration" in topic2.lower():
        return {
            "similarities": ["Biological processes", "Energy involved", "Plant cells", "Life essential", "Chemical reactions"],
            "left_differences": ["Food production", "Sunlight needed", "Green parts", "Oxygen creation", "Leaf location"],
            "right_differences": ["Food consumption", "Dark operation", "All cells", "Oxygen need", "Everywhere location"]
        }
    elif "d3" in topic1.lower() or "bubble" in topic2.lower() or "d3" in topic2.lower() or "bubble" in topic1.lower():
        return {
            "similarities": ["Visual diagrams", "Text commands", "Chart creation", "Computer tools", "Explanation aids"],
            "left_differences": ["Multiple types", "Wide usage", "Rich features", "Professional", "Flexible"],
            "right_differences": ["Comparison focus", "Simple use", "Learning tool", "Clear structure", "Easy understanding"]
        }
    elif any(brand in topic1.lower() or brand in topic2.lower() for brand in ['宝马', '奔驰', 'bmw', 'mercedes', 'audi', 'volkswagen', 'toyota', 'honda', 'ford', 'chevrolet']):
        return {
            "similarities": ["Car manufacturers", "Famous brands", "Global sales", "Quality focus", "Large customer base"],
            "left_differences": ["Unique designs", "Specific markets", "Different styles", "Special features", "Price range"],
            "right_differences": ["Company history", "Model variety", "Different strengths", "Brand reputation", "Market segments"]
        }
    elif any(animal in topic1.lower() or animal in topic2.lower() for animal in ['cat', 'dog', 'bird', 'fish', '猫', '狗', '鸟', '鱼']):
        return {
            "similarities": ["Animals", "Food water", "Home living", "Popular pets", "Unique behaviors"],
            "left_differences": ["Food preferences", "Body shapes", "Movement styles", "Care needs", "Lifespans"],
            "right_differences": ["Sound types", "Social needs", "Living spaces", "Abilities", "Personalities"]
        }
    elif any(fruit in topic1.lower() or fruit in topic2.lower() for fruit in ['apple', 'orange', '苹果', '橙子']):
        return {
            "similarities": ["Fruits", "Healthy", "Tree growth", "Global consumption", "Vitamins"],
            "left_differences": ["Taste profiles", "Growth requirements", "Appearances", "Nutrients", "Cooking uses"],
            "right_differences": ["Seasons", "Storage needs", "Health benefits", "Cultural importance", "Eating methods"]
        }
    elif any(tech in topic1.lower() or tech in topic2.lower() for tech in ['computer', 'phone', 'laptop', 'tablet', '电脑', '手机']):
        return {
            "similarities": ["Electronic devices", "Electricity use", "Communication tools", "Screens", "Charging needed"],
            "left_differences": ["Sizes", "Uses", "Features", "Usage methods", "Prices"],
            "right_differences": ["Portability", "Power needs", "User groups", "Capabilities", "Costs"]
        }
    else:
        return {
            "similarities": ["Comparable", "Features", "Useful", "Differences", "Interesting"],
            "left_differences": ["Special features", "Different", "Advantages"],
            "right_differences": ["Special features", "Different", "Advantages"]
        }


def detect_language(text):
    """
    Detect the language of the input text
    
    Args:
        text (str): Input text to analyze
    
    Returns:
        str: 'zh' for Chinese, 'en' for English
    """
    # Count Chinese characters
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    # Count English characters
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if chinese_chars > english_chars:
        return 'zh'
    else:
        return 'en'


def validate_agent_output(output, expected_type):
    """
    Validate agent output format and content
    
    Args:
        output (str): Agent output to validate
        expected_type (str): Expected output type ('topics' or 'characteristics')
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not output or not output.strip():
        return False
    
    if expected_type == 'topics':
        # Check if output contains at least two distinct items
        if ' and ' in output or '和' in output:
            return True
        return False
    
    elif expected_type == 'characteristics':
        # Check if output contains YAML-like structure
        if 'similarities:' in output and 'left_differences:' in output and 'right_differences:' in output:
            return True
        return False
    
    return False 


def extract_topics_with_agent(user_prompt, language='zh'):
    """
    Use LangChain agent to extract two topics for comparison
    Args:
        user_prompt (str): User's input prompt
        language (str): Language for processing ('zh' or 'en')
    Returns:
        tuple: (topic1, topic2) extracted topics
    Raises:
        ValueError: If user_prompt is empty or invalid
    """
    # Input validation - raise error instead of using fallback placeholder
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        logger.error("Invalid user_prompt provided - empty or not a string")
        raise ValueError("user_prompt cannot be empty")
    
    if not isinstance(language, str) or language not in ['zh', 'en']:
        logger.warning(f"Invalid language '{language}', defaulting to 'zh'")
        language = 'zh'
    
    logger.debug(f"Agent: Extracting topics from prompt: {user_prompt}")
    # Create the topic extraction chain
    from ..main_agent import create_topic_extraction_chain
    topic_chain = create_topic_extraction_chain(language)
    try:
        # Run the chain (refactored to use .invoke())
        result = topic_chain.invoke({"user_prompt": user_prompt})
        logger.debug(f"Agent: Topic extraction result: {result}")
        # Parse the result using utility function
        topics = parse_topic_extraction_result(result, language)
        return topics
    except Exception as e:
        logger.error(f"Agent: Topic extraction failed: {e}")
        # Fallback to utility function
        return extract_topics_from_prompt(user_prompt) 


def generate_characteristics_with_agent(topic1, topic2, language='zh'):
    """
    Use LangChain agent to generate characteristics for double bubble map
    Args:
        topic1 (str): First topic
        topic2 (str): Second topic
        language (str): Language for processing ('zh' or 'en')
    Returns:
        dict: Characteristics specification
    Raises:
        ValueError: If topic1 or topic2 is empty or invalid
    """
    # Input validation - raise error instead of using placeholder
    if not isinstance(topic1, str) or not topic1.strip():
        logger.error("Invalid topic1 provided - empty or not a string")
        raise ValueError("topic1 cannot be empty")
    
    if not isinstance(topic2, str) or not topic2.strip():
        logger.error("Invalid topic2 provided - empty or not a string")
        raise ValueError("topic2 cannot be empty")
    
    if not isinstance(language, str) or language not in ['zh', 'en']:
        logger.warning(f"Invalid language '{language}', defaulting to 'zh'")
        language = 'zh'
    
    logger.debug(f"Agent: Generating characteristics for {topic1} vs {topic2}")
    # Create the characteristics generation chain
    from ..main_agent import create_characteristics_chain
    char_chain = create_characteristics_chain(language)
    try:
        # Run the chain (refactored to use .invoke())
        result = char_chain.invoke({"topic1": topic1, "topic2": topic2})
        logger.debug(f"Agent: Characteristics generation result: {result}")
        # Parse the result using utility function
        spec = parse_characteristics_result(result, topic1, topic2)
        return spec
    except Exception as e:
        logger.error(f"Agent: Characteristics generation failed: {e}")
        # Fallback to utility function
        from agent_utils import generate_characteristics_fallback
        return generate_characteristics_fallback(topic1, topic2) 