"""
Bridge Map Agent

Specialized agent for generating bridge maps that show analogies and similarities.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import get_llm_client, extract_json_from_response

logger = logging.getLogger(__name__)

class BridgeMapAgent(BaseAgent):
    """Agent for generating bridge maps."""
    
    def __init__(self):
        super().__init__()
        self.llm_client = get_llm_client()
        self.diagram_type = "bridge_map"
        
    def generate_graph(self, prompt: str, language: str = "en") -> Dict[str, Any]:
        """
        Generate a bridge map from a prompt.
        
        Args:
            prompt: User's description of what analogy they want to show
            language: Language for generation ("en" or "zh")
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.info(f"🎯 BridgeMapAgent: Generating bridge map for prompt: {prompt}")
            
            # Generate the bridge map specification
            spec = self._generate_bridge_map_spec(prompt, language)
            
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate bridge map specification'
                }
            
            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning(f"BridgeMapAgent: Validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            # Enhance the spec with layout and dimensions
            enhanced_spec = self._enhance_spec(spec)
            
            logger.info(f"✅ BridgeMapAgent: Successfully generated bridge map")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"❌ BridgeMapAgent: Error generating bridge map: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    def _generate_bridge_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
        """Generate the bridge map specification using LLM."""
        try:
            if language == "zh":
                system_prompt = """你是一个专业的思维导图专家，专门创建桥形图。桥形图用于显示类比和相似性，通过桥梁结构连接相关的概念。

请根据用户的描述，创建一个详细的桥形图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "analogy_bridge": "类比桥梁",
  "left_side": {
    "topic": "左侧主题",
    "elements": [
      {
        "id": "left1",
        "text": "左侧元素1",
        "category": "类别1"
      }
    ]
  },
  "right_side": {
    "topic": "右侧主题",
    "elements": [
      {
        "id": "right1",
        "text": "右侧元素1",
        "category": "类别1"
      }
    ]
  },
  "bridge_connections": [
    {
      "from": "left1",
      "to": "right1",
      "label": "类比关系",
      "bridge_text": "桥梁说明"
    }
  ]
}

要求：
- 类比桥梁应该清晰明确
- 左右两侧的主题应该相关且可类比
- 每个元素都应该有对应的类比关系
- 桥梁说明应该解释类比的原因
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""
                
                user_prompt = f"请为以下描述创建一个桥形图：{prompt}"
            else:
                system_prompt = """You are a professional mind mapping expert specializing in bridge maps. Bridge maps are used to show analogies and similarities, connecting related concepts through a bridge structure.

Please create a detailed bridge map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "analogy_bridge": "Analogy Bridge",
  "left_side": {
    "topic": "Left Side Topic",
    "elements": [
      {
        "id": "left1",
        "text": "Left Element 1",
        "category": "Category 1"
      }
    ]
  },
  "right_side": {
    "topic": "Right Side Topic",
    "elements": [
      {
        "id": "right1",
        "text": "Right Element 1",
        "category": "Category 1"
      }
    ]
  },
  "bridge_connections": [
    {
      "from": "left1",
      "to": "right1",
      "label": "Analogy Relationship",
      "bridge_text": "Bridge Explanation"
    }
  ]
}

Requirements:
- Analogy bridge should be clear and specific
- Left and right side topics should be related and comparable
- Each element should have a corresponding analogy relationship
- Bridge explanations should clarify the analogy reasoning
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""
                
                user_prompt = f"Please create a bridge map for the following description: {prompt}"
            
            # Generate response from LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.llm_client.chat_completion(messages)
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                spec = extract_json_from_response(str(response))
            
            if not spec:
                logger.error("BridgeMapAgent: Failed to extract JSON from LLM response")
                return None
                
            return spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error in spec generation: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            # Add layout information
            spec['_layout'] = {
                'type': 'bridge_map',
                'bridge_position': 'center',
                'left_position': 'left',
                'right_position': 'right',
                'element_spacing': 100,
                'bridge_width': 120
            }
            
            # Add recommended dimensions
            spec['_recommended_dimensions'] = {
                'baseWidth': 1000,
                'baseHeight': 600,
                'padding': 80,
                'width': 1000,
                'height': 600
            }
            
            # Add metadata
            spec['_metadata'] = {
                'generated_by': 'BridgeMapAgent',
                'version': '1.0',
                'enhanced': True
            }
            
            return spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error enhancing spec: {e}")
            return spec
    
    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """
        Validate the generated bridge map specification.
        
        Args:
            spec: The specification to validate
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            # Check required fields
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"
            
            if 'analogy_bridge' not in spec or not spec['analogy_bridge']:
                return False, "Missing or empty analogy_bridge"
            
            if 'left_side' not in spec or not isinstance(spec['left_side'], dict):
                return False, "Missing or invalid left_side"
            
            if 'right_side' not in spec or not isinstance(spec['right_side'], dict):
                return False, "Missing or invalid right_side"
            
            if 'bridge_connections' not in spec or not isinstance(spec['bridge_connections'], list):
                return False, "Missing or invalid bridge_connections list"
            
            # Validate left side
            if 'topic' not in spec['left_side'] or not spec['left_side']['topic']:
                return False, "Missing or empty left_side topic"
            
            if 'elements' not in spec['left_side'] or not isinstance(spec['left_side']['elements'], list):
                return False, "Missing or invalid left_side elements"
            
            # Validate right side
            if 'topic' not in spec['right_side'] or not spec['right_side']['topic']:
                return False, "Missing or empty right_side topic"
            
            if 'elements' not in spec['right_side'] or not isinstance(spec['right_side']['elements'], list):
                return False, "Missing or invalid right_side elements"
            
            # Validate elements
            if len(spec['left_side']['elements']) < 2:
                return False, "Left side must have at least 2 elements"
            
            if len(spec['right_side']['elements']) < 2:
                return False, "Right side must have at least 2 elements"
            
            # Check total element count
            total_elements = (len(spec['left_side']['elements']) + 
                             len(spec['right_side']['elements']))
            if total_elements > 16:
                return False, "Too many total elements (max 16)"
            
            # Validate bridge connections
            if len(spec['bridge_connections']) < min(len(spec['left_side']['elements']), len(spec['right_side']['elements'])):
                return False, "Must have bridge connections for most elements"
            
            # Check for valid IDs
            valid_ids = set()
            for elem in spec['left_side']['elements']:
                valid_ids.add(elem.get('id'))
            for elem in spec['right_side']['elements']:
                valid_ids.add(elem.get('id'))
            
            for conn in spec['bridge_connections']:
                if conn.get('from') not in valid_ids or conn.get('to') not in valid_ids:
                    return False, "Invalid bridge connection references"
                if 'label' not in conn or not conn['label']:
                    return False, "Missing or empty bridge connection label"
                if 'bridge_text' not in conn or not conn['bridge_text']:
                    return False, "Missing or empty bridge text"
            
            return True, "Specification is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing bridge map specification.
        
        Args:
            spec: Existing specification to enhance
            
        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.info("BridgeMapAgent: Enhancing existing specification")
            
            # If already enhanced, return as-is
            if spec.get('_metadata', {}).get('enhanced'):
                return {'success': True, 'spec': spec}
            
            # Enhance the spec
            enhanced_spec = self._enhance_spec(spec)
            
            return {
                'success': True,
                'spec': enhanced_spec
            }
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error enhancing spec: {e}")
            return {
                'success': False,
                'error': f'Enhancement failed: {str(e)}'
            }
