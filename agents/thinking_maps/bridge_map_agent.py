"""
Bridge Map Agent

Specialized agent for generating bridge maps that show analogies and similarities.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..core.base_agent import BaseAgent
from ..core.agent_utils import get_llm_client, extract_json_from_response

# Use the centralized agent logger
logger = logging.getLogger('mindgraph.agents')

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
            
            # Basic validation
            logger.info("=== BASIC VALIDATION ===")
            is_valid, validation_msg = self._basic_validation(spec)
            if not is_valid:
                logger.warning(f"BridgeMapAgent: Basic validation failed: {validation_msg}")
                return {
                    'success': False,
                    'error': f'Generated invalid specification: {validation_msg}'
                }
            
            logger.info("Basic validation passed, proceeding to enhancement...")
            
            # Enhance the spec with layout and dimensions
            logger.info("=== ENHANCEMENT PHASE ===")
            enhanced_spec = self._enhance_spec(spec)
            
            logger.info(f"✅ BridgeMapAgent: Successfully generated bridge map")
            logger.info(f"Final result keys: {list(enhanced_spec.keys())}")
            logger.info(f"Final analogies count: {len(enhanced_spec.get('analogies', []))}")
            
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
    
    def _basic_validation(self, spec: Dict) -> Tuple[bool, str]:
        """
        Basic validation: check if required fields exist and have basic structure.
        """
        try:
            # Check if spec is a dictionary
            if not isinstance(spec, dict):
                return False, "Specification must be a dictionary"
            
            # Check for new standardized format first
            if 'analogies' in spec and 'relating_factor' in spec:
                # New format: relating_factor + analogies
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
                
                return True, "Basic validation passed (new format)"
            
            # Check for legacy format
            elif 'left_side' in spec and 'right_side' in spec:
                # Legacy format: left_side + right_side
                if not spec.get('left_side', {}).get('elements'):
                    return False, "Left side has no elements"
                if not spec.get('right_side', {}).get('elements'):
                    return False, "Right side has no elements"
                
                left_elements = spec['left_side']['elements']
                right_elements = spec['right_side']['elements']
                
                if len(left_elements) < 5:
                    return False, f"Left side has insufficient elements: {len(left_elements)}"
                if len(right_elements) < 5:
                    return False, f"Right side has insufficient elements: {len(right_elements)}"
                
                return True, "Basic validation passed (legacy format)"
            
            else:
                return False, "Specification must use either new format (relating_factor + analogies) or legacy format (left_side + right_side)"
            
        except Exception as e:
            return False, f"Basic validation error: {str(e)}"
    
    def _generate_bridge_map_spec(self, prompt: str, language: str) -> Optional[Dict]:
        """Generate the bridge map specification using LLM."""
        try:
            logger.info(f"=== BRIDGE MAP SPEC GENERATION START ===")
            logger.info(f"Prompt: {prompt}")
            logger.info(f"Language: {language}")
            
            # Import centralized prompt system
            from prompts import get_prompt
            
            # Get prompt from centralized system - use agent-specific format that matches validation
            system_prompt = get_prompt("bridge_map_agent", language, "generation")
            
            if not system_prompt:
                # Fallback to general format if agent-specific not found
                system_prompt = get_prompt("bridge_map", language, "generation")
            
            if not system_prompt:
                logger.error(f"BridgeMapAgent: No prompt found for language {language}")
                return None
            
            logger.info(f"System prompt length: {len(system_prompt)}")
            logger.info(f"System prompt preview: {system_prompt[:200]}...")
                
            user_prompt = f"请为以下描述创建一个桥形图：{prompt}" if language == "zh" else f"Please create a bridge map for the following description: {prompt}"
            logger.info(f"User prompt: {user_prompt}")
            
            # Generate response from LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            logger.info("Calling LLM for bridge map generation...")
            response = self.llm_client.chat_completion(messages)
            
            logger.info(f"LLM response received: {response[:500] if response else 'None'}...")
            
            # Extract JSON from response
            from ..core.agent_utils import extract_json_from_response
            
            logger.info("=== JSON EXTRACTION START ===")
            logger.info(f"Response type: {type(response)}")
            
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
                logger.info("Response is already a dictionary")
                logger.info(f"Dictionary keys: {list(spec.keys())}")
            else:
                # Try to extract JSON from string response
                logger.info("Response is string, extracting JSON...")
                spec = extract_json_from_response(str(response))
                logger.info(f"JSON extraction result type: {type(spec)}")
            
            if not spec:
                logger.error("BridgeMapAgent: Failed to extract JSON from LLM response")
                return None
            
            logger.info(f"Extracted spec keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
            logger.info("=== JSON EXTRACTION COMPLETE ===")
                
            return spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error in spec generation: {e}")
            return None
    
    def _enhance_spec(self, spec: Dict) -> Dict:
        """Enhance the specification with layout and dimension recommendations and convert to renderer format."""
        try:
            logger.info("=== ENHANCE SPEC START ===")
            logger.info(f"Input spec keys: {list(spec.keys())}")
            logger.info(f"Input spec type: {type(spec)}")
            
            # Convert agent format (analogy_bridge/left_side/right_side) to renderer format (relating_factor/analogies) for D3.js
            enhanced_spec = {}
            
            if 'analogy_bridge' in spec and 'left_side' in spec and 'right_side' in spec:
                logger.info("Processing agent format (analogy_bridge/left_side/right_side)")
                logger.info(f"Left side keys: {list(spec.get('left_side', {}).keys())}")
                logger.info(f"Right side keys: {list(spec.get('right_side', {}).keys())}")
                
                # Log the actual elements
                left_elements = spec.get('left_side', {}).get('elements', [])
                right_elements = spec.get('right_side', {}).get('elements', [])
                logger.info(f"Left elements count: {len(left_elements)}")
                logger.info(f"Right elements count: {len(right_elements)}")
                
                for i, elem in enumerate(left_elements):
                    logger.info(f"Left element {i}: {elem}")
                
                # === SIMPLE DEDUPLICATION ===
                # Use first 5 unique elements from each side (we have 6 elements, so 1 backup)
                logger.info("Applying simple deduplication to get 5 unique elements per side...")
                
                # Deduplicate left side
                left_elements = self._simple_deduplicate(left_elements, "left", max_elements=5)
                logger.info(f"Left side deduplication complete: {len(left_elements)} elements")
                
                # Deduplicate right side  
                right_elements = self._simple_deduplicate(right_elements, "right", max_elements=5)
                logger.info(f"Right side deduplication complete: {len(right_elements)} elements")
                
                # Log final elements
                left_texts = [elem.get('text', str(elem)) if isinstance(elem, dict) else str(elem) for elem in left_elements]
                right_texts = [elem.get('text', str(elem)) if isinstance(elem, dict) else str(elem) for elem in right_elements]
                logger.info(f"Final left elements: {left_texts}")
                logger.info(f"Final right elements: {right_texts}")
                
                # Convert agent format to renderer format
                enhanced_spec['relating_factor'] = 'as'  # Standard bridge map relating factor
                enhanced_spec['analogies'] = []
                
                # Check if spec already uses the new standardized format
                if 'analogies' in spec:
                    # Already in correct format, just copy and ensure 5 elements
                    enhanced_spec['analogies'] = spec['analogies'][:5]  # Take first 5
                    logger.info(f"Spec already in standardized format, using {len(enhanced_spec['analogies'])} analogies")
                else:
                    # Legacy format - convert from left_side/right_side structure
                    logger.info("Converting from legacy agent format to standardized format")
                    
                    # Create analogies from left and right side elements
                    left_elements = spec.get('left_side', {}).get('elements', [])
                    right_elements = spec.get('right_side', {}).get('elements', [])
                    
                    # Pair up elements (take first 5 from each side)
                    for i in range(min(5, len(left_elements), len(right_elements))):
                        left_text = left_elements[i].get('text', str(left_elements[i])) if isinstance(left_elements[i], dict) else str(left_elements[i])
                        right_text = right_elements[i].get('text', str(right_elements[i])) if isinstance(right_elements[i], dict) else str(right_elements[i])
                        
                        analogy = {
                            'left': left_text,
                            'right': right_text,
                            'id': i
                        }
                        enhanced_spec['analogies'].append(analogy)
                
                # Ensure we have exactly 5 analogies
                if len(enhanced_spec['analogies']) > 5:
                    logger.warning(f"Too many analogies ({len(enhanced_spec['analogies'])}), truncating to 5")
                    enhanced_spec['analogies'] = enhanced_spec['analogies'][:5]
                elif len(enhanced_spec['analogies']) < 5:
                    logger.warning(f"Too few analogies ({len(enhanced_spec['analogies'])}), expected 5")
                
                # Ensure at least one analogy
                if not enhanced_spec['analogies']:
                    enhanced_spec['analogies'] = [
                        {
                            'left': 'Default Left',
                            'right': 'Default Right',
                            'id': 0
                        }
                    ]
                
                # Preserve original agent data for debugging
                enhanced_spec['_agent_data'] = spec.copy()
                
            else:
                # Already in renderer format or unknown format
                enhanced_spec = spec.copy()
            
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
                'enhanced': True,
                'format_converted': 'analogy_bridge' in spec and 'left_side' in spec and 'right_side' in spec
            }
            
            logger.info("=== ENHANCE SPEC COMPLETE ===")
            logger.info(f"Final enhanced spec keys: {list(enhanced_spec.keys())}")
            logger.info(f"Final analogies count: {len(enhanced_spec.get('analogies', []))}")
            
            # Log each final analogy
            analogies = enhanced_spec.get('analogies', [])
            for i, analogy in enumerate(analogies):
                logger.info(f"Final analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            
            return enhanced_spec
            
        except Exception as e:
            logger.error(f"BridgeMapAgent: Error enhancing spec: {e}")
            return spec
    

        """
        Validate the generated bridge map specification.
        
        Args:
            spec: The specification to validate
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        try:
            logger.info("=== VALIDATION START ===")
            logger.info(f"Validating spec with keys: {list(spec.keys())}")
            
            # Check required fields
            if not isinstance(spec, dict):
                logger.error("Specification is not a dictionary")
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
            
            # Validate elements (expect exactly 5 for rich bridge maps)
            if len(spec['left_side']['elements']) < 3:
                return False, "Left side must have at least 3 elements for meaningful analogies"
            
            if len(spec['right_side']['elements']) < 3:
                return False, "Right side must have at least 3 elements for meaningful analogies"
            
            # Check total element count
            total_elements = (len(spec['left_side']['elements']) + 
                             len(spec['right_side']['elements']))
            if total_elements > 12:
                return False, "Too many total elements (max 10 recommended for clarity)"
            
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
                    logger.error(f"Invalid bridge connection: {conn}")
                    return False, "Invalid bridge connection references"
                if 'label' not in conn or not conn['label']:
                    logger.error(f"Missing label in connection: {conn}")
                    return False, "Missing or empty bridge connection label"
                if 'bridge_text' not in conn or not conn['bridge_text']:
                    logger.error(f"Missing bridge_text in connection: {conn}")
                    return False, "Missing or empty bridge text"
            
            logger.info("=== VALIDATION PASSED ===")
            logger.info(f"Valid spec with {len(spec['left_side']['elements'])} left and {len(spec['right_side']['elements'])} right elements")
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
    
    def _simple_deduplicate(self, elements: List[Dict], side_name: str, max_elements: int = 5) -> List[Dict]:
        """
        Simple deduplication: use first N unique elements, log when backups are used.
        
        Args:
            elements: List of element dictionaries
            side_name: Name of the side for logging (left/right)
            max_elements: Maximum number of elements to return
            
        Returns:
            List of first N unique elements
        """
        try:
            logger.info(f"Starting simple deduplication for {side_name} side...")
            
            seen = set()
            unique_elements = []
            duplicates_found = []
            
            for i, elem in enumerate(elements):
                text = elem.get('text', str(elem)) if isinstance(elem, dict) else str(elem)
                
                if text in seen:
                    duplicates_found.append((i, text))
                    logger.info(f"Duplicate found on {side_name} side: '{text}' at position {i}")
                elif len(unique_elements) < max_elements:
                    seen.add(text)
                    unique_elements.append(elem)
            
            if duplicates_found:
                logger.info(f"Used backup elements for {side_name} side. Duplicates: {duplicates_found}")
                logger.info(f"Final {side_name} elements: {[elem.get('text', str(elem)) for elem in unique_elements]}")
            
            return unique_elements
                
        except Exception as e:
            logger.error(f"Error in simple deduplication for {side_name} side: {e}")
            # Return first N elements as fallback
            return elements[:max_elements]
    

