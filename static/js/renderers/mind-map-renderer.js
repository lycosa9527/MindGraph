/**
 * Mind Map Renderer for MindGraph
 * 
 * This module provides standard mind map rendering using Python agent layout data.
 * - Always requires positioned layout from Python MindMapAgent
 * - Shows error message if Python agent fails (no fallback rendering)
 * 
 * Requires: shared-utilities.js, style-manager.js
 * Performance Impact: Loads only ~50KB instead of full 213KB
 */

// Check if shared utilities are available
if (typeof window.MindGraphUtils === 'undefined') {
    logger.error('MindMapRenderer', 'MindGraphUtils not found. Please load shared-utilities.js first.');
}

// Note: getTextRadius and addWatermark are available globally from shared-utilities.js

function renderMindMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.children)) {
        logger.error('MindMapRenderer', 'Invalid spec for mindmap');
        return;
    }
    
    // Determine canvas dimensions - use adaptive dimensions if provided
    let baseWidth, baseHeight, padding;
    
    if (spec._recommended_dimensions) {
        // Adaptive dimensions from template (calculated based on window size)
        baseWidth = spec._recommended_dimensions.width;
        baseHeight = spec._recommended_dimensions.height;
        padding = spec._recommended_dimensions.padding;
        logger.info('MindMapRenderer', 'Using adaptive dimensions:', { baseWidth, baseHeight, padding });
    } else if (dimensions) {
        // Provided dimensions (fallback)
        baseWidth = dimensions.width || dimensions.baseWidth || 700;
        baseHeight = dimensions.height || dimensions.baseHeight || 500;
        padding = dimensions.padding || 40;
    } else {
        // Default dimensions
        baseWidth = 700;
        baseHeight = 500;
        padding = 40;
    }
    
    // Load theme from style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('mindmap', null, null);
        } else {
            throw new Error('Style manager not available for mindmap rendering');
        }
    } catch (error) {
        logger.error('MindMapRenderer', 'Failed to load theme:', error);
        throw new Error('Failed to load theme from style manager');
    }
    
    // Apply container background - use THEME object that was loaded above
    const containerBackground = spec._layout?.params?.background || THEME?.background || '#f5f5f5';
    
    d3.select('#d3-container')
        .style('background-color', containerBackground, 'important')
        .style('width', '100%')
        .style('height', '100%')
        .style('min-height', `${baseHeight}px`);
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet')
        .style('background-color', containerBackground, 'important');
    
    // Require Python agent layout data
    const centerX = width / 2;
    const centerY = height / 2;
    
    if (spec._layout && spec._layout.positions) {
        // Render with positioned layout
        renderMindMapWithLayout(spec._layout, svg, centerX, centerY, THEME);
    } else {
        // Error: No layout data
        logger.error('MindMapRenderer', 'Mindmap rendering failed: No layout data from Python agent');
        return;
    }
    
    // Watermark removed from canvas display - will be added during PNG export only
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

function renderMindMapWithLayout(spec, svg, centerX, centerY, THEME) {
    const positions = spec.positions;
    const connections = spec.connections || [];
    
    // Draw connections first (so they appear behind nodes)
    connections.forEach(conn => {
        // Handle the actual connection format from Python agent
        // Connections have from: {x, y, type} and to: {x, y, type} format
        if (conn.from && conn.to && typeof conn.from === 'object' && typeof conn.to === 'object') {
            // Skip connections related to "Additional Aspect" branch
            if (isAdditionalAspectConnection(conn, positions)) {
                return; // Skip rendering this connection
            }
            
            const fromX = centerX + conn.from.x;
            const fromY = centerY + conn.from.y;
            const toX = centerX + conn.to.x;
            const toY = centerY + conn.to.y;
            
            // Draw connection line
            svg.append('line')
                .attr('x1', fromX)
                .attr('y1', fromY)
                .attr('x2', toX)
                .attr('y2', toY)
                .attr('stroke', conn.stroke_color || THEME?.connectionColor || '#666')
                .attr('stroke-width', conn.stroke_width || THEME?.connectionWidth || 2)
                .attr('opacity', 0.7);
        }
    });
    
    // Draw nodes
    Object.values(positions).forEach(pos => {
        // Skip "Additional Aspect" branch and its children
        if (isAdditionalAspectNode(pos, positions)) {
            return; // Skip rendering this node
        }
        
        if (pos.node_type === 'topic') {
            // Central topic (circle)
            const topicX = centerX + pos.x;
            const topicY = centerY + pos.y;
            
            const topicWidth = pos.width || 120;
            const topicHeight = pos.height || 60;
            
            // Calculate adaptive radius based on actual text dimensions
            let topicRadius;
            if (typeof getTextRadius === 'function') {
                topicRadius = getTextRadius(pos.text || 'Topic', THEME.fontTopic || '16px', 20);
            } else if (typeof window.MindGraphUtils !== 'undefined' && window.MindGraphUtils.getTextRadius) {
                topicRadius = window.MindGraphUtils.getTextRadius(pos.text || 'Topic', THEME.fontTopic || '16px', 20);
            } else {
                // Fallback calculation
                topicRadius = Math.max(30, Math.min(60, (pos.text || 'Topic').length * 3));
            }
            
            const finalFill = pos.fill || THEME.centralTopicFill || '#e3f2fd';
            const finalStroke = pos.stroke || THEME.centralTopicStroke || '#35506b';
            const finalTextColor = pos.text_color || THEME.centralTopicText || '#333333';
            
            // Draw circular node
            svg.append('circle')
                .attr('cx', topicX)
                .attr('cy', topicY)
                .attr('r', topicRadius)
                .attr('fill', finalFill)
                .attr('stroke', finalStroke)
                .attr('stroke-width', pos.stroke_width || 3)
                .attr('opacity', 1)
                .attr('data-node-id', 'topic_center')
                .attr('data-node-type', 'topic');
            
            // Draw text
            svg.append('text')
                .attr('x', topicX)
                .attr('y', topicY)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', finalTextColor)
                .attr('font-size', THEME.fontTopic || '16px')
                .attr('font-weight', 'bold')
                .attr('data-text-for', 'topic_center')
                .attr('data-node-id', 'topic_center')
                .attr('data-node-type', 'topic')
                .text(pos.text || 'Topic');
                
        } else if (pos.node_type === 'branch') {
            // Branch (rectangle)
            const branchX = centerX + pos.x;
            const branchY = centerY + pos.y;

            const branchWidth = pos.width || (pos.text ? Math.max(100, pos.text.length * 10) : 100);
            const branchHeight = pos.height || 50;
            
            const finalBranchFill = pos.fill || THEME.branchFill || '#e3f2fd';
            const finalBranchStroke = pos.stroke || THEME.branchStroke || '#4e79a7';
            const finalBranchTextColor = pos.text_color || THEME.branchText || '#333333';
            
            // Generate node ID for branch
            const branchNodeId = `branch_${pos.branch_index}`;
            
            // Draw rectangular node
            svg.append('rect')
                .attr('x', branchX - branchWidth / 2)
                .attr('y', branchY - branchHeight / 2)
                .attr('width', branchWidth)
                .attr('height', branchHeight)
                .attr('rx', 8)
                .attr('ry', 8)
                .attr('fill', finalBranchFill)
                .attr('stroke', finalBranchStroke)
                .attr('stroke-width', pos.stroke_width || THEME.branchStrokeWidth || 2)
                .attr('opacity', 1)
                .attr('data-node-id', branchNodeId)
                .attr('data-node-type', 'branch')
                .attr('data-branch-index', pos.branch_index)
                .attr('data-array-index', pos.branch_index);
            
            // Draw text
            svg.append('text')
                .attr('x', branchX)
                .attr('y', branchY)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', finalBranchTextColor)
                .attr('font-size', THEME.fontBranch || '16px')
                .attr('data-text-for', branchNodeId)
                .attr('data-node-id', branchNodeId)
                .attr('data-node-type', 'branch')
                .text(pos.text || 'Branch');
                
        } else if (pos.node_type === 'child') {
            // Child (rectangle)
            const childX = centerX + pos.x;
            const childY = centerY + pos.y;

            const childWidth = pos.width || (pos.text ? Math.max(80, pos.text.length * 8) : 100);
            const childHeight = pos.height || 40;
            
            const finalChildFill = pos.fill || THEME.childFill || '#f8f9fa';
            const finalChildStroke = pos.stroke || THEME.childStroke || '#6c757d';
            const finalChildTextColor = pos.text_color || THEME.childText || '#333333';
            
            // Generate node ID for child
            const childNodeId = `child_${pos.branch_index}_${pos.child_index}`;
            
            // Draw rectangular node
            svg.append('rect')
                .attr('x', childX - childWidth / 2)
                .attr('y', childY - childHeight / 2)
                .attr('width', childWidth)
                .attr('height', childHeight)
                .attr('rx', 6)
                .attr('ry', 6)
                .attr('fill', finalChildFill)
                .attr('stroke', finalChildStroke)
                .attr('stroke-width', pos.stroke_width || 2)
                .attr('opacity', 1)
                .attr('data-node-id', childNodeId)
                .attr('data-node-type', 'child')
                .attr('data-branch-index', pos.branch_index)
                .attr('data-child-index', pos.child_index)
                .attr('data-array-index', pos.child_index);
            
            // Draw text
            svg.append('text')
                .attr('x', childX)
                .attr('y', childY)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', finalChildTextColor)
                .attr('font-size', THEME.fontChild || '14px')
                .attr('data-text-for', childNodeId)
                .attr('data-node-id', childNodeId)
                .attr('data-node-type', 'child')
                .text(pos.text || 'Child');
        }
    });
}

// Helper function to check if a node is part of the "Additional Aspect" branch
function isAdditionalAspectNode(pos, positions) {
    // Check if the node text contains "Additional Aspect"
    if (pos.text && pos.text.includes('Additional Aspect')) {
        return true;
    }
    
    // Check if it's a child of the Additional Aspect branch
    if (pos.node_type === 'child' && pos.branch_index !== undefined) {
        // Find the parent branch and check if it's Additional Aspect
        const branchKey = `branch_${pos.branch_index}`;
        const parentBranch = positions[branchKey];
        if (parentBranch && parentBranch.text && parentBranch.text.includes('Additional Aspect')) {
            return true;
        }
    }
    
    return false;
}

// Helper function to check if a connection involves the "Additional Aspect" branch
function isAdditionalAspectConnection(conn, positions) {
    // Find the node at the connection endpoints
    const tolerance = 0.1; // Small tolerance for coordinate comparison
    
    for (const [nodeId, nodePos] of Object.entries(positions)) {
        // Check if connection 'from' point matches this node's position
        if (Math.abs(conn.from.x - nodePos.x) < tolerance && Math.abs(conn.from.y - nodePos.y) < tolerance) {
            if (nodePos.text && nodePos.text.includes('Additional Aspect')) {
                return true;
            }
        }
        
        // Check if connection 'to' point matches this node's position
        if (Math.abs(conn.to.x - nodePos.x) < tolerance && Math.abs(conn.to.y - nodePos.y) < tolerance) {
            if (nodePos.text && nodePos.text.includes('Additional Aspect')) {
                return true;
            }
            
            // Also check if this is a child of Additional Aspect branch by checking its parent
            if (nodePos.node_type === 'child' && nodePos.branch_index !== undefined) {
                // Find the parent branch
                const branchKey = `branch_${nodePos.branch_index}`;
                const parentBranch = positions[branchKey];
                if (parentBranch && parentBranch.text && parentBranch.text.includes('Additional Aspect')) {
                    return true;
                }
            }
        }
    }
    
    return false;
}

// Export functions for module system
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.MindMapRenderer = {
        renderMindMap,
        renderMindMapWithLayout
    };
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderMindMap,
        renderMindMapWithLayout
    };
}
