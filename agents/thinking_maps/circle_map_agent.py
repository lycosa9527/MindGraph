"""
Circle Map Agent

Specialized agent for generating circle maps that define topics in context.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import extract_json_from_response

logger = logging.getLogger(__name__)

class CircleMapAgent(BaseAgent):
    """Agent for generating circle maps."""
    
    def __init__(self, model='qwen'):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "circle_map"
        
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
        Generate a circle map from a prompt.
        
        Args:
            prompt: User's description of what they want to define
            language: Language for generation ("en" or "zh")
            user_id: User ID for token tracking
            organization_id: Organization ID for token tracking
            request_type: Request type for token tracking
            endpoint_path: Endpoint path for token tracking
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.debug(f"CircleMapAgent: Starting circle map generation for prompt")
            
            # Generate the circle map specification
            spec = await self._generate_circle_map_spec(
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
            
            logger.info(f"CircleMapAgent: Circle map generation completed successfully")
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"CircleMapAgent: Circle map generation failed: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    async def _generate_circle_map_spec(
        self, 
        prompt: str, 
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
        """Generate the circle map specification using LLM."""
        try:
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("circle_map_agent", language, "generation")
            
            if not system_prompt:
                logger.error(f"CircleMapAgent: No prompt found for language {language}")
                return None
                
            user_prompt = f"请为以下描述创建一个圆圈图：{prompt}" if language == "zh" else f"Please create a circle map for the following description: {prompt}"
            
            # Call middleware directly - clean and efficient!
            from services.llm_service import llm_service
            from config.settings import config
            
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,  # From .env (default 0.3 for structured output)
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='circle_map'
            )
            
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
                logger.error(f"CircleMapAgent: Raw response from {self.model}: {str(response)[:500]}")
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
            
            if 'topic' not in spec or not spec['topic']:
                return False, "Missing or empty topic"
            
            if 'context' not in spec or not isinstance(spec['context'], list):
                return False, "Missing or invalid context list"
            
            # Validate context elements (should be strings for renderer compatibility)
            if len(spec['context']) < 4:
                return False, "Must have at least 4 context elements"
            
            for i, ctx in enumerate(spec['context']):
                if not isinstance(ctx, str) or not ctx.strip():
                    return False, f"context[{i}] must be a non-empty string"
            
            return True, "Specification is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    async def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing circle map specification.
        
        Args:
            spec: Existing specification to enhance
            
        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.debug(f"CircleMapAgent: Enhancing spec - Topic: {spec.get('topic')}, Context elements: {len(spec.get('context', []))}")
            
            # If already enhanced, return as-is
            if spec.get('_metadata', {}).get('enhanced'):
                logger.debug("CircleMapAgent: Spec already enhanced, skipping")
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
