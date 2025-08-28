"""
Circle Map Agent

Specialized agent for generating circle maps that define topics in context.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import get_llm_client, extract_json_from_response

logger = logging.getLogger(__name__)

class CircleMapAgent(BaseAgent):
    """Agent for generating circle maps."""
    
    def __init__(self):
        super().__init__()
        self.llm_client = get_llm_client()
        self.diagram_type = "circle_map"
        
    def generate_graph(self, prompt: str, language: str = "en") -> Dict[str, Any]:
        """
        Generate a circle map from a prompt.
        
        Args:
            prompt: User's description of what they want to define
            language: Language for generation ("en" or "zh")
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.info(f"🎯 CircleMapAgent: Generating circle map for prompt: {prompt}")
            
            # Generate the circle map specification
            spec = self._generate_circle_map_spec(prompt, language)
            
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate circle map specification'
                }
            
            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning(f"CircleMapAgent: Validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            # Enhance the spec with layout and dimensions
            enhanced_spec = self._enhance_spec(spec)
            
            logger.info(f"✅ CircleMapAgent: Successfully generated circle map")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"❌ CircleMapAgent: Error generating circle map: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    def _generate_circle_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
        """Generate the circle map specification using LLM."""
        try:
            if language == "zh":
                system_prompt = """你是一个专业的思维导图专家，专门创建圆圈图。圆圈图用于在上下文中定义主题，通过同心圆展示主题的不同层次和方面。

请根据用户的描述，创建一个详细的圆圈图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "central_topic": "中心主题",
  "inner_circle": {
    "title": "内圈标题",
    "content": "内圈内容描述"
  },
  "middle_circle": {
    "title": "中圈标题",
    "content": "中圈内容描述"
  },
  "outer_circle": {
    "title": "外圈标题",
    "content": "外圈内容描述"
  },
  "context_elements": [
    {
      "id": "ctx1",
      "text": "上下文元素1",
      "category": "类别1"
    }
  ],
  "connections": [
    {
      "from": "central_topic",
      "to": "ctx1",
      "label": "关系标签"
    }
  ]
}

要求：
- 中心主题应该清晰明确
- 三个圆圈应该代表不同的层次或方面
- 上下文元素应该与主题相关且有意义
- 每个元素都应该有明确的连接
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""
                
                user_prompt = f"请为以下描述创建一个圆圈图：{prompt}"
            else:
                system_prompt = """You are a professional mind mapping expert specializing in circle maps. Circle maps are used to define topics in context, showing different levels and aspects through concentric circles.

Please create a detailed circle map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "central_topic": "Central Topic",
  "inner_circle": {
    "title": "Inner Circle Title",
    "content": "Inner circle content description"
  },
  "middle_circle": {
    "title": "Middle Circle Title",
    "content": "Middle circle content description"
  },
  "outer_circle": {
    "title": "Outer Circle Title",
    "content": "Outer circle content description"
  },
  "context_elements": [
    {
      "id": "ctx1",
      "text": "Context Element 1",
      "category": "Category 1"
    }
  ],
  "connections": [
    {
      "from": "central_topic",
      "to": "ctx1",
      "label": "Relationship Label"
    }
  ]
}

Requirements:
- Central topic should be clear and specific
- Three circles should represent different levels or aspects
- Context elements should be relevant and meaningful
- Each element should have a clear connection
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""
                
                user_prompt = f"Please create a circle map for the following description: {prompt}"
            
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
                logger.error("CircleMapAgent: Failed to extract JSON from LLM response")
                return None
                
            return spec
            
        except Exception as e:
            logger.error(f"CircleMapAgent: Error in spec generation: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            # Add layout information
            spec['_layout'] = {
                'type': 'circle_map',
                'central_position': 'center',
                'circle_spacing': 80,
                'inner_radius': 60,
                'middle_radius': 140,
                'outer_radius': 220
            }
            
            # Add recommended dimensions
            spec['_recommended_dimensions'] = {
                'baseWidth': 900,
                'baseHeight': 700,
                'padding': 100,
                'width': 900,
                'height': 700
            }
            
            # Add metadata
            spec['_metadata'] = {
                'generated_by': 'CircleMapAgent',
                'version': '1.0',
                'enhanced': True
            }
            
            return spec
            
        except Exception as e:
            logger.error(f"CircleMapAgent: Error enhancing spec: {e}")
            return spec
    
    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """
        Validate the generated circle map specification.
        
        Args:
            spec: The specification to validate
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            # Check required fields
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"
            
            if 'central_topic' not in spec or not spec['central_topic']:
                return False, "Missing or empty central_topic"
            
            if 'inner_circle' not in spec or not isinstance(spec['inner_circle'], dict):
                return False, "Missing or invalid inner_circle"
            
            if 'middle_circle' not in spec or not isinstance(spec['middle_circle'], dict):
                return False, "Missing or invalid middle_circle"
            
            if 'outer_circle' not in spec or not isinstance(spec['outer_circle'], dict):
                return False, "Missing or invalid outer_circle"
            
            if 'context_elements' not in spec or not isinstance(spec['context_elements'], list):
                return False, "Missing or invalid context_elements list"
            
            if 'connections' not in spec or not isinstance(spec['connections'], list):
                return False, "Missing or invalid connections list"
            
            # Validate circle content
            for circle_name, circle_data in [('inner_circle', spec['inner_circle']), 
                                           ('middle_circle', spec['middle_circle']), 
                                           ('outer_circle', spec['outer_circle'])]:
                if 'title' not in circle_data or not circle_data['title']:
                    return False, f"Missing or empty title in {circle_name}"
                if 'content' not in circle_data or not circle_data['content']:
                    return False, f"Missing or empty content in {circle_name}"
            
            # Validate context elements
            if len(spec['context_elements']) < 2:
                return False, "Must have at least 2 context elements"
            
            if len(spec['context_elements']) > 12:
                return False, "Too many context elements (max 12)"
            
            # Validate connections
            if len(spec['connections']) < len(spec['context_elements']):
                return False, "Each context element must have at least one connection"
            
            # Check for valid IDs
            valid_ids = {'central_topic'} | {elem.get('id') for elem in spec['context_elements']}
            for conn in spec['connections']:
                if conn.get('from') not in valid_ids or conn.get('to') not in valid_ids:
                    return False, "Invalid connection references"
            
            return True, "Specification is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing circle map specification.
        
        Args:
            spec: Existing specification to enhance
            
        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.info("CircleMapAgent: Enhancing existing specification")
            
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
            logger.error(f"CircleMapAgent: Error enhancing spec: {e}")
            return {
                'success': False,
                'error': f'Enhancement failed: {str(e)}'
            }
