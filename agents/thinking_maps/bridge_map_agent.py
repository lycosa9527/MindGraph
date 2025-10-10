"""
Bridge Map Agent

Specialized agent for generating bridge maps that show analogies and similarities.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import extract_json_from_response

# Use standard logging like other modules
logger = logging.getLogger(__name__)

class BridgeMapAgent(BaseAgent):
    """Agent for generating bridge maps."""
    
    def __init__(self, model='qwen'):
        super().__init__(model=model)
        # llm_client is now a dynamic property from BaseAgent
        self.diagram_type = "bridge_map"
        
    async def generate_graph(self, prompt: str, language: str = "en", dimension_preference: str = None) -> Dict[str, Any]:
        """
        Generate a bridge map from a prompt.
        
        Args:
            prompt: User's description of what analogy they want to show
            language: Language for generation ("en" or "zh")
            dimension_preference: Optional analogy relationship pattern preference
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.info(f"BridgeMapAgent: Starting bridge map generation for prompt")
            
            # Generate the bridge map specification
            spec = await self._generate_bridge_map_spec(prompt, language, dimension_preference)
            
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate bridge map specification'
                }
            
            # Basic validation
            logger.debug("Basic validation started")
            is_valid, validation_msg = self._basic_validation(spec)
            if not is_valid:
                logger.warning(f"BridgeMapAgent: Basic validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            logger.debug("Basic validation passed, proceeding to enhancement...")
            
            # Enhance the spec with layout and dimensions
            logger.debug("Enhancement phase started")
            enhanced_spec = self._enhance_spec(spec)
            
            logger.info(f"BridgeMapAgent: Bridge map generation completed successfully")
            logger.debug(f"Final result keys: {list(enhanced_spec.keys())}")
            logger.debug(f"Final analogies count: {len(enhanced_spec.get('analogies', []))}")
            
            return {
                'success': True,
                'spec': enhanced_spec,
                'diagram_type': self.diagram_type
            }
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Bridge map generation failed: {e}")
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}'
            }
    
    def _basic_validation(self, spec: Dict) -> Tuple[bool, str]:
        """
        Basic validation: check if required fields exist and have basic structure.
        """
        try:
            # Check if spec is a dictionary
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"
            
            # Check for required fields (renderer format)
            if 'analogies' not in spec or 'relating_factor' not in spec:
                return False, "Missing required fields. Expected (relating_factor, analogies)"
            
            # Validate optional dimension and alternative_dimensions fields
            if 'dimension' in spec and not isinstance(spec['dimension'], str):
                return False, "dimension field must be a string"
            if 'alternative_dimensions' in spec:
                if not isinstance(spec['alternative_dimensions'], list):
                    return False, "alternative_dimensions must be a list"
                if not all(isinstance(d, str) for d in spec['alternative_dimensions']):
                    return False, "All alternative dimensions must be strings"
            
            analogies = spec.get('analogies', [])
            if not analogies:
                return False, "Analogies array is empty"
            
            # Check if we have at least 5 analogies
            if len(analogies) < 5:
                return False, f"Insufficient analogies: {len(analogies)}, need at least 5"
            
            # Validate each analogy has required fields
            for i, analogy in enumerate(analogies):
                if not isinstance(analogy, dict):
                    return False, f"Analogy {i} is not a dictionary"
                if 'left' not in analogy or 'right' not in analogy:
                    return False, f"Analogy {i} missing left or right field"
            
            return True, "Basic validation passed"
            
        except Exception as e:
            return False, f"Basic validation error: {str(e)}"
    
    async def _generate_bridge_map_spec(self, prompt: str, language: str, dimension_preference: str = None) -> Optional[Dict]:
        """Generate the bridge map specification using LLM."""
        try:
            logger.debug(f"=== BRIDGE MAP SPEC GENERATION START ===")
            logger.debug(f"Prompt: {prompt}")
            logger.debug(f"Language: {language}")
            
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get prompt from centralized system - use agent-specific format
            system_prompt = get_prompt("bridge_map_agent", language, "generation")
            
            if not system_prompt:
                logger.error(f"BridgeMapAgent: No prompt found for language {language}")
                return None
            
            logger.debug(f"System prompt length: {len(system_prompt)}")
            logger.debug(f"System prompt preview: {system_prompt[:200]}...")
            
            # Build user prompt with dimension preference if specified
            if dimension_preference:
                if language == "zh":
                    user_prompt = f"请为以下描述创建一个桥形图，使用指定的类比关系模式'{dimension_preference}'：{prompt}"
                else:
                    user_prompt = f"Please create a bridge map for the following description using the specified analogy relationship pattern '{dimension_preference}': {prompt}"
                logger.info(f"BridgeMapAgent: User specified relationship pattern preference: {dimension_preference}")
            else:
                user_prompt = f"请为以下描述创建一个桥形图：{prompt}" if language == "zh" else f"Please create a bridge map for the following description: {prompt}"
            logger.debug(f"User prompt: {user_prompt}")
            
            # Call middleware directly - clean and efficient!
            from services.llm_service import llm_service
            from config.settings import config
            
            logger.debug("Calling LLM for bridge map generation...")
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE
            )
            
            logger.debug(f"LLM response received: {response[:500] if response else 'None'}...")
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            logger.debug("=== JSON EXTRACTION START ===")
            logger.debug(f"Response type: {type(response)}")
            
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
                logger.debug("Response is already a dictionary")
                logger.debug(f"Dictionary keys: {list(spec.keys())}")
            else:
                # Try to extract JSON from string response
                logger.debug("Response is string, extracting JSON...")
                spec = extract_json_from_response(str(response))
                logger.debug(f"JSON extraction result type: {type(spec)}")
            
            if not spec:
                logger.error("BridgeMapAgent: Failed to extract JSON from LLM response")
                return None
            
            logger.debug(f"Extracted spec keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
            logger.info(f"BridgeMapAgent: Dimension field from LLM: {spec.get('dimension', 'NOT PROVIDED')}")
            logger.info(f"BridgeMapAgent: Alternative dimensions from LLM: {spec.get('alternative_dimensions', 'NOT PROVIDED')}")
            logger.debug("=== JSON EXTRACTION COMPLETE ===")
                
            return spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error in spec generation: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            logger.info(f"BridgeMapAgent: Enhancing spec - Analogies: {len(spec.get('analogies', []))}")
            
            # Agent already generates correct renderer format, just enhance it
            enhanced_spec = spec.copy()
            
            # Ensure dimension and alternative_dimensions fields are preserved
            if 'dimension' in spec:
                enhanced_spec['dimension'] = spec['dimension']
                logger.info(f"BridgeMapAgent: Preserving dimension: {spec['dimension']}")
            else:
                logger.warning("BridgeMapAgent: No dimension field in spec - LLM did not provide it")
            
            if 'alternative_dimensions' in spec:
                enhanced_spec['alternative_dimensions'] = spec['alternative_dimensions']
                logger.info(f"BridgeMapAgent: Preserving {len(spec['alternative_dimensions'])} alternative dimensions")
            else:
                logger.warning("BridgeMapAgent: No alternative_dimensions field in spec - LLM did not provide it")
            
            # Ensure we have exactly 5 analogies (renderer expects this)
            if 'analogies' in enhanced_spec and len(enhanced_spec['analogies']) > 5:
                logger.info(f"BridgeMapAgent: Truncating {len(enhanced_spec['analogies'])} analogies to 5 for renderer")
                enhanced_spec['analogies'] = enhanced_spec['analogies'][:5]
            
            # Add layout information
            enhanced_spec['_layout'] = {
                'type': 'bridge_map',
                'bridge_position': 'center',
                'left_position': 'left',
                'right_position': 'right',
                'element_spacing': 100,
                'bridge_width': 120
            }
            
            # Add recommended dimensions
            enhanced_spec['_recommended_dimensions'] = {
                'baseWidth': 1000,
                'baseHeight': 600,
                'padding': 80,
                'width': 1000,
                'height': 600
            }
            
            # Add metadata
            enhanced_spec['_metadata'] = {
                'generated_by': 'BridgeMapAgent',
                'version': '1.0',
                'enhanced': True
            }
            
            logger.debug("=== ENHANCE SPEC COMPLETE ===")
            logger.debug(f"Final enhanced spec keys: {list(enhanced_spec.keys())}")
            logger.debug(f"Final analogies count: {len(enhanced_spec.get('analogies', []))}")
            
            # Log each final analogy
            analogies = enhanced_spec.get('analogies', [])
            for i, analogy in enumerate(analogies):
                logger.debug(f"Final analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            
            return enhanced_spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error enhancing spec: {e}")
            return spec
    
    async def enhance_spec(self, spec: Dict) -> Dict[str, Any]:
        """
        Enhance an existing bridge map specification.
        
        Args:
            spec: Existing specification to enhance
            
        Returns:
            Dict containing success status and enhanced spec
        """
        try:
            logger.info("BridgeMapAgent: Starting spec enhancement")
            
            # If already enhanced, return as-is
            if spec.get('_metadata', {}).get('enhanced'):
                logger.info("BridgeMapAgent: Spec already enhanced, skipping")
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

    

