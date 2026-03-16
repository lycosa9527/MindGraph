"""
Block-based positioning system and flexible layout calculator for brace maps.
"""
from typing import Any, Dict, List, Tuple, Union

from .brace_map_models import (
    Block,
    BlockUnit,
    CHAR_WIDTH_CONFIG,
    FONT_WEIGHT_CONFIG,
    NodePosition,
    SpacingInfo,
    UnitPosition,
)


class BlockBasedPositioningSystem:
    """Block-based positioning system that arranges nodes like LEGO pieces"""

    def __init__(self):
        pass

    def arrange_blocks(self, spec: Dict, dimensions: Dict, theme: Dict) -> List[BlockUnit]:
        """Arrange blocks using LEGO-like positioning"""
        # Step 1: Create blocks from specification
        blocks = self._create_blocks_from_spec(spec, theme)
        # Step 2: Group blocks into units
        units = self._group_blocks_into_units(blocks)
        # Step 3: Calculate optimal spacing and padding
        spacing_config = self._calculate_spacing_config(spec, dimensions, theme)
        # Step 4: Position blocks using block-based algorithm
        positioned_units = self._position_blocks(units, spacing_config, dimensions)
        return positioned_units

    def _create_blocks_from_spec(self, spec: Dict, theme: Dict) -> List[Block]:
        """Create blocks from specification with standard heights for each block type"""
        blocks = []

        # Define standard block heights (only width varies based on text)
        topic_height = theme['fontTopic'] + 20
        part_height = theme['fontPart'] + 20
        subpart_height = theme['fontSubpart'] + 20

        # Create topic block
        whole = spec.get('whole', 'Main Topic')
        topic_width = self._calculate_text_width(whole, theme['fontTopic'])
        topic_block = Block(
            id='topic',
            x=0, y=0,  # Will be positioned later
            width=topic_width,
            height=topic_height,  # Standard height for all topic blocks
            text=whole,
            node_type='topic'
        )
        blocks.append(topic_block)

        # Create part and subpart blocks
        for i, part in enumerate(spec.get('parts', [])):
            part_width = self._calculate_text_width(part['name'], theme['fontPart'])
            part_block = Block(
                id=f'part_{i}',
                x=0, y=0,  # Will be positioned later
                width=part_width,
                height=part_height,  # Standard height for all part blocks
                text=part['name'],
                node_type='part',
                part_index=i
            )
            blocks.append(part_block)

            # Create subpart blocks
            for j, subpart in enumerate(part.get('subparts', [])):
                subpart_width = self._calculate_text_width(subpart['name'], theme['fontSubpart'])
                subpart_block = Block(
                    id=f'subpart_{i}_{j}',
                    x=0, y=0,  # Will be positioned later
                    width=subpart_width,
                    height=subpart_height,  # Standard height for all subpart blocks
                    text=subpart['name'],
                    node_type='subpart',
                    part_index=i,
                    subpart_index=j,
                    parent_block_id=f'part_{i}'
                )
                blocks.append(subpart_block)

        return blocks

    def _group_blocks_into_units(self, blocks: List[Block]) -> List[BlockUnit]:
        """Group blocks into units (part + subparts)"""
        units = []

        # Find all part blocks
        part_blocks = [block for block in blocks if block.node_type == 'part']

        for part_block in part_blocks:
            # Find subpart blocks belonging to this part
            subpart_blocks = [block for block in blocks
                            if block.node_type == 'subpart' and
                            block.parent_block_id == part_block.id]

            unit = BlockUnit(
                unit_id=part_block.id,
                part_block=part_block,
                subpart_blocks=subpart_blocks,
                x=0, y=0, width=0, height=0  # Will be calculated later
            )
            units.append(unit)

        return units

    def _calculate_spacing_config(self, spec: Dict, dimensions: Dict, _theme: Dict) -> Dict:
        """Calculate dynamic spacing configuration based on content"""
        parts = spec.get('parts', [])
        total_parts = len(parts)
        total_subparts = sum(len(part.get('subparts', [])) for part in parts)

        # Calculate complexity score
        complexity_score = total_parts * 2 + total_subparts * 1.5

        # Dynamic spacing based on complexity - tightened for more compact layout
        if complexity_score > 50:
            block_spacing = 12.0  # Reduced from 20.0 for tighter spacing
            unit_spacing = 18.0   # Reduced from 30.0 for tighter spacing
            brace_padding = 30.0  # Reduced from 40.0 for tighter spacing
        elif complexity_score > 25:
            block_spacing = 10.0  # Reduced from 15.0 for tighter spacing
            unit_spacing = 15.0   # Reduced from 25.0 for tighter spacing
            brace_padding = 24.0  # Reduced from 30.0 for tighter spacing
        else:
            block_spacing = 8.0   # Reduced from 12.0 for tighter spacing
            unit_spacing = 12.0   # Reduced from 20.0 for tighter spacing
            brace_padding = 20.0  # Reduced from 25.0 for tighter spacing

        # Calculate available space
        available_width = dimensions['width'] - 2 * dimensions['padding']
        available_height = dimensions['height'] - 2 * dimensions['padding']

        return {
            'block_spacing': block_spacing,
            'unit_spacing': unit_spacing,
            'brace_padding': brace_padding,
            'available_width': available_width,
            'available_height': available_height,
            'complexity_score': complexity_score
        }

    def _position_blocks(self, units: List[BlockUnit], spacing_config: Dict, dimensions: Dict) -> List[BlockUnit]:
        """Position blocks using fixed column layout to prevent horizontal crashes"""
        if not units:
            return units

        # Step 1: Calculate unit dimensions
        for unit in units:
            self._calculate_unit_dimensions(unit, spacing_config)
        # Step 2: Define column layout with fixed brace columns and flexible node columns
        canvas_width = dimensions['width']
        padding = dimensions['padding']

        # Gaps around braces - increased to prevent overlap with nodes
        gap_topic_to_main_brace = 24.0  # Increased to prevent brace overlap with topic
        gap_main_brace_to_part = 28.0   # Increased to prevent brace overlap with parts
        gap_part_to_small_brace = 22.0  # Increased to prevent small brace overlap with parts
        gap_small_brace_to_subpart = 22.0  # Increased to prevent small brace overlap with subparts

        # Compute max widths of topic, part and subpart blocks to avoid overlap
        max_part_block_width = max((unit.part_block.width for unit in units), default=100.0)
        max_subpart_block_width = 100.0
        max_topic_block_width = 100.0
        for unit in units:
            # topic width approximated as the longest of part/subpart widths if not directly available yet
            if unit.part_block and unit.part_block.width > max_topic_block_width:
                max_topic_block_width = unit.part_block.width
            if unit.subpart_blocks:
                for sb in unit.subpart_blocks:
                    max_subpart_block_width = max(max_subpart_block_width, sb.width)
                    max_topic_block_width = max(max_topic_block_width, sb.width)

        # Column 1: Topic center (moved further left for brace space).
        # Approximate topic width from part widths if unavailable.
        approx_topic_width = max(60.0, max_topic_block_width)
        topic_column_x = padding + approx_topic_width / 2.0 - 12.0  # Reduced from 20px for tighter horizontal spacing

        # Estimate curly brace corridor widths (adaptive, conservative so parts never overlap brace)
        estimated_main_depth = min(max(24.0, canvas_width * 0.08), 100.0)
        estimated_small_depth = min(max(18.0, canvas_width * 0.06), 80.0)

        # Column 3: Parts center depends on estimated brace depth + gap + half of max part width (minimized)
        part_column_x = (
            topic_column_x + approx_topic_width / 2.0 + gap_topic_to_main_brace +
            estimated_main_depth + gap_main_brace_to_part + 6.0 +
            max_part_block_width / 2.0  # Reduced from 12px to move parts closer to brace
        )

        # Column 4: Small brace X (use estimated small depth/2 past part-right + gap)
        _small_brace_x = (
            part_column_x + max_part_block_width / 2.0 + gap_part_to_small_brace + estimated_small_depth / 2.0
        )

        # Column 5: Subparts center depends on estimated small brace depth + gap + half of max subpart width
        subpart_column_x = (
            part_column_x + max_part_block_width / 2.0 + gap_part_to_small_brace +
            estimated_small_depth + gap_small_brace_to_subpart +
            max_subpart_block_width / 2.0
        )

        # Step 3: Position units vertically with proper column separation
        current_y = dimensions['padding']

        for _i, unit in enumerate(units):
            # Position unit at current_y
            unit.y = current_y

            # Position part block at computed parts column center
            unit.part_block.x = part_column_x

            # Calculate subparts range center for part positioning
            if unit.subpart_blocks:
                # Calculate the vertical range of subparts for this part
                subparts_start_y = unit.y + unit.part_block.height + 12  # Reduced from 20
                subparts_end_y = (
                    subparts_start_y +
                    (len(unit.subpart_blocks) * unit.subpart_blocks[0].height) +
                    ((len(unit.subpart_blocks) - 1) * 7) - 7
                )  # Reduced from 10 for tighter spacing
                subparts_range_center_y = (subparts_start_y + subparts_end_y) / 2

                # Position part at subparts range center
                unit.part_block.y = subparts_range_center_y - unit.part_block.height / 2
            else:
                # No subparts: center vertically in unit
                unit.part_block.y = unit.y + (unit.height - unit.part_block.height) / 2

            # Position subpart blocks in right column (Column 3)
            if unit.subpart_blocks:
                # Calculate total subpart height for centering
                total_subpart_height = len(unit.subpart_blocks) * unit.subpart_blocks[0].height
                total_spacing = (len(unit.subpart_blocks) - 1) * spacing_config['block_spacing']
                total_height = total_subpart_height + total_spacing

                # Start position to center subparts within unit
                start_y = unit.y + (unit.height - total_height) / 2

                for j, subpart_block in enumerate(unit.subpart_blocks):
                    subpart_block.x = subpart_column_x
                    subpart_block.y = start_y + j * (subpart_block.height + spacing_config['block_spacing'])

            # Update current_y for next unit
            current_y = unit.y + unit.height + spacing_config['unit_spacing']

        return units

    def _calculate_unit_dimensions(self, unit: BlockUnit, spacing_config: Dict) -> None:
        """Calculate unit dimensions based on its blocks with standard heights"""
        if not unit.subpart_blocks:
            # Unit with only part block
            unit.width = unit.part_block.width + spacing_config['brace_padding']
            unit.height = unit.part_block.height  # Standard part height
        else:
            # Unit with part and subpart blocks
            # Calculate width: part width + spacing + max subpart width
            max_subpart_width = max(block.width for block in unit.subpart_blocks)
            unit.width = (unit.part_block.width + spacing_config['block_spacing'] +
                         max_subpart_width + spacing_config['brace_padding'])

            # Calculate height: total height of all subpart blocks + spacing
            # All subpart blocks have the same height, so just multiply by count
            subpart_height = unit.subpart_blocks[0].height  # Standard subpart height
            total_subpart_height = len(unit.subpart_blocks) * subpart_height
            total_spacing = (len(unit.subpart_blocks) - 1) * spacing_config['block_spacing']
            unit.height = max(unit.part_block.height, total_subpart_height + total_spacing)

    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate text width based on font size and character count"""
        char_widths = {
            'i': 0.3, 'l': 0.3, 'I': 0.4, 'f': 0.4, 't': 0.4, 'r': 0.4,
            'm': 0.8, 'w': 0.8, 'M': 0.8, 'W': 0.8,
            'default': 0.6
        }

        total_width = 0
        for char in text:
            char_width = char_widths.get(char, char_widths['default'])
            total_width += char_width * font_size

        return total_width


class FlexibleLayoutCalculator:
    """Implements the flexible dynamic layout algorithm"""

    def __init__(self):
        self._text_width_cache = {}

    def calculate_text_dimensions(self, spec: Dict, theme: Dict) -> Dict[str, Any]:
        """Calculate text dimensions for all nodes"""
        dimensions = {
            'topic': {'width': 0, 'height': 0},
            'parts': [],
            'subparts': []
        }

        # Calculate topic dimensions
        whole = spec.get('whole', 'Main Topic')
        topic_width = self._calculate_text_width(whole, theme['fontTopic'])
        topic_height = theme['fontTopic'] + 20
        dimensions['topic'] = {'width': topic_width, 'height': topic_height}

        # Calculate part dimensions
        for part in spec.get('parts', []):
            part_width = self._calculate_text_width(part['name'], theme['fontPart'])
            part_height = theme['fontPart'] + 20
            dimensions['parts'].append({'width': part_width, 'height': part_height})

        # Calculate subpart dimensions
        for part in spec.get('parts', []):
            part_subparts = []
            for subpart in part.get('subparts', []):
                subpart_width = self._calculate_text_width(subpart['name'], theme['fontSubpart'])
                subpart_height = theme['fontSubpart'] + 20
                part_subparts.append({'width': subpart_width, 'height': subpart_height})
            dimensions['subparts'].append(part_subparts)

        return dimensions

    def calculate_density(self, total_parts: int, subparts_per_part: List[int]) -> float:
        """Calculate content density for dynamic spacing"""
        total_elements = total_parts + sum(subparts_per_part)
        estimated_canvas_area = 800 * 600  # Default canvas size
        return total_elements / estimated_canvas_area

    def calculate_unit_spacing(self, units: List[Union[Dict, UnitPosition]]) -> float:
        """Calculate dynamic unit spacing based on content analysis"""
        total_units = len(units)
        if total_units <= 1:
            return 18.0  # Reduced minimum spacing from 30.0 for tighter layout

        # Analyze content complexity dynamically
        total_subparts = 0
        avg_unit_height = 0
        max_unit_height = 0

        for unit in units:
            if isinstance(unit, UnitPosition):
                height = unit.height
                subpart_count = len(unit.subpart_positions)
            elif isinstance(unit, dict):
                height = unit.get('height', 100.0)
                subpart_count = unit.get('subpart_count', 0)
            else:
                height = 100.0
                subpart_count = 0

            total_subparts += subpart_count
            avg_unit_height += height
            max_unit_height = max(max_unit_height, height)

        if units:
            avg_unit_height /= len(units)

        # Dynamic spacing factors based on content analysis
        content_density = (total_units + total_subparts) / max(1, total_units)
        height_factor = max_unit_height / 100.0  # Normalize to 100px baseline
        complexity_factor = min(2.5, content_density * height_factor)

        # Base spacing that scales with content complexity - reduced for tighter layout
        base_spacing = 18.0 * complexity_factor  # Reduced from 30.0

        # Additional spacing for complex diagrams - reduced for tighter layout
        if total_units > 3:
            base_spacing += 6.0 * (total_units - 3)  # Reduced from 10.0
        if total_subparts > total_units * 2:
            base_spacing += 9.0  # Reduced from 15.0 - Extra spacing for parts with many subparts

        return max(18.0, base_spacing)  # Reduced minimum spacing from 30.0

    def calculate_subpart_spacing(self, subparts: List[Dict]) -> float:
        """Calculate dynamic subpart spacing"""
        total_subparts = len(subparts)
        if total_subparts <= 1:
            return 12.0  # Reduced from 20.0 for tighter spacing

        # Dynamic spacing based on subpart count and content complexity - reduced for tighter layout
        base_spacing = 10.0  # Reduced from 15.0
        density_factor = min(1.5, total_subparts / 2.0)

        # Adjust based on text length (longer text needs more space)
        if subparts:
            avg_text_length = sum(len(subpart.get('name', '')) for subpart in subparts) / len(subparts)
            text_factor = min(1.3, avg_text_length / 20.0)
            return base_spacing * density_factor * text_factor

        return base_spacing * density_factor

    def calculate_main_topic_position(self, units: List[UnitPosition], dimensions: Dict) -> Tuple[float, float]:
        """Calculate main topic position (center-left of entire unit group)"""
        if not units:
            return (dimensions['padding'] + 50, dimensions['height'] / 2)

        # Sort units by Y position to ensure proper ordering
        sorted_units = sorted(units, key=lambda u: u.y)

        # Calculate the center of all units
        first_unit_y = sorted_units[0].y
        last_unit_y = sorted_units[-1].y + sorted_units[-1].height
        center_y = (first_unit_y + last_unit_y) / 2

        # Find the leftmost part position to avoid overlap
        leftmost_part_x = min(unit.part_position.x for unit in units)

        # Position topic to the left of all parts with proper spacing
        # Further reduced for tighter horizontal layout
        # Ensure topic is positioned at least 170px to the left of the leftmost part
        topic_x = max(
            dimensions['padding'] + 15,
            leftmost_part_x - 170
        )  # Further reduced from 220px for tighter horizontal spacing
        topic_y = center_y

        return (topic_x, topic_y)

    def calculate_unit_positions(self, spec: Dict, dimensions: Dict, theme: Dict) -> List[UnitPosition]:
        """Calculate positions for all units (part + subparts) using global grid alignment"""
        units = []
        parts = spec.get('parts', [])

        # Start with padding to account for canvas boundaries
        current_y = dimensions['padding']

        # Calculate dynamic positioning based on content structure
        total_subparts = sum(len(part.get('subparts', [])) for part in parts)

        # Analyze content for dynamic positioning
        _max_topic_width = self._calculate_text_width(
            spec.get('whole', 'Main Topic'), theme['fontTopic'])
        max_subpart_width = 0
        if total_subparts > 0:
            for part in parts:
                for subpart in part.get('subparts', []):
                    width = self._calculate_text_width(subpart['name'], theme['fontSubpart'])
                    max_subpart_width = max(max_subpart_width, width)

        # Dynamic horizontal positioning based on content analysis
        _canvas_width = dimensions['width']
        available_width = _canvas_width - 2 * dimensions['padding']

        # Calculate optimal spacing based on content
        part_offset = max(80, min(160, available_width * 0.2))
        subpart_offset = max(60, min(120, available_width * 0.16))

        # Calculate global grid positions for all subparts across all parts
        all_subparts = []
        for i, part in enumerate(parts):
            subparts = part.get('subparts', [])
            for j, subpart in enumerate(subparts):
                all_subparts.append({
                    'part_index': i,
                    'subpart_index': j,
                    'name': subpart['name'],
                    'height': theme['fontSubpart'] + 20
                })

        # Calculate global grid spacing
        # Calculate single global X position for ALL subparts (perfect vertical line)
        global_subpart_x = dimensions['padding'] + part_offset + subpart_offset

        if all_subparts:
            subpart_spacing = self.calculate_subpart_spacing([{'name': 'dummy'} for _ in range(len(all_subparts))])

            # Calculate global grid positions
            grid_positions = {}
            grid_y = current_y
            for subpart_info in all_subparts:
                grid_positions[(subpart_info['part_index'], subpart_info['subpart_index'])] = grid_y
                grid_y += subpart_info['height'] + subpart_spacing
        else:
            # No subparts case
            subpart_spacing = 20.0
            grid_positions = {}

        # Now position each unit using the global grid
        for i, part in enumerate(parts):
            subparts = part.get('subparts', [])

            if subparts:
                # Find the grid positions for this part's subparts
                part_subpart_positions = []
                for j, subpart in enumerate(subparts):
                    grid_y = grid_positions.get((i, j), current_y)
                    part_subpart_positions.append(grid_y)

                # Calculate part position (center of its subpart grid span)
                if part_subpart_positions:
                    first_j = 0
                    last_j = len(subparts) - 1
                    first_center = grid_positions[(i, first_j)] + (theme['fontSubpart'] + 20) / 2
                    last_center = grid_positions[(i, last_j)] + (theme['fontSubpart'] + 20) / 2
                    part_center_y = (first_center + last_center) / 2
                else:
                    part_center_y = current_y

                # Position part at center-left of its subpart grid span
                part_x = dimensions['padding'] + part_offset
                part_y = part_center_y - (theme['fontPart'] + 20) / 2

                # Create part node
                part_node = NodePosition(
                    x=part_x, y=part_y,
                    width=self._calculate_text_width(part['name'], theme['fontPart']),
                    height=theme['fontPart'] + 20,
                    text=part['name'], node_type='part', part_index=i
                )

                # Calculate subpart positions using global grid (all subparts in one vertical line)
                subpart_positions = []
                for j, subpart in enumerate(subparts):
                    subpart_x = global_subpart_x  # All subparts use the same X position
                    subpart_y = grid_positions[(i, j)]

                    subpart_node = NodePosition(
                        x=subpart_x, y=subpart_y,
                        width=self._calculate_text_width(subpart['name'], theme['fontSubpart']),
                        height=theme['fontSubpart'] + 20,
                        text=subpart['name'], node_type='subpart',
                        part_index=i, subpart_index=j
                    )
                    subpart_positions.append(subpart_node)

                # Create unit with dynamic width and height based on grid span
                if part_subpart_positions:
                    first_j = 0
                    last_j = len(subparts) - 1
                    first_top = grid_positions[(i, first_j)]
                    last_bottom = grid_positions[(i, last_j)] + (theme['fontSubpart'] + 20)
                    unit_height = last_bottom - first_top
                    unit_y = first_top
                else:
                    unit_height = part_node.height
                    unit_y = current_y

                # Calculate unit spacing - pass all units for better context
                temp_units = []
                for k in range(i + 1):
                    if k < len(units):
                        temp_units.append(units[k])
                    else:
                        temp_units.append({'height': unit_height})
                unit_spacing = self.calculate_unit_spacing(temp_units)

                # Calculate next_y with overlap prevention
                if part_subpart_positions:
                    next_y = last_bottom + unit_spacing
                else:
                    next_y = current_y + unit_height + unit_spacing

                # Define min_spacing for overlap prevention (used in multiple blocks)
                min_spacing = 18.0  # Reduced from 30.0 for tighter spacing between units

                # Ensure no overlap with previous units
                if i > 0 and units:
                    # Check against all previous units, not just the last one
                    max_prev_bottom = 0
                    for prev_unit in units:
                        prev_bottom = prev_unit.y + prev_unit.height
                        max_prev_bottom = max(max_prev_bottom, prev_bottom)

                    if unit_y < max_prev_bottom + min_spacing:
                        # Adjust current unit position to prevent overlap
                        unit_y = max_prev_bottom + min_spacing
                        # Update subpart positions to match new unit position
                        if part_subpart_positions:
                            # Recalculate subpart positions based on new unit_y
                            subpart_positions = []
                            for j, subpart in enumerate(subparts):
                                subpart_x = global_subpart_x
                                subpart_y = (
                                    unit_y + j * (theme['fontSubpart'] + 20 + subpart_spacing)
                                )  # subpart_spacing already reduced

                                subpart_node = NodePosition(
                                    x=subpart_x, y=subpart_y,
                                    width=self._calculate_text_width(
                                        subpart['name'], theme['fontSubpart']
                                    ),
                                    height=theme['fontSubpart'] + 20,
                                    text=subpart['name'], node_type='subpart',
                                    part_index=i, subpart_index=j
                                )
                                subpart_positions.append(subpart_node)

                            # Recalculate part position to maintain centering
                            if subpart_positions:
                                first_center = subpart_positions[0].y + (theme['fontSubpart'] + 20) / 2
                                last_center = subpart_positions[-1].y + (theme['fontSubpart'] + 20) / 2
                                part_center_y = (first_center + last_center) / 2
                                part_y = part_center_y - (theme['fontPart'] + 20) / 2
                                part_node = NodePosition(
                                    x=part_x, y=part_y,
                                    width=self._calculate_text_width(
                                        part['name'], theme['fontPart']
                                    ),
                                    height=theme['fontPart'] + 20,
                                    text=part['name'], node_type='part', part_index=i
                                )

                unit_width = max(400, part_node.width + subpart_offset + 50)  # Dynamic width
                unit = UnitPosition(
                    unit_index=i,
                    x=part_x, y=unit_y,
                    width=unit_width,
                    height=unit_height,
                    part_position=part_node,
                    subpart_positions=subpart_positions
                )

                # Final overlap check and adjustment using actual subpart bounds
                if i > 0 and units and subpart_positions:
                    # Calculate actual unit bounds based on subpart positions
                    subpart_ys = [s.y for s in subpart_positions]
                    actual_unit_min_y = min(subpart_ys)

                    for prev_unit in units:
                        prev_bottom = prev_unit.y + prev_unit.height
                        # Check for actual overlap: if current unit starts before previous unit ends + spacing
                        if actual_unit_min_y < prev_bottom + min_spacing:
                            # Force adjust the unit position
                            adjustment_needed = prev_bottom + min_spacing - actual_unit_min_y
                            unit.y += adjustment_needed
                            # Update all subpart positions
                            for subpart in subpart_positions:
                                subpart.y += adjustment_needed
                            # Update part position to maintain centering
                            if subpart_positions:
                                first_center = subpart_positions[0].y + (theme['fontSubpart'] + 20) / 2
                                last_center = subpart_positions[-1].y + (theme['fontSubpart'] + 20) / 2
                                part_center_y = (first_center + last_center) / 2
                                unit.part_position.y = part_center_y - (theme['fontPart'] + 20) / 2

                units.append(unit)

                # Update current_y for next iteration
                current_y = next_y
            else:
                # Part without subparts - dynamic positioning
                part_x = dimensions['padding'] + part_offset
                part_y = current_y + (theme['fontPart'] + 20) / 2  # Center the part

                part_node = NodePosition(
                    x=part_x, y=part_y,
                    width=self._calculate_text_width(part['name'], theme['fontPart']),
                    height=theme['fontPart'] + 20,
                    text=part['name'], node_type='part', part_index=i
                )

                # Dynamic height for unit without subparts
                unit_height = max(60, theme['fontPart'] + 40)  # Based on font size
                unit_width = max(200, part_node.width + 50)  # Dynamic width
                unit = UnitPosition(
                    unit_index=i,
                    x=part_x, y=current_y,
                    width=unit_width,
                    height=unit_height,
                    part_position=part_node,
                    subpart_positions=[]
                )
                units.append(unit)

                # Calculate unit spacing for next iteration - pass all units for better context
                temp_units = []
                for k in range(i + 1):
                    if k < len(units):
                        temp_units.append(units[k])
                    else:
                        # Estimate for remaining units
                        temp_units.append({'height': unit_height})
                unit_spacing = self.calculate_unit_spacing(temp_units)
                current_y += unit_height + unit_spacing

        return units

    def calculate_spacing_info(self, units: List[UnitPosition]) -> SpacingInfo:
        """Calculate dynamic spacing information"""
        total_units = len(units)
        total_subparts = sum(len(unit.subpart_positions) for unit in units)

        # Calculate unit spacing based on actual unit heights
        unit_heights = [unit.height for unit in units]
        unit_spacing = self.calculate_unit_spacing([{'height': height} for height in unit_heights])

        # Calculate subpart spacing based on actual subpart counts
        subpart_spacing = 20.0  # Default
        if total_subparts > 0:
            # Use the first unit with subparts to calculate spacing
            for unit in units:
                if unit.subpart_positions:
                    subpart_spacing = self.calculate_subpart_spacing(
                        [{'name': 'dummy'} for _ in unit.subpart_positions]
                    )
                    break

        brace_offset = 50.0  # Distance from nodes to brace
        content_density = (total_units + total_subparts) / 1000.0  # Normalized density

        return SpacingInfo(
            unit_spacing=unit_spacing,
            subpart_spacing=subpart_spacing,
            brace_offset=brace_offset,
            content_density=content_density
        )

    def _calculate_text_width(self, text: str, font_size: int) -> float:
        """Calculate text width based on font size and character count with caching"""
        if not text or font_size <= 0:
            return 0

        # Simple caching - could be enhanced with proper cache decorator
        cache_key = f"{text}_{font_size}"
        if cache_key in self._text_width_cache:
            return self._text_width_cache[cache_key]

        total_width = 0
        for char in text:
            char_width = CHAR_WIDTH_CONFIG.get(char, CHAR_WIDTH_CONFIG['default'])
            total_width += char_width * font_size

        # Cache the result
        self._text_width_cache[cache_key] = total_width

        return total_width

    def _get_font_weight(self, node_type: str) -> str:
        """Get font weight for node type using configuration"""
        return FONT_WEIGHT_CONFIG.get(node_type, 'normal')
