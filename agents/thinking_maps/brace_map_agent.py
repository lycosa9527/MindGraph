"""
brace map agent module.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging

from config.settings import config
from prompts import get_prompt
from services.llm import llm_service

from ..core.base_agent import BaseAgent
from ..core.agent_utils import extract_json_from_response

from .brace_map_helpers import (
    CollisionDetector,
    ContextAwareAlgorithmSelector,
    ContextManager,
    LLMHybridProcessor,
)
from .brace_map_models import (
    FONT_WEIGHT_CONFIG,
    BlockUnit,
    LayoutAlgorithm,
    LayoutResult,
    NodePosition,
    SpacingInfo,
    UnitPosition,
)
from .brace_map_positioning import (
    BlockBasedPositioningSystem,
    FlexibleLayoutCalculator,
)


logger = logging.getLogger(__name__)


class BraceMapAgent(BaseAgent):
    """Brace Map Agent with block-based positioning system"""

    def __init__(self, model="qwen"):
        super().__init__(model=model)
        self.context_manager = ContextManager()
        self.llm_processor = LLMHybridProcessor()
        self.algorithm_selector = ContextAwareAlgorithmSelector(self.context_manager)
        self.layout_calculator = FlexibleLayoutCalculator()
        self.block_positioning = BlockBasedPositioningSystem()
        self.diagram_type = "brace_map"

        # Initialize with default theme
        self.default_theme = {
            "fontTopic": 24,
            "fontPart": 18,
            "fontSubpart": 14,
            "topicColor": "#2c3e50",
            "partColor": "#34495e",
            "subpartColor": "#7f8c8d",
            "strokeColor": "#95a5a6",
            "strokeWidth": 2,
        }

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = "en",
        dimension_preference: Optional[str] = None,
        fixed_dimension: Optional[str] = None,
        dimension_only_mode: Optional[bool] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a brace map from a prompt."""
        user_id = kwargs.get("user_id")
        organization_id = kwargs.get("organization_id")
        request_type = kwargs.get("request_type", "diagram_generation")
        endpoint_path = kwargs.get("endpoint_path")
        try:
            # Three-scenario system (similar to bridge_map):
            # Scenario 1: Topic only 鈫?standard generation
            # Scenario 2: Topic + dimension 鈫?fixed_dimension mode
            # Scenario 3: Dimension only (no topic) 鈫?dimension_only_mode
            if dimension_only_mode and fixed_dimension:
                # Scenario 3: Dimension-only mode - generate topic and children based on dimension
                logger.debug(
                    "BraceMapAgent: Dimension-only mode - generating topic and children for dimension '%s'",
                    fixed_dimension,
                )
                spec = await self._generate_from_dimension_only(
                    fixed_dimension,
                    language,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                )
            else:
                # Scenario 1 or 2: Standard generation or fixed dimension with topic
                spec = await self._generate_brace_map_spec(
                    user_prompt,
                    language,
                    dimension_preference,
                    user_id=user_id,
                    organization_id=organization_id,
                    request_type=request_type,
                    endpoint_path=endpoint_path,
                    fixed_dimension=fixed_dimension,
                )
            if not spec:
                return {
                    "success": False,
                    "error": "Failed to generate brace map specification",
                }

            # Validate the generated spec
            is_valid, validation_msg = self.validate_output(spec)
            if not is_valid:
                logger.warning("BraceMapAgent: Validation failed: %s", validation_msg)
                return {
                    "success": False,
                    "error": f"Generated invalid specification: {validation_msg}",
                }

            # Enhance the spec with layout and dimensions
            enhanced_result = await self.enhance_spec(spec)
            if not enhanced_result.get("success"):
                return enhanced_result

            enhanced_spec = enhanced_result["spec"]

            logger.info("BraceMapAgent: Brace map generation completed successfully")
            return {
                "success": True,
                "spec": enhanced_spec,
                "diagram_type": self.diagram_type,
            }

        except Exception as e:
            logger.error("BraceMapAgent: Brace map generation failed: %s", e)
            return {"success": False, "error": f"Generation failed: {e}"}

    async def _generate_brace_map_spec(
        self,
        prompt: str,
        language: str,
        dimension_preference: Optional[str] = None,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = "diagram_generation",
        endpoint_path: Optional[str] = None,
        # Fixed dimension: user has already specified this, do NOT change it
        fixed_dimension: Optional[str] = None,
    ) -> Optional[Dict]:
        """Generate the brace map specification using LLM."""
        try:
            # Choose prompt based on whether user has specified a fixed dimension
            if fixed_dimension:
                logger.debug(
                    "BraceMapAgent: Using FIXED dimension mode with '%s'",
                    fixed_dimension,
                )
                system_prompt = get_prompt("brace_map_agent", language, "fixed_dimension")

                if not system_prompt:
                    logger.warning("BraceMapAgent: No fixed_dimension prompt found, using fallback")
                    if language == "zh":
                        json_example = (
                            '{"whole": "' + prompt + '", "dimension": "' + fixed_dimension + '", '
                            '"parts": [...], "alternative_dimensions": [...]}'
                        )
                        system_prompt = f"""用户已经指定了拆解维度："{fixed_dimension}"
你必须使用这个指定的拆解维度来生成括号图。不要改变或重新解释这个拆解维度。
生成一个括号图，将主题按照指定的维度进行拆解，包含3-5个部分，每个部分有2-4个子部分。
返回JSON：{json_example}

重要：dimension字段必须完全保持为"{fixed_dimension}"，不要改变它！"""
                    else:
                        system_prompt = (
                            f"""The user has ALREADY SPECIFIED the decomposition dimension: """
                            f""""{fixed_dimension}"
You MUST use this exact dimension to generate the brace map. Do NOT change or reinterpret it.

Generate a brace map decomposing the topic according to the specified dimension """
                            f""""{fixed_dimension}", with 3-5 parts, each with 2-4 subparts.
Return JSON: {{"whole": "{prompt}", "dimension": "{fixed_dimension}", """
                            f""""parts": [...], "alternative_dimensions": [...]}}

CRITICAL: The dimension field MUST remain exactly "{fixed_dimension}" """
                            f"""- do NOT change it!"""
                        )
                else:
                    system_prompt = system_prompt.format(topic=prompt)

                if language == "zh":
                    user_prompt = f"主题：{prompt}\n\n请使用指定的拆解维度「{fixed_dimension}」生成括号图。"
                else:
                    user_prompt = (
                        f"Topic: {prompt}\n\nGenerate a brace map using the "
                        f'EXACT decomposition dimension "{fixed_dimension}".'
                    )
            else:
                # No fixed dimension - use standard generation prompt
                system_prompt = get_prompt("brace_map_agent", language, "generation")

                if not system_prompt:
                    logger.error("BraceMapAgent: No prompt found for language %s", language)
                    return None
                system_prompt = system_prompt.format(topic=prompt)

                # Build user prompt with dimension preference if specified
                if dimension_preference:
                    if language == "zh":
                        user_prompt = (
                            f"请为以下描述创建一个括号图，使用指定的拆解维度'{dimension_preference}'：{prompt}"
                        )
                    else:
                        user_prompt = (
                            f"Please create a brace map for the following description "
                            f"using the specified decomposition dimension "
                            f"'{dimension_preference}': {prompt}"
                        )
                    logger.debug(
                        "BraceMapAgent: User specified dimension preference: %s",
                        dimension_preference,
                    )
                else:
                    if language == "zh":
                        user_prompt = f"请为以下描述创建一个括号图：{prompt}"
                    else:
                        user_prompt = f"Please create a brace map for the following description: {prompt}"

            # Call middleware directly - clean and efficient!
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
                diagram_type="brace_map",
            )

            if not response:
                logger.error("BraceMapAgent: No response from LLM")
                return None

            # Extract JSON from response
            # Check if response is already a dictionary (from mock client)
            if isinstance(response, dict):
                spec = response
            else:
                # Log raw response for debugging
                response_str = str(response)
                logger.debug(
                    "BraceMapAgent: Raw LLM response (first 500 chars): %s",
                    response_str[:500],
                )

                # Try to extract JSON from string response
                spec = extract_json_from_response(response_str)

                # Check if we got a non-JSON response error
                if isinstance(spec, dict) and spec.get("_error") == "non_json_response":
                    # LLM returned non-JSON asking for more info - retry with more explicit prompt
                    logger.warning(
                        "BraceMapAgent: LLM returned non-JSON response asking for more info. "
                        "Retrying with explicit JSON-only prompt."
                    )

                    # Retry with more explicit prompt emphasizing JSON-only output
                    if language == "zh":
                        retry_user_prompt = (
                            f"{user_prompt}\n\n"
                            f"重要：你必须只返回有效的JSON格式，不要询问更多信息。"
                            f"如果提示不清楚，请根据提示内容做出合理假设并直接生成JSON规范。"
                        )
                    else:
                        retry_user_prompt = (
                            f"{user_prompt}\n\n"
                            f"IMPORTANT: You MUST respond with valid JSON only. "
                            f"Do not ask for more information. "
                            f"If the prompt is unclear, make reasonable assumptions "
                            f"and generate the JSON specification directly."
                        )

                    retry_response = await llm_service.chat(
                        prompt=retry_user_prompt,
                        model=self.model,
                        system_message=system_prompt,
                        max_tokens=1000,
                        temperature=config.LLM_TEMPERATURE,
                        user_id=user_id,
                        organization_id=organization_id,
                        request_type=request_type,
                        endpoint_path=endpoint_path,
                        diagram_type="brace_map",
                    )

                    # Try extraction again
                    if isinstance(retry_response, dict):
                        spec = retry_response
                    else:
                        spec = extract_json_from_response(str(retry_response))

                        # If still non-JSON, return None
                        if isinstance(spec, dict) and spec.get("_error") == "non_json_response":
                            logger.error(
                                "BraceMapAgent: Retry also returned non-JSON response. Giving up after 1 retry attempt."
                            )
                            return None

            if not spec or (isinstance(spec, dict) and spec.get("_error")):
                logger.error(
                    "BraceMapAgent: Failed to extract JSON from LLM response. Response type: %s, Response length: %s",
                    type(response),
                    len(str(response)),
                )
                logger.error("BraceMapAgent: Raw response content: %s", str(response)[:1000])
                return None

            # Normalize field names (e.g., 'topic' -> 'whole') before validation
            spec = self._normalize_field_names(spec)
            # Log extracted spec for debugging
            spec_keys = list(spec.keys()) if isinstance(spec, dict) else "Not a dict"
            logger.debug("BraceMapAgent: Extracted spec keys: %s", spec_keys)
            if isinstance(spec, dict) and "whole" in spec:
                logger.debug(
                    "BraceMapAgent: Extracted 'whole' field value: %s",
                    spec.get("whole"),
                )

            # If fixed_dimension was provided, enforce it regardless of what LLM returned
            if fixed_dimension:
                spec["dimension"] = fixed_dimension
                logger.debug("BraceMapAgent: Enforced FIXED dimension: %s", fixed_dimension)

            return spec

        except Exception as e:
            logger.error("BraceMapAgent: Error in spec generation: %s", e)
            return None

    async def _generate_from_dimension_only(
        self,
        dimension: str,
        language: str,
        # Token tracking parameters
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        request_type: str = "diagram_generation",
        endpoint_path: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Generate brace map from a decomposition dimension only (no topic).

        This is Scenario 3 of the three-scenario system:
        - Scenario 1: Topic only 鈫?standard generation
        - Scenario 2: Topic + dimension 鈫?fixed_dimension mode
        - Scenario 3: Dimension only (no topic) 鈫?generate topic and children (this method)

        Args:
            dimension: The decomposition dimension specified by user (e.g., "Physical Parts", "Functional Modules")
            language: Language for generation

        Returns:
            Spec with generated topic and parts following the specified dimension
        """
        try:
            logger.debug(
                "BraceMapAgent: Dimension-only mode - generating topic and parts for dimension '%s'",
                dimension,
            )

            # Get the dimension-only prompt
            system_prompt = get_prompt("brace_map_agent", language, "dimension_only")

            if not system_prompt:
                logger.warning(
                    "BraceMapAgent: No dimension_only prompt found, using fixed_dimension prompt as fallback"
                )
                system_prompt = get_prompt("brace_map_agent", language, "fixed_dimension")

            # Build user prompt with the dimension
            if language == "zh":
                user_prompt = f"用户指定的拆解维度：{dimension}\n\n请根据这个拆解维度生成一个合适的主题和部分。"
            else:
                user_prompt = (
                    f"User's specified decomposition dimension: {dimension}\n\n"
                    f"Generate a suitable topic and parts following this "
                    f"decomposition dimension."
                )

            logger.debug("User prompt: %s", user_prompt)

            # Call LLM
            response = await llm_service.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                max_tokens=1000,
                temperature=config.LLM_TEMPERATURE,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                diagram_type="brace_map",
            )

            logger.debug("LLM response: %s...", response[:500] if response else "None")

            # Extract JSON from response
            if isinstance(response, dict):
                result = response
            else:
                result = extract_json_from_response(str(response))

                # Check if we got a non-JSON response error
                if isinstance(result, dict) and result.get("_error") == "non_json_response":
                    # LLM returned non-JSON asking for more info - retry with more explicit prompt
                    logger.warning(
                        "BraceMapAgent: LLM returned non-JSON response in dimension-only mode. "
                        "Retrying with explicit JSON-only prompt."
                    )

                    # Retry with more explicit prompt
                    if language == "zh":
                        retry_user_prompt = (
                            f"{user_prompt}\n\n"
                            f"重要：你必须只返回有效的JSON格式，不要询问更多信息。"
                            f"根据拆解维度直接生成JSON规范。"
                        )
                    else:
                        retry_user_prompt = (
                            f"{user_prompt}\n\n"
                            f"IMPORTANT: You MUST respond with valid JSON only. "
                            f"Do not ask for more information. "
                            f"Generate the JSON specification directly based on the decomposition dimension."
                        )

                    retry_response = await llm_service.chat(
                        prompt=retry_user_prompt,
                        model=self.model,
                        system_message=system_prompt,
                        max_tokens=1000,
                        temperature=config.LLM_TEMPERATURE,
                        user_id=user_id,
                        organization_id=organization_id,
                        request_type=request_type,
                        endpoint_path=endpoint_path,
                        diagram_type="brace_map",
                    )

                    # Try extraction again
                    if isinstance(retry_response, dict):
                        result = retry_response
                    else:
                        result = extract_json_from_response(str(retry_response))

                        # If still non-JSON, return None
                        if isinstance(result, dict) and result.get("_error") == "non_json_response":
                            logger.error(
                                "BraceMapAgent: Retry also returned non-JSON response in dimension-only mode. "
                                "Giving up after 1 retry attempt."
                            )
                            return None

            if not result or (isinstance(result, dict) and result.get("_error")):
                logger.error("BraceMapAgent: Failed to extract JSON from dimension-only response")
                return None

            # Normalize field names (e.g., 'topic' -> 'whole') before validation
            result = self._normalize_field_names(result)
            # If fixed_dimension was provided, enforce it regardless of what LLM returned
            if dimension:
                result["dimension"] = dimension
                logger.debug("BraceMapAgent: Enforced FIXED dimension: %s", dimension)

            logger.debug(
                "BraceMapAgent: Dimension-only complete - dimension: '%s', whole: '%s'",
                dimension,
                result.get("whole", "N/A"),
            )

            return result

        except Exception as e:
            logger.error("BraceMapAgent: Error in dimension-only mode: %s", e)
            return None

    def validate_output(self, output: Dict) -> Tuple[bool, str]:
        """Validate a brace map specification."""
        try:
            if not output or not isinstance(output, dict):
                return False, "Invalid specification: must be a non-empty dictionary"

            if "whole" not in output or not output["whole"]:
                return False, "Missing or empty whole field"

            if "parts" not in output or not isinstance(output["parts"], list):
                return False, "Missing or invalid parts field"

            if not output["parts"]:
                return False, "Must have at least one part"

            return True, "Valid brace map specification"
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def enhance_spec(self, spec: Dict) -> Dict:
        """Enhance a brace map specification with layout data."""
        try:
            if not spec or not isinstance(spec, dict):
                return {"success": False, "error": "Invalid specification"}

            if "whole" not in spec or not spec["whole"]:
                return {"success": False, "error": "Missing whole"}

            if "parts" not in spec or not isinstance(spec["parts"], list):
                return {"success": False, "error": "Missing parts"}

            if not spec["parts"]:
                return {"success": False, "error": "At least one part is required"}

            # Normalize field names: convert 'label' to 'name' for compatibility
            spec = self._normalize_field_names(spec)
            # Generate layout data
            dimensions = self._calculate_dimensions(spec)
            block_units = self.block_positioning.arrange_blocks(spec, dimensions, self.default_theme)
            nodes, units = self._convert_blocks_to_nodes(block_units, spec, dimensions)

            # Add layout to spec
            spec["_layout"] = {
                "nodes": [self._serialize_nodes(nodes)],
                "units": self._serialize_units(units),
                "dimensions": dimensions,
            }
            spec["_recommended_dimensions"] = dimensions
            spec["_agent"] = "brace_map_agent"

            return {"success": True, "spec": spec}

        except Exception as e:
            return {"success": False, "error": f"BraceMapAgent failed: {e}"}

    def _normalize_field_names(self, spec: Dict) -> Dict:
        """Normalize field names for compatibility with existing validation logic."""
        try:
            # Create a copy to avoid modifying the original
            normalized_spec = spec.copy()

            # Normalize 'topic' to 'whole' if 'whole' doesn't exist (backward compatibility)
            if "topic" in normalized_spec and "whole" not in normalized_spec:
                normalized_spec["whole"] = normalized_spec["topic"]
                logger.debug("BraceMapAgent: Normalized 'topic' field to 'whole'")

            # Normalize parts
            if "parts" in normalized_spec and isinstance(normalized_spec["parts"], list):
                for part in normalized_spec["parts"]:
                    if isinstance(part, dict):
                        # Convert 'label' to 'name' if 'name' doesn't exist
                        if "label" in part and "name" not in part:
                            part["name"] = part["label"]

                        # Normalize subparts
                        if "subparts" in part and isinstance(part["subparts"], list):
                            for subpart in part["subparts"]:
                                if isinstance(subpart, dict):
                                    if "label" in subpart and "name" not in subpart:
                                        subpart["name"] = subpart["label"]

            return normalized_spec

        except Exception as e:
            logger.error("Error normalizing field names: %s", e)
            return spec

    def generate_diagram(self, spec: Dict, user_id: Optional[str] = None) -> Dict:
        """Generate brace map diagram using block-based positioning with enhanced validation"""
        start_time = datetime.now()
        # Debug log removed

        try:
            # Enhanced input validation
            if not spec or not isinstance(spec, dict):
                return {
                    "success": False,
                    "error": "Invalid specification: must be a non-empty dictionary",
                    "debug_logs": [],
                }

            # Validate required fields - no fallbacks
            if "whole" not in spec or not spec["whole"]:
                return {
                    "success": False,
                    "error": 'Invalid specification: missing or empty "whole" field',
                    "debug_logs": [],
                }

            if "parts" not in spec or not isinstance(spec["parts"], list):
                return {
                    "success": False,
                    "error": 'Invalid specification: missing or invalid "parts" field',
                    "debug_logs": [],
                }

            # Validate parts structure with enhanced error messages
            for i, part in enumerate(spec["parts"]):
                if not isinstance(part, dict):
                    return {
                        "success": False,
                        "error": f"Invalid part at index {i}: must be a dictionary",
                        "debug_logs": [],
                    }

                if "name" not in part or not part["name"]:
                    return {
                        "success": False,
                        "error": f'Invalid part at index {i}: missing or empty "name" field',
                        "debug_logs": [],
                    }

                # Validate subparts structure
                if "subparts" not in part:
                    part["subparts"] = []  # Allow missing subparts as empty list
                elif not isinstance(part["subparts"], list):
                    return {
                        "success": False,
                        "error": f'Invalid part at index {i}: "subparts" must be a list',
                        "debug_logs": [],
                    }

                # Validate subparts with enhanced error messages
                for j, subpart in enumerate(part["subparts"]):
                    if not isinstance(subpart, dict):
                        return {
                            "success": False,
                            "error": f"Invalid subpart at part {i}, subpart {j}: must be a dictionary",
                            "debug_logs": [],
                        }

                    if "name" not in subpart or not subpart["name"]:
                        return {
                            "success": False,
                            "error": f'Invalid subpart at part {i}, subpart {j}: missing or empty "name" field',
                            "debug_logs": [],
                        }

            # Validate empty specification
            if not spec["parts"]:
                return {
                    "success": False,
                    "error": "Invalid specification: must have at least one part",
                    "debug_logs": [],
                }

            # Store user context if user_id provided
            if user_id and "prompt" in spec:
                self.context_manager.store_user_prompt(user_id, spec["prompt"], "brace_map")

            # Get user context for personalization
            context = self.context_manager.get_user_context(user_id) if user_id else {}

            # Alter specification based on context
            spec = self.context_manager.alter_diagram_based_on_context(spec, context)

            # Analyze complexity and determine strategy
            complexity = self.llm_processor.analyze_complexity(spec)
            strategy = self.llm_processor.determine_strategy(complexity, context.get("preferences"))

            # Debug log removed

            # Select layout algorithm
            algorithm = self.algorithm_selector.select_algorithm(spec, user_id)

            # Calculate dimensions
            dimensions = self._calculate_dimensions(spec)

            # Use block-based positioning system
            # Debug log removed
            block_units = self.block_positioning.arrange_blocks(spec, dimensions, self.default_theme)

            # Convert block units to NodePosition format for compatibility
            nodes, units = self._convert_blocks_to_nodes(block_units, spec, dimensions)

            # Validate that we have nodes
            if not nodes:
                return {
                    "success": False,
                    "error": "Failed to generate nodes from specification",
                    "debug_logs": [],
                }

            # Calculate optimal canvas dimensions
            optimal_dimensions = self._calculate_optimal_dimensions(nodes, dimensions)

            # Adjust node positions to center them in the optimal canvas
            nodes = self._adjust_node_positions_for_optimal_canvas(nodes, dimensions, optimal_dimensions)

            # Create layout data
            layout_data = {
                "units": self._serialize_units(units),
                "spacing_info": self._serialize_spacing_info(
                    SpacingInfo(
                        unit_spacing=50.0,
                        subpart_spacing=20.0,
                        brace_offset=50.0,
                        content_density=1.0,
                    )
                ),
                "text_dimensions": self.layout_calculator.calculate_text_dimensions(spec, self.default_theme),
                "canvas_dimensions": optimal_dimensions,
                "nodes": self._serialize_nodes(nodes),
            }

            # Generate SVG data
            svg_data = self._generate_svg_data_from_layout(layout_data, self.default_theme)

            # Validate SVG data
            if not svg_data or "elements" not in svg_data:
                return {
                    "success": False,
                    "error": "Failed to generate SVG data",
                    "debug_logs": [],
                }

            # Calculate performance metrics
            processing_time = (datetime.now() - start_time).total_seconds()

            result = {
                "success": True,
                "svg_data": svg_data,
                "layout_data": layout_data,
                "algorithm_used": algorithm.value,
                "complexity": complexity.value,
                "strategy": strategy.value,
                "processing_time": processing_time,
                "debug_logs": [],
            }

            # Debug log removed
            return result

        except Exception as e:
            # Debug log removed}")
            return {"success": False, "error": str(e), "debug_logs": []}

    def _convert_blocks_to_nodes(
        self, block_units: List[BlockUnit], spec: Dict, dimensions: Dict
    ) -> Tuple[List[NodePosition], List[UnitPosition]]:
        """Convert block units to NodePosition and UnitPosition format with fixed column layout"""
        nodes = []
        units = []

        # Create topic node with enhanced height to prevent squeezing
        whole = spec.get("whole", "Main Topic")
        topic_width = self._calculate_text_width(whole, self.default_theme["fontTopic"])

        # Set topic height to be larger than standard blocks but not full canvas
        # This prevents squeezing while maintaining proper positioning
        topic_height = self.default_theme["fontTopic"] + 60  # Enhanced height for topic blocks

        # Position topic in left column (Column 1) - like in the image
        padding = dimensions["padding"]

        # Topic goes in left column (Column 1) - exactly at padding + 50
        # Since text is centered within the block, we need to adjust for the block width
        topic_x = padding + 50  # Same as topic_column_x in _position_blocks

        # Topic Y position will be calculated after brace center is determined
        # Use temporary position for now
        topic_y = (dimensions["height"] - topic_height) / 2

        # Ensure topic doesn't extend beyond canvas bounds
        if topic_x + topic_width > dimensions["width"] - dimensions["padding"]:
            topic_x = dimensions["width"] - dimensions["padding"] - topic_width

        topic_node = NodePosition(
            x=topic_x,
            y=topic_y,
            width=topic_width,
            height=topic_height,
            text=whole,
            node_type="topic",
        )
        nodes.append(topic_node)

        # Convert block units to UnitPosition format
        for i, block_unit in enumerate(block_units):
            # Convert part block
            part_node = NodePosition(
                x=block_unit.part_block.x,
                y=block_unit.part_block.y,
                width=block_unit.part_block.width,
                height=block_unit.part_block.height,
                text=block_unit.part_block.text,
                node_type="part",
                part_index=i,
            )
            nodes.append(part_node)

            # Convert subpart blocks
            subpart_nodes = []
            for j, subpart_block in enumerate(block_unit.subpart_blocks):
                subpart_node = NodePosition(
                    x=subpart_block.x,
                    y=subpart_block.y,
                    width=subpart_block.width,
                    height=subpart_block.height,
                    text=subpart_block.text,
                    node_type="subpart",
                    part_index=i,
                    subpart_index=j,
                )
                subpart_nodes.append(subpart_node)
                nodes.append(subpart_node)

            # Create UnitPosition
            unit = UnitPosition(
                unit_index=i,
                x=block_unit.x,
                y=block_unit.y,
                width=block_unit.width,
                height=block_unit.height,
                part_position=part_node,
                subpart_positions=subpart_nodes,
            )
            units.append(unit)

        return nodes, units

    def _generate_svg_data_from_layout(self, layout_data: Dict, theme: Dict) -> Dict:
        """Generate SVG data from layout data with improved text alignment within blocks"""
        svg_elements = []

        # Generate nodes from layout data
        nodes_data = layout_data.get("nodes", [])

        # Add text elements for all nodes with improved alignment
        for node_data in nodes_data:
            # Calculate text position to center it within the block
            node_x = node_data["x"]
            node_y = node_data["y"]
            node_width = node_data["width"]
            node_height = node_data["height"]

            # Center text within the block
            text_x = node_x + node_width / 2
            text_y = node_y + node_height / 2

            element = {
                "type": "text",
                "x": text_x,
                "y": text_y,
                "text": node_data["text"],
                "node_type": node_data["node_type"],
                "font_size": self._get_font_size(node_data["node_type"], theme),
                "fill": self._get_node_color(node_data["node_type"], theme),
                "text_anchor": "middle",  # Center horizontally
                "dominant_baseline": "middle",  # Center vertically
                "font_weight": self._get_font_weight(node_data["node_type"]),
            }
            svg_elements.append(element)

        # Generate brace elements using minimalist design (adaptive to canvas size)
        brace_elements = self._generate_brace_elements(nodes_data, theme, layout_data.get("canvas_dimensions", {}))
        svg_elements.extend(brace_elements)

        # Use canvas dimensions from layout data
        canvas_dimensions = layout_data.get("canvas_dimensions", {})

        return {
            "elements": svg_elements,
            "width": canvas_dimensions.get("width", 800),
            "height": canvas_dimensions.get("height", 600),
            "background": "#ffffff",
            "layout_data": layout_data,
        }

    def _generate_brace_elements(self, nodes_data: List[Dict], theme: Dict, canvas_dimensions: Dict) -> List[Dict]:
        """Generate brace path elements (curly style) with adaptive widths and outline (Option 3)"""
        brace_elements = []

        # Determine adaptive stroke widths based on canvas size
        canvas_width = float(canvas_dimensions.get("width", 1000))
        canvas_height = float(canvas_dimensions.get("height", 600))
        # Base on height for visual consistency; clamp to sensible bounds
        scale_h = max(0.5, min(2.0, canvas_height / 600.0))
        main_stroke_width = max(1.5, min(5.5, 3.2 * scale_h))
        small_stroke_width = max(1.0, min(4.5, main_stroke_width * 0.66))

        # Outline widths slightly larger than main strokes
        main_outline_width = min(main_stroke_width * 1.6, main_stroke_width + 3.0)
        small_outline_width = min(small_stroke_width * 1.6, small_stroke_width + 3.0)

        # Colors
        outline_color = theme.get("braceOutlineColor", "#333333")
        brace_color = theme.get("braceColor", "#666666")

        # Separate nodes by type
        topic_nodes = [n for n in nodes_data if n["node_type"] == "topic"]
        part_nodes = [n for n in nodes_data if n["node_type"] == "part"]
        subpart_nodes = [n for n in nodes_data if n["node_type"] == "subpart"]

        if not topic_nodes or not part_nodes:
            return brace_elements

        topic_node = topic_nodes[0]

        # Generate main brace (connects topic to all parts)
        if part_nodes:
            # Find the full vertical extent of all parts (top to bottom)
            parts_top_y = min(n["y"] for n in part_nodes)
            parts_bottom_y = max(n["y"] + n["height"] for n in part_nodes)
            first_part_y = parts_top_y
            last_part_y = parts_bottom_y
            brace_height = last_part_y - first_part_y

            # Overlap-safe main brace placement between topic and parts
            topic_right = topic_node["x"] + topic_node["width"]
            parts_left = min(n["x"] for n in part_nodes)

            # Curly (math-style) main brace opening to the left (very conservative spacing)
            safety_gap = max(24.0, canvas_width * 0.03)  # Reduced from 35.0 to move brace closer to nodes

            # CRITICAL: Calculate safe positioning for LEFT-opening brace
            # Brace extends LEFT by tip_depth and RIGHT by arc_radius
            # Calculate brace height based on first and last part centers
            first_part_center_y = min(n["y"] + n["height"] / 2 for n in part_nodes)
            last_part_center_y = max(n["y"] + n["height"] / 2 for n in part_nodes)

            # Current calculation gives us total range (A) = true brace height (B) + 2 * arc radius
            # We need to solve: A = B + 2 * (B * 0.04) = B + 0.08 * B = B * (1 + 0.08) = B * 1.08
            # So: B = A / 1.08
            total_range_a = last_part_center_y - first_part_center_y
            true_brace_height_b = total_range_a / 1.08  # Remove arc radius contribution
            arc_radius = true_brace_height_b * 0.04  # Arc radius based on true height
            tip_depth = true_brace_height_b * 0.05  # Tip depth based on true height

            # CRITICAL: Position brace to the RIGHT of topic text box
            # Brace should be positioned after topic with sufficient gap
            # The brace's leftmost point (brace_x - tip_depth) should be after topic's right edge
            min_brace_x = topic_right + safety_gap + tip_depth  # Minimum X to avoid overlap with topic

            # Calculate maximum X position (before parts start)
            max_brace_x = parts_left - safety_gap - arc_radius  # Maximum X to avoid overlap with parts

            # Position brace to the right of topic
            if min_brace_x >= max_brace_x:
                # Not enough space - position as close to topic as possible
                # Reduced from 6px to move brace closer to topic
                brace_x = topic_right + safety_gap + tip_depth + 3.0
            else:
                # Position brace closer to both topic and parts
                # Reduced from 30% to 15% to move brace closer to both nodes
                brace_x = min_brace_x + (max_brace_x - min_brace_x) * 0.15

            # CRITICAL: Brace boundaries include arc radius for complete display (arcs extend inward)
            brace_start_y = first_part_center_y + arc_radius  # Include top arc radius (inward)
            brace_end_y = last_part_center_y - arc_radius  # Include bottom arc radius (inward)
            brace_height = brace_end_y - brace_start_y  # Total height including arcs
            brace_center_y = (brace_start_y + brace_end_y) / 2  # Center between adjusted boundaries

            # CRITICAL: Adjust topic position to align with brace tip (left tip horizontal line)
            # The brace tip is at the vertical center of the brace, which is brace_center_y
            # Topic center line should align with brace_center_y
            # Update topic node position so its center line aligns with brace center line
            topic_node["y"] = brace_center_y - topic_node["height"] / 2

            y_top = brace_start_y
            y_bot = brace_end_y
            y_mid = (y_top + y_bot) / 2.0

            # New sharp tip brace design - matching kh4.html (LEFT direction, precise proportions)
            tip_depth = brace_height * 0.05  # Tip protrudes to the LEFT (5% of height)
            tip_width = brace_height * 0.01  # Sharp tip width (1% of height)
            corner_arc = brace_height * 0.005  # Smooth transition at tip (0.5% of height)

            # Control points for upper and lower halves (symmetric) - LEFT direction
            cp_top_x = brace_x - corner_arc
            cp_top_y = y_mid - tip_width
            cp_bottom_x = brace_x - corner_arc
            cp_bottom_y = y_mid + tip_width
            tip_x = brace_x - tip_depth  # LEFT direction

            # Main brace path with sharp mid-point tip
            brace_path = (
                f"M {brace_x:.2f} {y_top:.2f} "
                f"C {cp_top_x:.2f} {y_top + (y_mid - y_top - tip_width) / 2:.2f} "
                f"{cp_top_x:.2f} {cp_top_y:.2f} {tip_x:.2f} {y_mid:.2f} "
                f"C {cp_bottom_x:.2f} {cp_bottom_y:.2f} "
                f"{cp_bottom_x:.2f} {y_mid + (y_bot - y_mid - tip_width) / 2:.2f} "
                f"{brace_x:.2f} {y_bot:.2f}"
            )

            # Outline (draw first)
            brace_elements.append(
                {
                    "type": "path",
                    "d": brace_path,
                    "fill": "none",
                    "stroke": outline_color,
                    "stroke_width": main_outline_width,
                    "stroke_linecap": "round",
                    "stroke_linejoin": "round",
                }
            )
            # Main stroke (on top)
            brace_elements.append(
                {
                    "type": "path",
                    "d": brace_path,
                    "fill": "none",
                    "stroke": brace_color,
                    "stroke_width": main_stroke_width,
                    "stroke_linecap": "round",
                    "stroke_linejoin": "round",
                }
            )

            # Add decorative arcs at top and bottom (if height is sufficient)
            arc_radius = brace_height * 0.04  # Arc radius 4% of height
            if brace_height > 50:
                # Top arc - corrected position
                upper_cx = brace_x + arc_radius
                upper_start_x = upper_cx - arc_radius
                upper_end_x = upper_cx
                upper_end_y = y_top - arc_radius
                top_arc_path = (
                    f"M {upper_start_x:.2f} {y_top:.2f} A {arc_radius:.2f} "
                    f"{arc_radius:.2f} 0 0 1 {upper_end_x:.2f} {upper_end_y:.2f}"
                )
                brace_elements.append(
                    {
                        "type": "path",
                        "d": top_arc_path,
                        "fill": "none",
                        "stroke": outline_color,
                        "stroke_width": main_outline_width,
                        "stroke_linecap": "round",
                        "stroke_linejoin": "round",
                    }
                )
                brace_elements.append(
                    {
                        "type": "path",
                        "d": top_arc_path,
                        "fill": "none",
                        "stroke": brace_color,
                        "stroke_width": main_stroke_width,
                        "stroke_linecap": "round",
                        "stroke_linejoin": "round",
                    }
                )

                # Bottom arc - corrected position
                lower_cx = brace_x + arc_radius
                lower_start_x = lower_cx - arc_radius
                lower_end_x = lower_cx
                lower_end_y = y_bot + arc_radius
                bottom_arc_path = (
                    f"M {lower_start_x:.2f} {y_bot:.2f} A {arc_radius:.2f} "
                    f"{arc_radius:.2f} 0 0 0 {lower_end_x:.2f} {lower_end_y:.2f}"
                )
                brace_elements.append(
                    {
                        "type": "path",
                        "d": bottom_arc_path,
                        "fill": "none",
                        "stroke": outline_color,
                        "stroke_width": main_outline_width,
                        "stroke_linecap": "round",
                        "stroke_linejoin": "round",
                    }
                )
                brace_elements.append(
                    {
                        "type": "path",
                        "d": bottom_arc_path,
                        "fill": "none",
                        "stroke": brace_color,
                        "stroke_width": main_stroke_width,
                        "stroke_linecap": "round",
                        "stroke_linejoin": "round",
                    }
                )

        # Generate small braces (connect each part to its subparts)
        for part_node in part_nodes:
            part_index = part_node.get("part_index", 0)

            # Find subparts for this part
            part_subparts = [n for n in subpart_nodes if n.get("part_index") == part_index]

            if part_subparts:
                # Find the full vertical extent of subparts for this part (top to bottom)
                subparts_top_y = min(n["y"] for n in part_subparts)
                subparts_bottom_y = max(n["y"] + n["height"] for n in part_subparts)
                _first_subpart_y = subparts_top_y
                _last_subpart_y = subparts_bottom_y
                subpart_brace_height = _last_subpart_y - _first_subpart_y

                # Overlap-safe small brace placement between part and subparts
                part_right = part_node["x"] + part_node["width"]
                subparts_left = min(n["x"] for n in part_subparts)

                # Reduced from 28.0 to move small brace closer to nodes
                small_safety_gap = max(20.0, canvas_width * 0.025)

                # CRITICAL: Calculate safe positioning for LEFT-opening small brace
                # Calculate small brace height based on first and last subpart centers
                first_subpart_center_y = min(n["y"] + n["height"] / 2 for n in part_subparts)
                last_subpart_center_y = max(n["y"] + n["height"] / 2 for n in part_subparts)

                # Apply same logic as main brace: calculate true height and arc radius
                total_subpart_range_a = last_subpart_center_y - first_subpart_center_y
                true_small_brace_height_b = total_subpart_range_a / 1.08  # Remove arc radius contribution
                s_arc_radius = true_small_brace_height_b * 0.04  # Arc radius based on true height
                s_tip_depth = true_small_brace_height_b * 0.05  # Tip depth based on true height

                # Calculate safe brace X position:
                # 1. Tip must not overlap part: small_brace_x >= part_right + gap + tip_depth
                # 2. Right edge must not overlap subparts: small_brace_x <= subparts_left - gap - arc_radius

                min_sx = part_right + small_safety_gap + s_tip_depth
                max_sx = subparts_left - small_safety_gap - s_arc_radius

                if min_sx > max_sx:
                    # Very tight space: position as safely as possible
                    small_brace_x = min_sx
                else:
                    # Position small brace closer to both parts and subparts
                    # Reduced from 0.5 (middle) to 0.2 to move closer to nodes
                    small_brace_x = min_sx + (max_sx - min_sx) * 0.2

                # CRITICAL: Small brace boundaries include arc radius for display
                small_brace_start_y = first_subpart_center_y + s_arc_radius
                small_brace_end_y = last_subpart_center_y - s_arc_radius
                subpart_brace_height = small_brace_end_y - small_brace_start_y
                small_brace_center_y = (small_brace_start_y + small_brace_end_y) / 2

                yt = small_brace_start_y
                yb = small_brace_end_y
                ym = small_brace_center_y

                # New sharp tip brace design for small braces - matching kh4.html (LEFT direction, precise proportions)
                s_tip_depth = subpart_brace_height * 0.05  # Tip protrudes to the LEFT (5% of height)
                s_tip_width = subpart_brace_height * 0.01  # Sharp tip width (1% of height)
                s_corner_arc = subpart_brace_height * 0.005  # Smooth transition (0.5% of height)

                # Control points for upper and lower halves (symmetric) - LEFT direction
                s_cp_top_x = small_brace_x - s_corner_arc
                s_cp_top_y = ym - s_tip_width
                s_cp_bottom_x = small_brace_x - s_corner_arc
                s_cp_bottom_y = ym + s_tip_width
                s_tip_x = small_brace_x - s_tip_depth  # LEFT direction

                # Main small brace path with sharp mid-point tip
                small_brace_path = (
                    f"M {small_brace_x:.2f} {yt:.2f} "
                    f"C {s_cp_top_x:.2f} {yt + (ym - yt - s_tip_width) / 2:.2f} "
                    f"{s_cp_top_x:.2f} {s_cp_top_y:.2f} {s_tip_x:.2f} {ym:.2f} "
                    f"C {s_cp_bottom_x:.2f} {s_cp_bottom_y:.2f} "
                    f"{s_cp_bottom_x:.2f} {ym + (yb - ym - s_tip_width) / 2:.2f} "
                    f"{small_brace_x:.2f} {yb:.2f}"
                )

                # Outline (draw first)
                brace_elements.append(
                    {
                        "type": "path",
                        "d": small_brace_path,
                        "fill": "none",
                        "stroke": outline_color,
                        "stroke_width": small_outline_width,
                        "stroke_linecap": "round",
                        "stroke_linejoin": "round",
                    }
                )
                # Main stroke (on top)
                brace_elements.append(
                    {
                        "type": "path",
                        "d": small_brace_path,
                        "fill": "none",
                        "stroke": brace_color,
                        "stroke_width": small_stroke_width,
                        "stroke_linecap": "round",
                        "stroke_linejoin": "round",
                    }
                )

                # Add decorative arcs at top and bottom for small braces (if height is sufficient)
                s_arc_radius = subpart_brace_height * 0.04  # Arc radius 4% of height
                if subpart_brace_height > 50:
                    # Top arc - corrected position
                    s_upper_cx = small_brace_x + s_arc_radius
                    s_upper_start_x = s_upper_cx - s_arc_radius
                    s_upper_end_x = s_upper_cx
                    s_upper_end_y = yt - s_arc_radius
                    s_top_arc_path = (
                        f"M {s_upper_start_x:.2f} {yt:.2f} A {s_arc_radius:.2f} "
                        f"{s_arc_radius:.2f} 0 0 1 "
                        f"{s_upper_end_x:.2f} {s_upper_end_y:.2f}"
                    )
                    brace_elements.append(
                        {
                            "type": "path",
                            "d": s_top_arc_path,
                            "fill": "none",
                            "stroke": outline_color,
                            "stroke_width": small_outline_width,
                            "stroke_linecap": "round",
                            "stroke_linejoin": "round",
                        }
                    )
                    brace_elements.append(
                        {
                            "type": "path",
                            "d": s_top_arc_path,
                            "fill": "none",
                            "stroke": brace_color,
                            "stroke_width": small_stroke_width,
                            "stroke_linecap": "round",
                            "stroke_linejoin": "round",
                        }
                    )

                    # Bottom arc - corrected position
                    s_lower_cx = small_brace_x + s_arc_radius
                    s_lower_start_x = s_lower_cx - s_arc_radius
                    s_lower_end_x = s_lower_cx
                    s_lower_end_y = yb + s_arc_radius
                    s_bottom_arc_path = (
                        f"M {s_lower_start_x:.2f} {yb:.2f} A {s_arc_radius:.2f} "
                        f"{s_arc_radius:.2f} 0 0 0 "
                        f"{s_lower_end_x:.2f} {s_lower_end_y:.2f}"
                    )
                    brace_elements.append(
                        {
                            "type": "path",
                            "d": s_bottom_arc_path,
                            "fill": "none",
                            "stroke": outline_color,
                            "stroke_width": small_outline_width,
                            "stroke_linecap": "round",
                            "stroke_linejoin": "round",
                        }
                    )
                    brace_elements.append(
                        {
                            "type": "path",
                            "d": s_bottom_arc_path,
                            "fill": "none",
                            "stroke": brace_color,
                            "stroke_width": small_stroke_width,
                            "stroke_linecap": "round",
                            "stroke_linejoin": "round",
                        }
                    )

        return brace_elements

    def _get_font_weight(self, node_type: str) -> str:
        """Get font weight for node type using configuration"""
        return FONT_WEIGHT_CONFIG.get(node_type, "normal")

    def _calculate_dimensions(self, spec: Dict) -> Dict:
        """Calculate initial canvas dimensions based on actual content analysis"""
        parts = spec.get("parts", [])
        whole = spec.get("whole", "Main Topic")
        total_subparts = sum(len(part.get("subparts", [])) for part in parts)
        total_parts = len(parts)

        # Calculate max text length safely
        text_lengths = [len(whole)]
        if parts:
            text_lengths.extend(len(part["name"]) for part in parts)
            for part in parts:
                if "subparts" in part and part["subparts"]:
                    text_lengths.extend(len(subpart["name"]) for subpart in part["subparts"])

        max_text_length = max(text_lengths) if text_lengths else len(whole)

        # Calculate dimensions based on actual content
        # Base dimensions per element type
        topic_height = 84  # fontTopic + 60
        part_height = 38  # fontPart + 20
        subpart_height = 34  # fontSubpart + 20

        # Calculate required height based on content
        if total_subparts == 0:
            # Only topic and parts
            # 20px spacing between parts
            required_height = topic_height + (total_parts * part_height) + (total_parts * 20)
        else:
            # Topic + parts + subparts
            # Spacing
            required_height = (
                topic_height
                + (total_parts * part_height)
                + (total_subparts * subpart_height)
                + (total_parts * 30)
                + (total_subparts * 15)
            )

        # Calculate required width for 5-column layout
        # Column 1: Topic, Column 2: Main brace, Column 3: Parts,
        # Column 4: Small braces, Column 5: Subparts
        estimated_topic_width = max_text_length * 12  # Approximate character width
        estimated_part_width = max(len(part["name"]) for part in parts) * 10 if parts else 100
        estimated_subpart_width = (
            max(len(subpart["name"]) for part in parts for subpart in part.get("subparts", [])) * 8
            if total_subparts > 0
            else 100
        )

        # 5-column layout requires more width + extra space for brace tip
        brace_tip_space = 100  # Extra space for brace tip extension
        required_width = (
            estimated_topic_width + 150 + estimated_part_width + 150 + estimated_subpart_width + 120 + brace_tip_space
        )

        # Add watermark space (bottom and right margins)
        watermark_margin = 24  # Tighter watermark margin

        # Calculate final dimensions with minimal padding - no hardcoded minimums
        final_width = required_width + watermark_margin
        final_height = required_height + watermark_margin

        # Ensure reasonable aspect ratio without shrinking content width/height
        aspect_ratio = final_width / final_height
        if aspect_ratio > 3:  # Too wide: increase height instead of reducing width
            final_height = max(final_height, int(final_width / 2.5))
        elif aspect_ratio < 0.5:  # Too tall: increase width instead of reducing height
            final_width = max(final_width, int(final_height * 0.8))

        # Minimal padding for content
        padding = 16  # Tighter padding for brace map

        return {
            "width": int(final_width),
            "height": int(final_height),
            "padding": padding,
        }

    def _calculate_optimal_dimensions(self, nodes: List[NodePosition], initial_dimensions: Dict) -> Dict:
        """Calculate optimal canvas dimensions based on actual node positions with watermark space"""
        if not nodes:
            return initial_dimensions

        # Filter out nodes with invalid coordinates
        valid_nodes = [
            node for node in nodes if node.x is not None and node.y is not None and node.width > 0 and node.height > 0
        ]

        if not valid_nodes:
            return initial_dimensions

        # Calculate actual bounds of all nodes (using node boundaries, not centers)
        min_x = min(node.x for node in valid_nodes)
        max_x = max(node.x + node.width for node in valid_nodes)
        min_y = min(node.y for node in valid_nodes)
        max_y = max(node.y + node.height for node in valid_nodes)

        # Calculate required canvas size
        content_width = max_x - min_x
        content_height = max_y - min_y

        # Add minimal padding for content (left padding target)
        content_padding = 24  # Tighter left margin

        # Add watermark space (bottom and right margins)
        watermark_margin = 80  # Space for watermark

        # Calculate optimal dimensions with proper text padding
        # For center-anchored text, we need padding equal to half the maximum text width plus buffer
        # Find the maximum width of all nodes to ensure text doesn't get cut off
        max_text_extension = 0
        if nodes:
            for node in nodes:
                # For center-anchored text, calculate how far it extends beyond its position
                text_extension = node.width / 2
                max_text_extension = max(max_text_extension, text_extension)

        # Right padding should be at least the maximum text extension plus a small buffer
        right_spacing = max(50, max_text_extension + 20)  # Ensure adequate padding for center-anchored text
        optimal_width = int(content_width + content_padding + right_spacing)
        # Height keeps additional space for watermark at bottom
        optimal_height = int(content_height + 2 * content_padding + watermark_margin)

        # Ensure content fits without excessive whitespace - no hardcoded minimums
        optimal_width = int(optimal_width)
        optimal_height = int(optimal_height)

        # Ensure reasonable aspect ratio without shrinking content; expand the smaller side
        aspect_ratio = optimal_width / optimal_height
        if aspect_ratio > 3:  # Too wide: expand height
            optimal_height = max(optimal_height, int(optimal_width / 2.5))
        elif aspect_ratio < 0.5:  # Too tall: expand width
            optimal_width = max(optimal_width, int(optimal_height * 0.8))

        return {
            "width": int(optimal_width),
            "height": int(optimal_height),
            "padding": initial_dimensions["padding"],
            "content_bounds": {
                "min_x": min_x,
                "max_x": max_x,
                "min_y": min_y,
                "max_y": max_y,
            },
        }

    def _adjust_node_positions_for_optimal_canvas(
        self,
        nodes: List[NodePosition],
        _initial_dimensions: Dict,
        optimal_dimensions: Dict,
    ) -> List[NodePosition]:
        """Adjust node positions to center them in the optimal canvas while preserving topic alignment"""
        if not nodes:
            return nodes

        content_bounds = optimal_dimensions["content_bounds"]

        # Calculate content dimensions
        _content_width = content_bounds["max_x"] - content_bounds["min_x"]
        _content_height = content_bounds["max_y"] - content_bounds["min_y"]

        # Calculate minimal padding for centering
        content_padding = 40  # Minimal padding around content

        # Calculate centering offsets with minimal padding (never negative)
        offset_x = max(0, content_padding - content_bounds["min_x"])
        offset_y = max(0, content_padding - content_bounds["min_y"])

        # Find topic and part nodes
        topic_nodes = [node for node in nodes if node.node_type == "topic"]
        part_nodes = [node for node in nodes if node.node_type == "part"]

        # Calculate the original alignment between topic and parts
        original_topic_part_alignment = None
        if topic_nodes and part_nodes:
            topic_node = topic_nodes[0]
            part_centers = [part.y + part.height / 2 for part in part_nodes]
            parts_center_y = sum(part_centers) / len(part_centers)
            topic_center_y = topic_node.y + topic_node.height / 2
            original_topic_part_alignment = topic_center_y - parts_center_y
            # Original topic-part alignment calculated

        # Apply offset to all nodes
        adjusted_nodes = []
        for node in nodes:
            adjusted_node = NodePosition(
                x=node.x + offset_x,
                y=node.y + offset_y,
                width=node.width,
                height=node.height,
                text=node.text,
                node_type=node.node_type,
                part_index=node.part_index,
                subpart_index=node.subpart_index,
            )
            adjusted_nodes.append(adjusted_node)

        # If we had topic-part alignment, preserve it after adjustment
        if original_topic_part_alignment is not None and topic_nodes and part_nodes:
            adjusted_topic = next((node for node in adjusted_nodes if node.node_type == "topic"), None)
            adjusted_parts = [node for node in adjusted_nodes if node.node_type == "part"]

            if adjusted_topic and adjusted_parts:
                # Calculate new parts center after adjustment
                new_part_centers = [part.y + part.height / 2 for part in adjusted_parts]
                new_parts_center_y = sum(new_part_centers) / len(new_part_centers)

                # Calculate what the topic center should be to maintain alignment
                target_topic_center_y = new_parts_center_y + original_topic_part_alignment

                # Calculate the new topic Y position
                new_topic_y = target_topic_center_y - adjusted_topic.height / 2

                # Topic position adjustment completed

                # Update topic position
                adjusted_topic.y = new_topic_y

                # Topic position updated

        return adjusted_nodes

    def _handle_positioning(self, spec: Dict, dimensions: Dict, theme: Dict) -> LayoutResult:
        """Handle node positioning using flexible dynamic algorithm with optimal canvas sizing"""
        start_time = datetime.now()

        # Calculate text dimensions
        text_dimensions = self.layout_calculator.calculate_text_dimensions(spec, theme)

        # Calculate unit positions using initial dimensions
        units = self.layout_calculator.calculate_unit_positions(spec, dimensions, theme)

        # Create all nodes
        nodes = []

        # Add all unit nodes first
        for unit in units:
            nodes.append(unit.part_position)
            nodes.extend(unit.subpart_positions)

        # Calculate main topic position BEFORE adjustments
        topic_x, topic_y = self.layout_calculator.calculate_main_topic_position(units, dimensions)

        # Add main topic
        whole = spec.get("whole", "Main Topic")
        topic_node = NodePosition(
            x=topic_x,
            y=topic_y,
            width=text_dimensions["topic"]["width"],
            height=text_dimensions["topic"]["height"],
            text=whole,
            node_type="topic",
        )
        nodes.append(topic_node)

        # Calculate optimal canvas dimensions based on actual node positions
        optimal_dimensions = self._calculate_optimal_dimensions(nodes, dimensions)

        # Adjust node positions to center them in the optimal canvas
        nodes = self._adjust_node_positions_for_optimal_canvas(nodes, dimensions, optimal_dimensions)

        # Validate and resolve collisions using optimal dimensions
        nodes = self._validate_and_adjust_boundaries(nodes, optimal_dimensions)
        nodes = CollisionDetector.resolve_collisions(nodes, padding=20.0)

        # Update unit positions to match adjusted nodes
        adjusted_units = []
        for i, unit in enumerate(units):
            # Find the adjusted part node
            adjusted_part = next(
                (node for node in nodes if node.node_type == "part" and node.part_index == i),
                None,
            )
            if adjusted_part is None:
                # Create a new part node if not found
                adjusted_part = NodePosition(
                    x=unit.part_position.x,
                    y=unit.part_position.y,
                    width=unit.part_position.width,
                    height=unit.part_position.height,
                    text=unit.part_position.text,
                    node_type="part",
                    part_index=i,
                )

            # Find the adjusted subpart nodes
            adjusted_subparts = [node for node in nodes if node.node_type == "subpart" and node.part_index == i]

            # Create adjusted unit
            adjusted_unit = UnitPosition(
                unit_index=unit.unit_index,
                x=adjusted_part.x,
                y=adjusted_part.y,
                width=unit.width,
                height=unit.height,
                part_position=adjusted_part,
                subpart_positions=adjusted_subparts,
            )
            adjusted_units.append(adjusted_unit)

        # After adjustments, recompute tight canvas width accounting for center-anchored text
        if nodes:
            # For center-anchored text, the rightmost edge is at node.x + node.width/2
            adjusted_max_x = max(node.x + node.width / 2 for node in nodes)
            # Add buffer for center-anchored text (half width of largest text + safety margin)
            max_half_width = max(node.width / 2 for node in nodes) if nodes else 0
            tight_right_buffer = max(50, max_half_width + 20)
            tight_width = int(adjusted_max_x + tight_right_buffer)
            # Update optimal dimensions width only (preserve height and padding)
            optimal_dimensions = {
                **optimal_dimensions,
                "width": tight_width,
            }

        # Create layout data with updated optimal dimensions
        layout_data = {
            "units": self._serialize_units(adjusted_units),
            "spacing_info": self._serialize_spacing_info(
                SpacingInfo(
                    unit_spacing=50.0,
                    subpart_spacing=20.0,
                    brace_offset=50.0,
                    content_density=1.0,
                )
            ),
            "text_dimensions": text_dimensions,
            "canvas_dimensions": optimal_dimensions,
            "nodes": self._serialize_nodes(nodes),
        }

        processing_time = (datetime.now() - start_time).total_seconds()

        return LayoutResult(
            nodes=nodes,
            braces=[],  # Braces will be handled in rendering phase
            dimensions=optimal_dimensions,  # Use updated optimal dimensions
            algorithm_used=LayoutAlgorithm.FLEXIBLE_DYNAMIC,
            performance_metrics={"processing_time": processing_time},
            layout_data=layout_data,
        )

    def _serialize_units(self, units: List[UnitPosition]) -> List[Dict]:
        """Convert UnitPosition objects to JSON-serializable dictionaries"""
        serialized_units = []
        for unit in units:
            serialized_unit = {
                "unit_index": unit.unit_index,
                "x": unit.x,
                "y": unit.y,
                "width": unit.width,
                "height": unit.height,
                "part_position": {
                    "x": unit.part_position.x,
                    "y": unit.part_position.y,
                    "width": unit.part_position.width,
                    "height": unit.part_position.height,
                    "text": unit.part_position.text,
                    "node_type": unit.part_position.node_type,
                    "part_index": unit.part_position.part_index,
                    "subpart_index": unit.part_position.subpart_index,
                },
                "subpart_positions": [
                    {
                        "x": subpart.x,
                        "y": subpart.y,
                        "width": subpart.width,
                        "height": subpart.height,
                        "text": subpart.text,
                        "node_type": subpart.node_type,
                        "part_index": subpart.part_index,
                        "subpart_index": subpart.subpart_index,
                    }
                    for subpart in unit.subpart_positions
                ],
            }
            serialized_units.append(serialized_unit)
        return serialized_units

    def _serialize_spacing_info(self, spacing_info: SpacingInfo) -> Dict:
        """Convert SpacingInfo object to JSON-serializable dictionary"""
        return {
            "unit_spacing": spacing_info.unit_spacing,
            "subpart_spacing": spacing_info.subpart_spacing,
            "brace_offset": spacing_info.brace_offset,
            "content_density": spacing_info.content_density,
        }

    def _serialize_nodes(self, nodes: List[NodePosition]) -> List[Dict]:
        """Convert NodePosition objects to JSON-serializable dictionaries"""
        serialized_nodes = []
        for node in nodes:
            serialized_node = {
                "x": round(node.x, 1) if isinstance(node.x, (int, float)) else node.x,
                "y": round(node.y, 1) if isinstance(node.y, (int, float)) else node.y,
                "width": round(node.width, 1) if isinstance(node.width, (int, float)) else node.width,
                "height": round(node.height, 1) if isinstance(node.height, (int, float)) else node.height,
                "text": node.text,
                "node_type": node.node_type,
                "part_index": node.part_index,
                "subpart_index": node.subpart_index,
            }
            serialized_nodes.append(serialized_node)
        return serialized_nodes

    def _validate_and_adjust_boundaries(self, nodes: List[NodePosition], dimensions: Dict) -> List[NodePosition]:
        """Validate node boundaries and adjust if necessary"""
        adjusted_nodes = []

        for node in nodes:
            # Check if node extends beyond canvas boundaries
            # Nodes are positioned with their top-left corner at (x, y)
            node.x = max(node.x, dimensions["padding"])
            if node.x + node.width > dimensions["width"] - dimensions["padding"]:
                node.x = dimensions["width"] - dimensions["padding"] - node.width
            node.y = max(node.y, dimensions["padding"])
            if node.y + node.height > dimensions["height"] - dimensions["padding"]:
                node.y = dimensions["height"] - dimensions["padding"] - node.height

            adjusted_nodes.append(node)

        return adjusted_nodes

    def _generate_svg_data(self, layout_result: LayoutResult, theme: Dict) -> Dict:
        """Generate SVG data for rendering (layout phase only)"""
        svg_elements = []

        # Generate nodes only (braces will be handled in rendering phase)
        for node in layout_result.nodes:
            element = {
                "type": "text",
                "x": node.x,
                "y": node.y,
                "text": node.text,
                "node_type": node.node_type,  # Add node_type for identification
                "font_size": self._get_font_size(node.node_type, theme),
                "fill": self._get_node_color(node.node_type, theme),
                "text_anchor": "middle",
                "dominant_baseline": "middle",
            }
            svg_elements.append(element)

        # Use optimal dimensions from layout result
        optimal_dimensions = layout_result.dimensions

        return {
            "elements": svg_elements,
            "width": optimal_dimensions["width"],
            "height": optimal_dimensions["height"],
            "background": "#ffffff",
            "layout_data": layout_result.layout_data,  # Include layout data for rendering phase
        }

    def _get_font_size(self, node_type: str, theme: Dict) -> int:
        """Get font size for node type"""
        font_map = {
            "topic": theme["fontTopic"],
            "part": theme["fontPart"],
            "subpart": theme["fontSubpart"],
        }
        return font_map.get(node_type, theme["fontPart"])

    def _get_node_color(self, node_type: str, theme: Dict) -> str:
        """Get color for node type"""
        color_map = {
            "topic": theme["topicColor"],
            "part": theme["partColor"],
            "subpart": theme["subpartColor"],
        }
        return color_map.get(node_type, theme["partColor"])

    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate text width based on font size and character count"""
        char_widths = {
            "i": 0.3,
            "l": 0.3,
            "I": 0.4,
            "f": 0.4,
            "t": 0.4,
            "r": 0.4,
            "m": 0.8,
            "w": 0.8,
            "M": 0.8,
            "W": 0.8,
            "default": 0.6,
        }

        total_width = 0
        for char in text:
            char_width = char_widths.get(char, char_widths["default"])
            total_width += char_width * font_size

        return total_width


# Export the main agent class
__all__ = ["BraceMapAgent"]
