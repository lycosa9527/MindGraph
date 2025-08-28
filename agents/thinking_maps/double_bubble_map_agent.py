"""
Double Bubble Map Agent

Specialized agent for generating double bubble maps that compare and contrast two topics.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import get_llm_client, extract_json_from_response

logger = logging.getLogger(__name__)

class DoubleBubbleMapAgent(BaseAgent):
    """Agent for generating double bubble maps."""
    
    def __init__(self):
        super().__init__()
        self.llm_client = get_llm_client()
        self.diagram_type = "double_bubble_map"
        
    def generate_graph(self, prompt: str, language: str = "en") -> Dict[str, Any]:
        """
        Generate a double bubble map from a prompt.
        
        Args:
            prompt: User's description of what they want to compare
            language: Language for generation ("en" or "zh")
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.info(f"🎯 DoubleBubbleMapAgent: Generating double bubble map for prompt: {prompt}")
            
            # Generate the double bubble map specification
            spec = self._generate_double_bubble_map_spec(prompt, language)
            
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate double bubble map specification'
                }
            
            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning(f"DoubleBubbleMapAgent: Validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            # Enhance the spec with layout and dimensions
            enhanced_spec = self._enhance_spec(spec)
            
            logger.info(f"✅ DoubleBubbleMapAgent: Successfully generated double bubble map")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"❌ DoubleBubbleMapAgent: Error generating double bubble map: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    def _generate_double_bubble_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
        """Generate the double bubble map specification using LLM."""
        try:
            if language == "zh":
                system_prompt = """你是一个专业的思维导图专家，专门创建双气泡图。双气泡图用于比较和对比两个主题的异同。

请根据用户的描述，创建一个详细的双气泡图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic1": "主题1",
  "topic2": "主题2",
  "topic1_attributes": [
    {
      "id": "t1_attr1",
      "text": "主题1的属性1",
      "category": "类别1"
    }
  ],
  "topic2_attributes": [
    {
      "id": "t2_attr1",
      "text": "主题2的属性1",
      "category": "类别1"
    }
  ],
  "shared_attributes": [
    {
      "id": "shared1",
      "text": "共同属性1",
      "category": "共同类别"
    }
  ],
  "connections": [
    {
      "from": "topic1",
      "to": "t1_attr1",
      "label": "关系标签"
    }
  ]
}

要求：
- 两个主题应该明确且可比较
- 每个主题的属性应该具体且有意义
- 共同属性应该反映两个主题的相似之处
- 每个属性都应该有明确的连接
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""
                
                user_prompt = f"请为以下描述创建一个双气泡图：{prompt}"
            else:
                system_prompt = """You are a professional mind mapping expert specializing in double bubble maps. Double bubble maps are used to compare and contrast two topics.

Please create a detailed double bubble map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic1": "Topic 1",
  "topic2": "Topic 2",
  "topic1_attributes": [
    {
      "id": "t1_attr1",
      "text": "Topic 1 Attribute 1",
      "category": "Category 1"
    }
  ],
  "topic2_attributes": [
    {
      "id": "t2_attr1",
      "text": "Topic 2 Attribute 1",
      "category": "Category 1"
    }
  ],
  "shared_attributes": [
    {
      "id": "shared1",
      "text": "Shared Attribute 1",
      "category": "Shared Category"
    }
  ],
  "connections": [
    {
      "from": "topic1",
      "to": "t1_attr1",
      "label": "Relationship Label"
    }
  ]
}

Requirements:
- Both topics should be clear and comparable
- Each topic's attributes should be concrete and meaningful
- Shared attributes should reflect similarities between topics
- Each attribute should have a clear connection
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""
                
                user_prompt = f"Please create a double bubble map for the following description: {prompt}"
            
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
                logger.error("DoubleBubbleMapAgent: Failed to extract JSON from LLM response")
                return None
                
            return spec
            
        except Exception as e:
            logger.error(f"DoubleBubbleMapAgent: Error in spec generation: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            # Add layout information
            spec['_layout'] = {
                'type': 'double_bubble_map',
                'topic1_position': 'left',
                'topic2_position': 'right',
                'shared_position': 'center',
                'attribute_spacing': 100,
                'bubble_radius': 50
            }
            
            # Add recommended dimensions
            spec['_recommended_dimensions'] = {
                'baseWidth': 1000,
                'baseHeight': 700,
                'padding': 100,
                'width': 1000,
                'height': 700
            }
            
            # Add metadata
            spec['_metadata'] = {
                'generated_by': 'DoubleBubbleMapAgent',
                'version': '1.0',
                'enhanced': True
            }
            
            return spec
            
        except Exception as e:
            logger.error(f"DoubleBubbleMapAgent: Error enhancing spec: {e}")
            return spec
    
    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """
        Validate the generated double bubble map specification.
        
        Args:
            spec: The specification to validate
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            # Check required fields
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"
            
            if 'topic1' not in spec or not spec['topic1']:
                return False, "Missing or empty topic1"
            
            if 'topic2' not in spec or not spec['topic2']:
                return False, "Missing or empty topic2"
            
            if 'topic1_attributes' not in spec or not isinstance(spec['topic1_attributes'], list):
                return False, "Missing or invalid topic1_attributes list"
            
            if 'topic2_attributes' not in spec or not isinstance(spec['topic2_attributes'], list):
                return False, "Missing or invalid topic2_attributes list"
            
            if 'shared_attributes' not in spec or not isinstance(spec['shared_attributes'], list):
                return False, "Missing or invalid shared_attributes list"
            
            if 'connections' not in spec or not isinstance(spec['connections'], list):
                return False, "Missing or invalid connections list"
            
            # Validate attributes
            if len(spec['topic1_attributes']) < 2:
                return False, "Topic1 must have at least 2 attributes"
            
            if len(spec['topic2_attributes']) < 2:
                return False, "Topic2 must have at least 2 attributes"
            
            if len(spec['shared_attributes']) < 1:
                return False, "Must have at least 1 shared attribute"
            
            # Check total attribute count
            total_attrs = (len(spec['topic1_attributes']) + 
                          len(spec['topic2_attributes']) + 
                          len(spec['shared_attributes']))
            if total_attrs > 20:
                return False, "Too many total attributes (max 20)"
            
            # Validate connections
            if len(spec['connections']) < total_attrs:
                return False, "Each attribute must have at least one connection"
            
            # Check for valid IDs
            valid_ids = {'topic1', 'topic2'} | {attr.get('id') for attr in spec['topic1_attributes']} | {attr.get('id') for attr in spec['topic2_attributes']} | {attr.get('id') for attr in spec['shared_attributes']}
            for conn in spec['connections']:
                if conn.get('from') not in valid_ids or conn.get('to') not in valid_ids:
                    return False, "Invalid connection references"
            
            return True, "Specification is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing double bubble map specification.
        
        Args:
            spec: Existing specification to enhance
            
        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.info("DoubleBubbleMapAgent: Enhancing existing specification")
            
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
            logger.error(f"DoubleBubbleMapAgent: Error enhancing spec: {e}")
            return {
                'success': False,
                'error': f'Enhancement failed: {str(e)}'
            }
