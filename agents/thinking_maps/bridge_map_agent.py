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
        
    async def generate_graph(
        self, 
        prompt: str, 
        language: str = "en", 
        dimension_preference: str = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None,
        # Bridge map auto-complete: existing pairs to preserve
        existing_analogies: Optional[List[Dict[str, str]]] = None,
        # Bridge map auto-complete: fixed dimension/relationship that user has already specified
        fixed_dimension: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a bridge map from a prompt.
        
        Args:
            prompt: User's description of what analogy they want to show
            language: Language for generation ("en" or "zh")
            dimension_preference: Optional analogy relationship pattern preference
            user_id: User ID for token tracking
            organization_id: Organization ID for token tracking
            request_type: Request type for token tracking
            endpoint_path: Endpoint path for token tracking
            existing_analogies: For auto-complete mode - existing pairs to preserve [{left, right}, ...]
                               When provided, LLM only identifies the relationship pattern, doesn't generate new pairs
            fixed_dimension: For auto-complete mode - user-specified relationship pattern that should NOT be changed by LLM
            
        Returns:
            Dict containing success status and generated spec
        """
        try:
            logger.debug(f"BridgeMapAgent: Starting bridge map generation for prompt")
            
            # Three-template system for bridge maps:
            # 1. existing_analogies provided → identify relationship pattern
            # 2. NO existing_analogies but fixed_dimension provided → relationship-only mode
            # 3. Neither → full generation mode
            
            if existing_analogies and len(existing_analogies) > 0:
                # Case 1 & 2: Has existing pairs
                if fixed_dimension:
                    logger.debug(f"BridgeMapAgent: Mode 2 - Pairs + Relationship provided, FIXED dimension '{fixed_dimension}' - preserving {len(existing_analogies)} pairs")
                else:
                    logger.debug(f"BridgeMapAgent: Mode 1 - Only pairs provided, will identify relationship pattern from {len(existing_analogies)} pairs")
                spec = await self._identify_relationship_pattern(
                    existing_analogies,
                    language,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                    fixed_dimension=fixed_dimension
                )
            elif fixed_dimension:
                # Case 3: Relationship-only mode - user provided ONLY the relationship, no pairs
                logger.debug(f"BridgeMapAgent: Mode 3 - Relationship-only mode, generating pairs for '{fixed_dimension}'")
                spec = await self._generate_from_relationship_only(
                    fixed_dimension,
                    language,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path
                )
            else:
                # Case 4: Full generation mode - no pairs, no fixed dimension
                spec = await self._generate_bridge_map_spec(
                    prompt, 
                    language, 
                    dimension_preference,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path
                )
            
            if not spec:
                return {
                    'success': False,
                    'error': 'Failed to generate bridge map specification'
                }
            
            # Basic validation - skip minimum count check in auto-complete mode
            logger.debug("Basic validation started")
            is_autocomplete_mode = existing_analogies and len(existing_analogies) > 0
            is_valid, validation_msg = self._basic_validation(spec, skip_min_count=is_autocomplete_mode)
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
    
    def _basic_validation(self, spec: Dict, skip_min_count: bool = False) -> Tuple[bool, str]:
        """
        Basic validation: check if required fields exist and have basic structure.
        
        Args:
            spec: The specification to validate
            skip_min_count: If True, skip the minimum 5 analogies check (for auto-complete mode)
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
            
            # Check if we have at least 5 analogies (skip in auto-complete mode)
            if not skip_min_count and len(analogies) < 5:
                return False, f"Insufficient analogies: {len(analogies)}, need at least 5"
            
            # In auto-complete mode, just ensure at least 1 analogy exists
            if skip_min_count and len(analogies) < 1:
                return False, "At least 1 analogy required"
            
            # Validate each analogy has required fields
            for i, analogy in enumerate(analogies):
                if not isinstance(analogy, dict):
                    return False, f"Analogy {i} is not a dictionary"
                if 'left' not in analogy or 'right' not in analogy:
                    return False, f"Analogy {i} missing left or right field"
            
            return True, "Basic validation passed"
            
        except Exception as e:
            return False, f"Basic validation error: {str(e)}"
    
    async def _generate_bridge_map_spec(
        self, 
        prompt: str, 
        language: str, 
        dimension_preference: str = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
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
                logger.debug(f"BridgeMapAgent: User specified relationship pattern preference: {dimension_preference}")
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
                temperature=config.LLM_TEMPERATURE,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='bridge_map'
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
                # Log the actual response for debugging
                response_str = str(response) if response else "None"
                response_preview = response_str[:500] + "..." if len(response_str) > 500 else response_str
                logger.error(f"BridgeMapAgent: Failed to extract JSON from LLM response. Response preview: {response_preview}")
                return None
            
            logger.debug(f"Extracted spec keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
            logger.debug(f"BridgeMapAgent: Dimension field from LLM: {spec.get('dimension', 'NOT PROVIDED')}")
            logger.debug(f"BridgeMapAgent: Alternative dimensions from LLM: {spec.get('alternative_dimensions', 'NOT PROVIDED')}")
            logger.debug("=== JSON EXTRACTION COMPLETE ===")
                
            return spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error in spec generation: {e}")
            return None
    
    async def _identify_relationship_pattern(
        self,
        existing_analogies: List[Dict[str, str]],
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None,
        # Fixed dimension: user has already specified this relationship, do NOT change it
        fixed_dimension: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Identify the relationship pattern from existing analogy pairs and generate more pairs.
        Preserves user's pairs and adds new pairs following the same pattern.
        
        Args:
            existing_analogies: List of existing pairs [{left, right}, ...]
            language: Language for generation
            fixed_dimension: User-specified relationship pattern that should be preserved (not changed by LLM)
            
        Returns:
            Spec with user's pairs + new generated pairs + identified/fixed dimension
        """
        try:
            logger.debug(f"BridgeMapAgent: Auto-complete from {len(existing_analogies)} existing pairs")
            
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Format the existing pairs for the prompt
            pairs_text = "\n".join([f"- {pair.get('left', '')} → {pair.get('right', '')}" for pair in existing_analogies])
            
            # Create a set of existing pairs for deduplication
            existing_set = set()
            for pair in existing_analogies:
                existing_set.add((pair.get('left', '').strip().lower(), pair.get('right', '').strip().lower()))
            
            # Choose prompt based on whether user has specified a fixed dimension
            if fixed_dimension:
                # User has already specified the relationship - use fixed dimension prompt
                logger.debug(f"BridgeMapAgent: Using FIXED dimension mode with '{fixed_dimension}'")
                system_prompt = get_prompt("bridge_map_agent", language, "fixed_dimension")
                
                if not system_prompt:
                    logger.warning("BridgeMapAgent: No fixed_dimension prompt found, using fallback")
                    # Fallback prompt for fixed dimension mode
                    if language == "zh":
                        system_prompt = f"""用户已经指定了类比关系模式："{fixed_dimension}"
你必须使用这个指定的关系模式生成新的类比对。不要改变或重新解释这个关系模式。

根据用户现有的类比对，生成5-6个遵循"{fixed_dimension}"关系模式的新类比对。
返回JSON：{{"dimension": "{fixed_dimension}", "analogies": [{{"left": "X", "right": "Y"}}...], "alternative_dimensions": [...]}}

重要：dimension字段必须完全保持为"{fixed_dimension}"，不要改变它！"""
                    else:
                        system_prompt = f"""The user has ALREADY SPECIFIED the analogy relationship pattern: "{fixed_dimension}"
You MUST use this exact relationship pattern to generate new pairs. Do NOT change or reinterpret it.

Based on the user's existing pairs, generate 5-6 NEW pairs that follow the "{fixed_dimension}" relationship pattern.
Return JSON: {{"dimension": "{fixed_dimension}", "analogies": [{{"left": "X", "right": "Y"}}...], "alternative_dimensions": [...]}}

CRITICAL: The dimension field MUST remain exactly "{fixed_dimension}" - do NOT change it!"""
                
                if language == "zh":
                    user_prompt = f"用户指定的关系模式：{fixed_dimension}\n\n用户已创建的类比对：\n{pairs_text}\n\n请使用指定的关系模式「{fixed_dimension}」生成5-6个新的类比对（不要重复上面的对）。"
                else:
                    user_prompt = f"User's specified relationship pattern: {fixed_dimension}\n\nUser's existing pairs:\n{pairs_text}\n\nGenerate 5-6 NEW pairs using the EXACT relationship pattern \"{fixed_dimension}\" (do not duplicate the above)."
            else:
                # No fixed dimension - identify the pattern from existing pairs
                system_prompt = get_prompt("bridge_map_agent", language, "identify_relationship")
                
                if not system_prompt:
                    logger.warning("BridgeMapAgent: No identify_relationship prompt found, using fallback")
                    # Fallback prompt
                    if language == "zh":
                        system_prompt = """分析以下类比对，识别关系模式，并生成更多遵循相同模式的新对。
返回JSON：{"dimension": "模式名", "analogies": [{"left": "X", "right": "Y"}...], "alternative_dimensions": [...]}"""
                    else:
                        system_prompt = """Analyze these pairs, identify the pattern, and generate more pairs following the same pattern.
Return JSON: {"dimension": "pattern", "analogies": [{"left": "X", "right": "Y"}...], "alternative_dimensions": [...]}"""
                
                if language == "zh":
                    user_prompt = f"用户已创建的类比对：\n{pairs_text}\n\n请识别关系模式，并生成5-6个新的类比对（不要重复上面的对）。"
                else:
                    user_prompt = f"User's existing pairs:\n{pairs_text}\n\nIdentify the pattern and generate 5-6 NEW pairs (do not duplicate the above)."
            
            logger.debug(f"User prompt: {user_prompt}")
            
            # Call LLM to identify relationship and generate new pairs
            from services.llm_service import llm_service
            from config.settings import config
            
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=800,  # Increased for generating pairs
                temperature=config.LLM_TEMPERATURE,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='bridge_map'
            )
            
            logger.debug(f"LLM response: {response[:500] if response else 'None'}...")
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            if isinstance(response, dict):
                result = response
            else:
                result = extract_json_from_response(str(response))
            
            if not result:
                logger.warning("BridgeMapAgent: Failed to extract JSON, returning existing pairs only")
                result = {}
            
            # Get new pairs from LLM response
            llm_new_pairs = result.get('analogies', [])
            logger.debug(f"BridgeMapAgent: LLM generated {len(llm_new_pairs)} new pairs")
            
            # Build combined analogies: user's pairs first, then new unique pairs
            combined_analogies = []
            
            # Add user's existing pairs first (with IDs starting from 0)
            for i, pair in enumerate(existing_analogies):
                combined_analogies.append({
                    'left': pair.get('left', ''),
                    'right': pair.get('right', ''),
                    'id': i
                })
            
            # Add new pairs from LLM (filter duplicates)
            next_id = len(existing_analogies)
            for pair in llm_new_pairs:
                left = pair.get('left', '').strip()
                right = pair.get('right', '').strip()
                
                # Fallback: Handle malformed format where both values are in 'left' field
                # Some LLMs (e.g., Hunyuan) may return {"left": "东京 → 日本"} instead of {"left": "东京", "right": "日本"}
                if left and not right and ' → ' in left:
                    parts = left.split(' → ', 1)
                    if len(parts) == 2:
                        left = parts[0].strip()
                        right = parts[1].strip()
                        logger.debug(f"Fixed malformed pair: '{left}' → '{right}'")
                
                # Skip empty pairs
                if not left or not right:
                    continue
                
                # Skip duplicates (case-insensitive)
                pair_key = (left.lower(), right.lower())
                if pair_key in existing_set:
                    logger.debug(f"Skipping duplicate pair: {left} → {right}")
                    continue
                
                existing_set.add(pair_key)
                combined_analogies.append({
                    'left': left,
                    'right': right,
                    'id': next_id
                })
                next_id += 1
            
            logger.debug(f"BridgeMapAgent: Combined total: {len(combined_analogies)} pairs ({len(existing_analogies)} user + {len(combined_analogies) - len(existing_analogies)} new)")
            
            # Build final spec - use fixed_dimension if provided, otherwise use LLM-identified dimension
            final_dimension = fixed_dimension if fixed_dimension else result.get('dimension', '')
            
            spec = {
                'relating_factor': 'as',
                'dimension': final_dimension,
                'analogies': combined_analogies,
                'alternative_dimensions': result.get('alternative_dimensions', [])
            }
            
            if fixed_dimension:
                logger.debug(f"BridgeMapAgent: Using FIXED dimension: {final_dimension}")
            else:
                logger.debug(f"BridgeMapAgent: Identified dimension: {spec.get('dimension', 'NOT IDENTIFIED')}")
            
            return spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error in auto-complete: {e}")
            # Return spec with just the existing pairs, preserving fixed_dimension if provided
            return {
                'relating_factor': 'as',
                'dimension': fixed_dimension if fixed_dimension else '',
                'analogies': [
                    {'left': pair.get('left', ''), 'right': pair.get('right', ''), 'id': i}
                    for i, pair in enumerate(existing_analogies)
                ],
                'alternative_dimensions': []
            }
    
    async def _generate_from_relationship_only(
        self,
        relationship: str,
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = 'diagram_generation',
        endpoint_path: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Generate bridge map pairs from a relationship pattern only (no existing pairs).
        
        This is Mode 3 of the three-template system:
        - Mode 1: Only pairs provided → identify relationship
        - Mode 2: Pairs + relationship provided → keep as-is
        - Mode 3: Only relationship provided → generate pairs (this method)
        
        Args:
            relationship: The relationship pattern specified by user (e.g., "货币到国家", "Author to Book")
            language: Language for generation
            
        Returns:
            Spec with generated pairs following the specified relationship
        """
        try:
            logger.debug(f"BridgeMapAgent: Relationship-only mode - generating pairs for '{relationship}'")
            
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get the relationship-only prompt
            system_prompt = get_prompt("bridge_map_agent", language, "relationship_only")
            
            if not system_prompt:
                logger.warning("BridgeMapAgent: No relationship_only prompt found, using generation prompt as fallback")
                system_prompt = get_prompt("bridge_map_agent", language, "generation")
            
            # Build user prompt with the relationship
            if language == "zh":
                user_prompt = f"用户指定的关系模式：{relationship}\n\n请根据这个关系模式生成6个类比对。"
            else:
                user_prompt = f"User's specified relationship pattern: {relationship}\n\nGenerate 6 analogy pairs following this relationship pattern."
            
            logger.debug(f"User prompt: {user_prompt}")
            
            # Call LLM
            from services.llm_service import llm_service
            from config.settings import config
            
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=800,
                temperature=config.LLM_TEMPERATURE,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type='bridge_map'
            )
            
            logger.debug(f"LLM response: {response[:500] if response else 'None'}...")
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            if isinstance(response, dict):
                result = response
            else:
                result = extract_json_from_response(str(response))
            
            if not result:
                logger.error("BridgeMapAgent: Failed to extract JSON from relationship-only response")
                return None
            
            # Get pairs from LLM response
            analogies = result.get('analogies', [])
            logger.debug(f"BridgeMapAgent: Generated {len(analogies)} pairs for relationship '{relationship}'")
            
            # Add IDs to analogies
            for i, pair in enumerate(analogies):
                pair['id'] = i
            
            # Build final spec - ALWAYS use the user's relationship as dimension
            spec = {
                'relating_factor': 'as',
                'dimension': relationship,  # Keep user's relationship exactly
                'analogies': analogies,
                'alternative_dimensions': result.get('alternative_dimensions', [])
            }
            
            logger.debug(f"BridgeMapAgent: Relationship-only complete - dimension: '{relationship}', pairs: {len(analogies)}")
            
            return spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error in relationship-only mode: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations."""
        try:
            logger.debug(f"BridgeMapAgent: Enhancing spec - Analogies: {len(spec.get('analogies', []))}")
            
            # Agent already generates correct renderer format, just enhance it
            enhanced_spec = spec.copy()
            
            # Ensure dimension and alternative_dimensions fields are preserved
            if 'dimension' in spec:
                enhanced_spec['dimension'] = spec['dimension']
                logger.debug(f"BridgeMapAgent: Preserving dimension: {spec['dimension']}")
            else:
                logger.warning("BridgeMapAgent: No dimension field in spec - LLM did not provide it")
            
            if 'alternative_dimensions' in spec:
                enhanced_spec['alternative_dimensions'] = spec['alternative_dimensions']
                logger.debug(f"BridgeMapAgent: Preserving {len(spec['alternative_dimensions'])} alternative dimensions")
            else:
                logger.warning("BridgeMapAgent: No alternative_dimensions field in spec - LLM did not provide it")
            
            # Ensure we have exactly 5 analogies (renderer expects this)
            if 'analogies' in enhanced_spec and len(enhanced_spec['analogies']) > 5:
                logger.debug(f"BridgeMapAgent: Truncating {len(enhanced_spec['analogies'])} analogies to 5 for renderer")
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
            logger.debug("BridgeMapAgent: Starting spec enhancement")
            
            # If already enhanced, return as-is
            if spec.get('_metadata', {}).get('enhanced'):
                logger.debug("BridgeMapAgent: Spec already enhanced, skipping")
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

    

