"""
Bubble Map Agent

Specialized agent for generating bubble maps that describe attributes of a single topic.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import extract_json_from_response

logger = logging.getLogger(__name__)

class BubbleMapAgent(BaseAgent):
    """Agent for generating bubble maps."""
    
    def __init__(self, model='qwen'):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "bubble_map"
        
    async def generate_graph(
        self, 
        prompt: str, 
        language: str = "en",
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a bubble map from a prompt.
        
        Args:
            prompt: User's description of what they want
            language: Language for generation ("en" or "zh")
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.debug(f"BubbleMapAgent: Starting bubble map generation for prompt")
            
            # Generate the bubble map specification
            spec = await self._generate_bubble_map_spec(
                prompt, 
                language,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate bubble map specification'
                }
            
            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning(f"BubbleMapAgent: Validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            # Enhance the spec with layout and dimensions
            enhanced_spec = self._enhance_spec(spec)
            
            logger.info(f"BubbleMapAgent: Bubble map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"BubbleMapAgent: Bubble map generation failed: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    async def _generate_bubble_map_spec(
        self, 
        prompt: str, 
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate the bubble map specification using LLM."""
        try:
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("bubble_map_agent", language, "generation")
            
            if not system_prompt:
                logger.error(f"BubbleMapAgent: No prompt found for language {language}")
                return None
                
            user_prompt = f"请为以下描述创建一个气泡图：{prompt}" if language == "zh" else f"Please create a bubble map for the following description: {prompt}"
            
            # Call middleware directly - clean and efficient!
            from services.llm_service import llm_service
            from config.settings import config
            
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='bubble_map'
            )
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Try to extract JSON from string response
                response_str = str(response)
                spec = extract_json_from_response(response_str)
                
                if not spec:
                    # Log the actual response for debugging
                    response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                    logger.error(f"BubbleMapAgent: Failed to extract JSON from LLM response. Response preview: {response_preview}")
                    return None
                
            return spec
            
        except Exception as e:
            logger.error(f"BubbleMapAgent: Error in spec generation: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            # Add layout information
            spec['_layout'] = {
                'type': 'bubble_map',
                'topic_position': 'center',
                'attribute_spacing': 120,
                'bubble_radius': 60
            }
            
            # Add recommended dimensions
            spec['_recommended_dimensions'] = {
                'baseWidth': 800,
                'baseHeight': 600,
                'padding': 80,
                'width': 800,
                'height': 600
            }
            
            # Add metadata
            spec['_metadata'] = {
                'generated_by': 'BubbleMapAgent',
                'version': '1.0',
                'enhanced': True
            }
            
            return spec
            
        except Exception as e:
            logger.error(f"BubbleMapAgent: Error enhancing spec: {e}")
            return spec
    
    def validate_output(self, spec: Dict) -> Tuple[bool, str]:
        """
        Validate the generated bubble map specification.
        
        Args:
            spec: The specification to validate
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            # Check required fields
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"
            
            if 'topic' not in spec or not spec['topic']:
                return False, "Missing or empty topic"
            
            if 'attributes' not in spec or not isinstance(spec['attributes'], list):
                return False, "Missing or invalid attributes list"
            
            # Connections are optional for simple bubble maps
            if 'connections' in spec and not isinstance(spec['connections'], list):
                return False, "Invalid connections list"
            
            # Validate attributes (simple string format)
            if len(spec['attributes']) < 3:
                return False, "Must have at least 3 attributes"
            
            if len(spec['attributes']) > 15:
                return False, "Too many attributes (max 15)"
            
            # Validate each attribute is a non-empty string
            for i, attr in enumerate(spec['attributes']):
                if not isinstance(attr, str) or not attr.strip():
                    return False, f"attributes[{i}] must be a non-empty string"
            
            # Validate connections if present
            if 'connections' in spec:
                if len(spec['connections']) < len(spec['attributes']):
                    return False, "Each attribute must have at least one connection"
            
            return True, "Specification is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing bubble map specification.
        
        Args:
            spec: Existing specification to enhance
            
        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.debug(f"BubbleMapAgent: Enhancing spec - Topic: {spec.get('topic')}, Attributes: {len(spec.get('attributes', []))}")
            
            # If already enhanced, return as-is
            if spec.get('_metadata', {}).get('enhanced'):
                logger.debug("BubbleMapAgent: Spec already enhanced, skipping")
                return {'success': True, 'spec': spec}
            
            # Enhance the spec
            enhanced_spec = self._enhance_spec(spec)
            
            return {
                'success': True,
                'spec': enhanced_spec
            }
            
        except Exception as e:
            logger.error(f"BubbleMapAgent: Error enhancing spec: {e}")
            return {
                'success': False,
                'error': f'Enhancement failed: {str(e)}'
            }
