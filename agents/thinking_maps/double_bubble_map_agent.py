"""
Double Bubble Map Agent

Specialized agent for generating double bubble maps that compare and contrast two topics.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import extract_json_from_response

logger = logging.getLogger(__name__)

class DoubleBubbleMapAgent(BaseAgent):
    """Agent for generating double bubble maps."""
    
    def __init__(self, model='qwen'):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "double_bubble_map"
        
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
        Generate a double bubble map from a prompt.
        
        Args:
            prompt: User's description of what they want to compare
            language: Language for generation ("en" or "zh")
            user_id: User ID for token tracking
            organization_id: Organization ID for token tracking
            request_type: Request type for token tracking
            endpoint_path: Endpoint path for token tracking
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.debug(f"DoubleBubbleMapAgent: Starting double bubble map generation for prompt")
            
            # Generate the double bubble map specification
            spec = await self._generate_double_bubble_map_spec(
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
    
    async def _generate_double_bubble_map_spec(
        self, 
        prompt: str, 
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate the double bubble map specification using LLM."""
        try:
            # Import centralized prompt system
            from prompts import get_prompt
            from ..main_agent import extract_double_bubble_topics_llm
            
            # Extract two topics for comparison using specialized LLM extraction (async)
            topics = await extract_double_bubble_topics_llm(prompt, language, self.model)
            logger.debug(f"DoubleBubbleMapAgent: Extracted topics: {topics}")
            
            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("double_bubble_map_agent", language, "generation")
            
            if not system_prompt:
                logger.error(f"DoubleBubbleMapAgent: No prompt found for language {language}")
                return None
                
            # Use the extracted topics instead of raw prompt
            user_prompt = f"请为以下描述创建一个双气泡图：{topics}" if language == "zh" else f"Please create a double bubble map for the following description: {topics}"
            
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
                diagram_type='double_bubble_map'
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
                    # Log the actual response for debugging with more context
                    response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                    logger.error(f"DoubleBubbleMapAgent: Failed to extract JSON from LLM response")
                    logger.error(f"DoubleBubbleMapAgent: Response length: {len(response_str)}, Preview: {response_preview}")
                    logger.error(f"DoubleBubbleMapAgent: This may indicate LLM returned invalid JSON or non-JSON response")
                    # Return None to trigger error handling upstream
                    return None
                
            return spec
            
        except Exception as e:
            logger.error(f"DoubleBubbleMapAgent: Error in spec generation: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            logger.debug(f"DoubleBubbleMapAgent: Enhancing spec - Left: {spec.get('left')}, Right: {spec.get('right')}")
            logger.debug(f"DoubleBubbleMapAgent: Left attributes: {len(spec.get('left_only', []))}, Right attributes: {len(spec.get('right_only', []))}, Shared: {len(spec.get('shared', []))}")
            
            # Agent already generates correct renderer format, just enhance it
            enhanced_spec = spec.copy()
            
            # Add layout information
            enhanced_spec['_layout'] = {
                'type': 'double_bubble_map',
                'left_position': 'left',
                'right_position': 'right',
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
                'enhanced': True
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
            
            if 'left' not in spec or not spec['left']:
                return False, "Missing or empty left topic"
            
            if 'right' not in spec or not spec['right']:
                return False, "Missing or empty right topic"
            
            if 'left_differences' not in spec or not isinstance(spec['left_differences'], list):
                return False, "Missing or invalid left_differences list"
            
            if 'right_differences' not in spec or not isinstance(spec['right_differences'], list):
                return False, "Missing or invalid right_differences list"
            
            if 'similarities' not in spec or not isinstance(spec['similarities'], list):
                return False, "Missing or invalid similarities list"
            
            # Validate attributes
            if len(spec['left_differences']) < 2:
                return False, "Left topic must have at least 2 attributes"
            
            if len(spec['right_differences']) < 2:
                return False, "Right topic must have at least 2 attributes"
            
            if len(spec['similarities']) < 1:
                return False, "Must have at least 1 shared attribute"
            
            # Check total attribute count
            total_attrs = (len(spec['left_differences']) + 
                          len(spec['right_differences']) + 
                          len(spec['similarities']))
            if total_attrs > 20:
                return False, "Too many total attributes (max 20)"
            
            return True, "Specification is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    async def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing double bubble map specification.
        
        Args:
            spec: Existing specification to enhance
            
        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.debug("DoubleBubbleMapAgent: Enhancing existing specification")
            
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
