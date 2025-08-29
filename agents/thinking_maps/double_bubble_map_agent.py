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
            logger.info(f"DoubleBubbleMapAgent: Starting double bubble map generation for prompt")
            
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
            
            logger.info(f"DoubleBubbleMapAgent: Double bubble map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"DoubleBubbleMapAgent: Double bubble map generation failed: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    def _generate_double_bubble_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
        """Generate the double bubble map specification using LLM."""
        try:
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get prompt from centralized system
            # Use agent-specific format that matches validation
            system_prompt = get_prompt("double_bubble_map_agent", language, "generation")
            
            if not system_prompt:
                # Fallback to general format if agent-specific not found
                system_prompt = get_prompt("double_bubble_map", language, "generation")
            
            if not system_prompt:
                logger.error(f"DoubleBubbleMapAgent: No prompt found for language {language}")
                return None
                
            user_prompt = f"请为以下描述创建一个双气泡图：{prompt}" if language == "zh" else f"Please create a double bubble map for the following description: {prompt}"
            
            # Generate response from LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = self.llm_client.chat_completion(messages)
            
            # Response already generated above with centralized prompts
            
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
        """Enhance the specification with layout and dimension recommendations and convert to renderer format."""
        try:
            # Convert agent format (topic1/topic2) to renderer format (left/right) for D3.js
            enhanced_spec = {}
            
            if 'topic1' in spec and 'topic2' in spec:
                # Agent format - convert to renderer format
                enhanced_spec['left'] = spec['topic1']
                enhanced_spec['right'] = spec['topic2']
                
                # Convert attributes to simple arrays for renderer
                enhanced_spec['similarities'] = []
                if 'shared_attributes' in spec:
                    for attr in spec['shared_attributes']:
                        if isinstance(attr, dict) and 'text' in attr:
                            enhanced_spec['similarities'].append(attr['text'])
                        elif isinstance(attr, str):
                            enhanced_spec['similarities'].append(attr)
                
                enhanced_spec['left_differences'] = []
                if 'topic1_attributes' in spec:
                    for attr in spec['topic1_attributes']:
                        if isinstance(attr, dict) and 'text' in attr:
                            enhanced_spec['left_differences'].append(attr['text'])
                        elif isinstance(attr, str):
                            enhanced_spec['left_differences'].append(attr)
                
                enhanced_spec['right_differences'] = []
                if 'topic2_attributes' in spec:
                    for attr in spec['topic2_attributes']:
                        if isinstance(attr, dict) and 'text' in attr:
                            enhanced_spec['right_differences'].append(attr['text'])
                        elif isinstance(attr, str):
                            enhanced_spec['right_differences'].append(attr)
                            
                # Preserve original agent data for debugging
                enhanced_spec['_agent_data'] = spec.copy()
                
            else:
                # Already in renderer format or unknown format
                enhanced_spec = spec.copy()
            
            # Add layout information
            enhanced_spec['_layout'] = {
                'type': 'double_bubble_map',
                'topic1_position': 'left',
                'topic2_position': 'right',
                'shared_position': 'center',
                'attribute_spacing': 100,
                'bubble_radius': 50
            }
            
            # Add recommended dimensions
            enhanced_spec['_recommended_dimensions'] = {
                'baseWidth': 1000,
                'baseHeight': 700,
                'padding': 100,
                'width': 1000,
                'height': 700
            }
            
            # Add metadata
            enhanced_spec['_metadata'] = {
                'generated_by': 'DoubleBubbleMapAgent',
                'version': '1.0',
                'enhanced': True,
                'format_converted': 'topic1' in spec and 'topic2' in spec
            }
            
            return enhanced_spec
            
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
