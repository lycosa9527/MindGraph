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
    console.error('MindGraphUtils not found. Please load shared-utilities.js first.');
}

// Note: getTextRadius and addWatermark are available globally from shared-utilities.js

function renderMindMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.children)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for mindmap');
        return;
    }
    
    // Determine canvas dimensions
    let baseWidth, baseHeight, padding;
    
    if (spec._recommended_dimensions) {
        // Python agent dimensions
        baseWidth = spec._recommended_dimensions.width;
        baseHeight = spec._recommended_dimensions.height;
        padding = spec._recommended_dimensions.padding;
    } else if (dimensions) {
        // Provided dimensions
        baseWidth = dimensions.baseWidth || 700;
        baseHeight = dimensions.baseHeight || 500;
        padding = dimensions.padding || 40;
    } else {
        // Default dimensions
        baseWidth = 700;
        baseHeight = 500;
        padding = 40;
    }
    
    // Load theme
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('mindmap', theme, theme);
            console.log('=== MIND MAP THEME DEBUG ===');
            console.log('Mind Map Theme loaded from styleManager:', THEME);
            console.log('Theme properties:');
            console.log('- background:', THEME.background);
            console.log('- centralTopicFill:', THEME.centralTopicFill);
            console.log('- centralTopicText:', THEME.centralTopicText);
            console.log('- centralTopicStroke:', THEME.centralTopicStroke);
            console.log('- branchFill:', THEME.branchFill);
            console.log('- childFill:', THEME.childFill);
            console.log('- childText:', THEME.childText);
            console.log('- childStroke:', THEME.childStroke);
            console.log('=== END THEME DEBUG ===');

        } else {
            console.warn('Style manager not available, using fallback theme');
            THEME = {
                background: '#f5f5f5',
                centralTopicFill: '#1976d2',
                centralTopicText: '#ffffff',
                centralTopicStroke: '#000000',
                centralTopicStrokeWidth: 3,
                branchFill: '#1976d2',
                branchText: '#ffffff',
                branchStroke: '#000000',
                branchStrokeWidth: 2,
                childFill: '#e3f2fd',
                childText: '#333333',
                childStroke: '#1976d2',
                childStrokeWidth: 2,
                fontTopic: 20,
                fontBranch: 16,
                fontChild: 14
            };
            console.log('=== MIND MAP FALLBACK THEME DEBUG ===');
            console.log('Mind Map Fallback theme applied:', THEME);
            console.log('=== END FALLBACK THEME DEBUG ===');
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        THEME = {
            background: '#f5f5f5',
            centralTopicFill: '#1976d2',
            centralTopicText: '#ffffff',
            centralTopicStroke: '#000000',
            centralTopicStrokeWidth: 3,
            branchFill: '#1976d2',
            branchText: '#ffffff',
            branchStroke: '#000000',
            branchStrokeWidth: 2,
            childFill: '#e3f2fd',
            childText: '#333333',
            childStroke: '#1976d2',
            childStrokeWidth: 2,
            fontTopic: 20,
            fontBranch: 16,
            fontChild: 14
        };
        console.log('=== MIND MAP EMERGENCY THEME DEBUG ===');
        console.log('Emergency fallback theme applied:', THEME);
        console.log('=== END EMERGENCY THEME DEBUG ===');
    }
    
    // Apply container background - use THEME object that was loaded above
    const containerBackground = spec._layout?.params?.background || THEME?.background || '#f5f5f5';
    
    console.log('=== BACKGROUND DEBUG ===');
    console.log('- spec._layout?.params?.background:', spec._layout?.params?.background);
    console.log('- THEME?.background:', THEME?.background);
    console.log('- Final containerBackground:', containerBackground);
    console.log('=== END BACKGROUND DEBUG ===');
    
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
        .style('background-color', containerBackground, 'important'); // Use the same background color
    
    // Require Python agent layout data
    const centerX = width / 2;
    const centerY = height / 2;
    
    if (spec._layout && spec._layout.positions) {
        // Render with positioned layout
        renderMindMapWithLayout(spec._layout, svg, centerX, centerY, THEME);
    } else {
        // Error: No layout data
        d3.select('#d3-container').append('div')
            .style('color', 'red')
            .style('font-size', '18px')
            .style('text-align', 'center')
            .style('padding', '50px')
            .text('Error: Python MindMapAgent failed to provide layout data. No fallback rendering available.');
        console.error('Mindmap rendering failed: No layout data from Python agent');
        return;
    }
    
    // Add watermark in lower right corner - matching original d3-renderers.js
    const watermarkText = 'MindGraph';
    
    // Get SVG dimensions
    const w = +svg.attr('width');
    const h = +svg.attr('height');
    
    // Check if SVG uses viewBox
    const viewBox = svg.attr('viewBox');
    let watermarkX, watermarkY, watermarkFontSize;
    
    if (viewBox) {
        // SVG uses viewBox - position within viewBox coordinate system
        const viewBoxParts = viewBox.split(' ').map(Number);
        const viewBoxWidth = viewBoxParts[2];
        const viewBoxHeight = viewBoxParts[3];
        
        // Calculate font size based on viewBox dimensions
        watermarkFontSize = Math.max(8, Math.min(16, Math.min(viewBoxWidth, viewBoxHeight) * 0.02));
        
        // Calculate padding based on viewBox size
        const padding = Math.max(5, Math.min(15, Math.min(viewBoxWidth, viewBoxHeight) * 0.01));
        
        // Position in lower right corner of viewBox
        watermarkX = viewBoxParts[0] + viewBoxWidth - padding;
        watermarkY = viewBoxParts[1] + viewBoxHeight - padding;
    } else {
        // SVG uses standard coordinate system
        watermarkFontSize = Math.max(12, Math.min(20, Math.min(w, h) * 0.025));
        const padding = Math.max(10, Math.min(20, Math.min(w, h) * 0.02));
        watermarkX = w - padding;
        watermarkY = h - padding;
    }
    
    // Add watermark with proper styling
    svg.append('text')
        .attr('x', watermarkX)
        .attr('y', watermarkY)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'alphabetic')
        .attr('fill', '#2c3e50')  // Original dark blue-grey color
        .attr('font-size', watermarkFontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('font-weight', '500')
        .attr('opacity', 0.8)     // Original 80% opacity
        .attr('pointer-events', 'none')
        .text(watermarkText);
}

function renderMindMapWithLayout(spec, svg, centerX, centerY, THEME) {
    const positions = spec.positions;
    const connections = spec.connections || [];
    
    // Begin rendering
    // Rendering mindmap with calculated nodes and connections
    
    // Draw connections first
    if (connections.length > 0) {
        // Explicit connections
        connections.forEach(conn => {
            let fromPos, toPos;
            
            // Handle topic connections
            if (conn.from.type === 'topic') {
                fromPos = positions['topic'];
            } else if (conn.from.type === 'branch') {
                fromPos = positions[`branch_${conn.branch_index}`];
            }
            
            // Handle branch and child connections
            if (conn.to.type === 'branch') {
                toPos = positions[`branch_${conn.branch_index}`];
            } else if (conn.to.type === 'child') {
                // For child connections, we need both branch_index and child_index
                if (conn.child_index !== undefined) {
                    toPos = positions[`child_${conn.branch_index}_${conn.child_index}`];
                }
            }
            
            if (fromPos && toPos) {
                const fromX = centerX + fromPos.x;
                const fromY = centerY + fromPos.y;

                const fromWidth = fromPos.width || (fromPos.text ? Math.max(80, fromPos.text.length * 8) : 100);
                const fromHeight = fromPos.height || 50;
                
                const toX = centerX + toPos.x;
                const toY = centerY + toPos.y;
                const toWidth = toPos.width || (toPos.text ? Math.max(80, toPos.text.length * 8) : 100);
                const toHeight = toPos.height || 40;
                
                // Calculate line endpoints to stop at node boundaries
                const dx = toX - fromX;
                const dy = toY - fromY;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist > 0) {
                    // Calculate connection points for explicit connections using left/right border centers
                    let lineStartX, lineStartY, lineEndX, lineEndY;
                    
                    // Handle FROM node connection point
                    if (fromPos.node_type === 'topic') {
                        // Topic is a circle - connect from center point
                        lineStartX = fromX;  // Always connect from center of topic
                        lineStartY = fromY;
                    } else if (fromPos.node_type === 'branch') {
                        // Branch node - connect from CENTER POINT
                        lineStartX = fromX;  // Center X
                        lineStartY = fromY;  // Center Y
                    } else {
                        // Child is a rectangle - connect at left/right edge center
                        if (toX > fromX) {
                            // Connect from right edge
                            lineStartX = fromX + (fromWidth / 2);
                            lineStartY = fromY;
                        } else {
                            // Connect from left edge
                            lineStartX = fromX - (fromWidth / 2);
                            lineStartY = fromY;
                        }
                    }
                    
                    // Handle TO node connection point
                    if (toPos.node_type === 'topic') {
                        // Topic is a circle - connect to center point
                        lineEndX = toX;  // Always connect to center of topic
                        lineEndY = toY;
                    } else if (toPos.node_type === 'branch') {
                        // Branch node - connect to CENTER POINT
                        lineEndX = toX;  // Center X
                        lineEndY = toY;  // Center Y
                    } else {
                        // Child is a rectangle - connect at left/right edge center
                        if (fromX > toX) {
                            // Connect to right edge
                            lineEndX = toX + (toWidth / 2);
                            lineEndY = toY;
                        } else {
                            // Connect to left edge
                            lineEndX = toX - (toWidth / 2);
                            lineEndY = toY;
                        }
                    }
                    
                    svg.append('line')
                        .attr('x1', lineStartX)
                        .attr('y1', lineStartY)
                        .attr('x2', lineEndX)
                        .attr('y2', lineEndY)
                        .attr('stroke', conn.stroke_color || THEME.linkStroke || '#888')
                        .attr('stroke-width', conn.stroke_width || 2);
                }
            }
        });
    } else {
        // Infer connections from positions
        Object.keys(positions).forEach(key => {
            const pos = positions[key];
            
            if (pos.node_type === 'branch') {
                    // Draw connecting line from center to branch
                    const branchX = centerX + pos.x;
                    const branchY = centerY + pos.y;
    
                    const branchWidth = pos.width || (pos.text ? Math.max(100, pos.text.length * 10) : 100);
                    const branchHeight = pos.height || 50;
                    
                    const dx = branchX - centerX;
                    const dy = branchY - centerY;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    
                    if (dist > 0) {
                        // Calculate line endpoints for proper mind map connections
                        const topicPos = positions['topic'];
                        const topicRadius = topicPos ? getTextRadius(topicPos.text || 'Topic', THEME.fontCentral || '16px', 20) : 60;
                        
                        // Determine if branch is on left or right side
                        const branchIsOnLeft = branchX < centerX;
                        
                        // For topic (circle): connect from center point
                        let lineStartX, lineStartY;
                        lineStartX = centerX;  // Always connect from center of topic
                        lineStartY = centerY;
                        
                        // For branch (rectangle): connect to CENTER POINT of branch node  
                        let lineEndX, lineEndY;
                        // Always connect to branch center point (consistent with child-to-branch connections)
                        lineEndX = branchX;  // Center X
                        lineEndY = branchY;  // Center Y
                        
                        console.log('=== CONNECTION LINE DEBUG (topic to branch) ===');
                        console.log('- Topic center:', { x: centerX, y: centerY });
                        console.log('- Topic radius:', topicRadius);
                        console.log('- Branch center:', { x: branchX, y: branchY });
                        console.log('- Branch is on left:', branchIsOnLeft);
                        console.log('- Line start (topic CENTER):', { x: lineStartX, y: lineStartY });
                        console.log('- Line end (branch CENTER POINT):', { x: lineEndX, y: lineEndY });
                        console.log('=== END CONNECTION DEBUG ===');
                        
                        svg.append('line')
                            .attr('x1', lineStartX)
                            .attr('y1', lineStartY)
                            .attr('x2', lineEndX)
                            .attr('y2', lineEndY)
                            .attr('stroke', THEME.linkStroke || '#888')
                        .attr('stroke-width', 2);
                    }
                } else if (pos.node_type === 'child') {
                    // Draw connecting line from branch to child
                    const childX = centerX + pos.x;
                    const childY = centerY + pos.y;
    
                    const childWidth = pos.width || (pos.text ? Math.max(80, pos.text.length * 8) : 100);
                    const childHeight = pos.height || 40;
                    
                    const branchKey = `branch_${pos.branch_index}`;
                    if (positions[branchKey]) {
                        const branchPos = positions[branchKey];
                        const branchX = centerX + branchPos.x;
                        const branchY = centerY + branchPos.y;
        
                        const branchWidth = branchPos.width || (branchPos.text ? Math.max(100, branchPos.text.length * 10) : 100);
                        const branchHeight = branchPos.height || 50;
                        
                        // Calculate line endpoints to stop at node boundaries
                        const dx = childX - branchX;
                        const dy = childY - branchY;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        
                        if (dist > 0) {
                            // Determine if child is on left or right side of branch
                            const childIsOnLeft = childX < branchX;
                            
                            // For branch (rectangle): connect from CENTER POINT of branch node
                            let lineStartX, lineStartY;
                            // Always connect from branch center point (not border)
                            lineStartX = branchX;  // Center X
                            lineStartY = branchY;  // Center Y
                            
                            // For child (rectangle): connect at left/right edge center
                            let lineEndX, lineEndY;
                            if (childIsOnLeft) {
                                // Child is on left, connect to right edge of child
                                lineEndX = childX + (childWidth / 2);
                                lineEndY = childY;
                            } else {
                                // Child is on right, connect to left edge of child
                                lineEndX = childX - (childWidth / 2);
                                lineEndY = childY;
                            }
                            
                            console.log('=== CONNECTION LINE DEBUG (branch to child) ===');
                            console.log('- Branch center:', { x: branchX, y: branchY });
                            console.log('- Branch dimensions:', { width: branchWidth, height: branchHeight });
                            console.log('- Child center:', { x: childX, y: childY });
                            console.log('- Child is on left:', childIsOnLeft);
                            console.log('- Line start (branch CENTER POINT):', { x: lineStartX, y: lineStartY });
                            console.log('- Line end (child border center):', { x: lineEndX, y: lineEndY });
                            console.log('=== END CONNECTION DEBUG ===');
                            
        svg.append('line')
                                .attr('x1', lineStartX)
                                .attr('y1', lineStartY)
                                .attr('x2', lineEndX)
                                .attr('y2', lineEndY)
                                .attr('stroke', THEME.linkStroke || '#ccc')
            .attr('stroke-width', 1);
                        }
                    }
                }
            });
        }
        
        // Draw nodes on top
        Object.keys(positions).forEach(key => {
            const pos = positions[key];
            console.log(`=== NODE RENDERING DEBUG: ${key} ===`);
            console.log('Position data:', pos);
            console.log('Node type:', pos.node_type);

            
            if (pos.node_type === 'topic') {
                // Central topic (circle)
                const topicX = centerX + pos.x;
                const topicY = centerY + pos.y;
                const topicWidth = pos.width || 120;
                const topicHeight = pos.height || 60;
                // Calculate adaptive radius based on actual text dimensions using getTextRadius
                const topicRadius = getTextRadius(pos.text || 'Topic', THEME.fontCentral || '16px', 20);
                
                const finalFill = pos.fill || THEME.centralTopicFill || '#1976d2';
                const finalStroke = pos.stroke || THEME.centralTopicStroke || '#000000';
                const finalTextColor = pos.text_color || THEME.centralTopicText || '#ffffff';
                
                console.log('=== TOPIC NODE COLOR DEBUG ===');
                console.log('- Topic radius:', topicRadius);
                console.log('- Final fill color:', finalFill);
                console.log('- Final stroke color:', finalStroke);
                console.log('- Final text color:', finalTextColor);
                console.log('- pos.fill:', pos.fill);
                console.log('- THEME.centralTopicFill:', THEME.centralTopicFill);
                console.log('- THEME.centralNodeFill:', THEME.centralNodeFill);
                console.log('=== END TOPIC DEBUG ===');
                
    svg.append('circle')
                    .attr('cx', topicX)
                    .attr('cy', topicY)
                    .attr('r', topicRadius)
                    .attr('fill', finalFill)
                    .attr('stroke', finalStroke)
                    .attr('stroke-width', pos.stroke_width || 3);
    
    svg.append('text')
                    .attr('x', topicX)
                    .attr('y', topicY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
                    .attr('fill', finalTextColor)
                    .attr('font-size', THEME.fontCentral || '16px')
        .attr('font-weight', 'bold')
                    .text(pos.text || 'Topic');
                    
            } else if (pos.node_type === 'branch') {
                // Branch (rectangle)
                const branchX = centerX + pos.x;
                const branchY = centerY + pos.y;

                const branchWidth = pos.width || (pos.text ? Math.max(100, pos.text.length * 10) : 100);
                const branchHeight = pos.height || 50;
                
                const finalBranchFill = pos.fill || THEME.branchFill || '#1976d2';
                const finalBranchStroke = pos.stroke || THEME.branchStroke || '#000000';
                const finalBranchTextColor = pos.text_color || THEME.branchText || '#ffffff';
                
                console.log('=== BRANCH NODE COLOR DEBUG ===');
                console.log('- Branch position:', { x: branchX, y: branchY });
                console.log('- Branch dimensions:', { width: branchWidth, height: branchHeight });
                console.log('- Final fill color:', finalBranchFill);
                console.log('- Final stroke color:', finalBranchStroke);
                console.log('- Final text color:', finalBranchTextColor);
                console.log('- pos.fill:', pos.fill);
                console.log('- THEME.branchFill:', THEME.branchFill);
                console.log('=== END BRANCH DEBUG ===');
                
                // Draw rectangular node
                svg.append('rect')
                    .attr('x', branchX - branchWidth / 2)
                    .attr('y', branchY - branchHeight / 2)
                    .attr('width', branchWidth)
                    .attr('height', branchHeight)
                    .attr('rx', 8) // Rounded corners
                    .attr('ry', 8)
                    .attr('fill', finalBranchFill)
                    .attr('stroke', finalBranchStroke)
                    .attr('stroke-width', pos.stroke_width || THEME.branchStrokeWidth || 2);
    
    svg.append('text')
                    .attr('x', branchX)
                    .attr('y', branchY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
                    .attr('fill', finalBranchTextColor)
                    .attr('font-size', THEME.fontBranch || '16px')
                    .text(pos.text || 'Branch');
                    
            } else if (pos.node_type === 'child') {
                // Child (rectangle)
                const childX = centerX + pos.x;
                const childY = centerY + pos.y;

                const childWidth = pos.width || (pos.text ? Math.max(80, pos.text.length * 8) : 100);
                const childHeight = pos.height || 40;
                
                const finalChildFill = pos.fill || THEME.childFill || '#e3f2fd';
                const finalChildStroke = pos.stroke || THEME.childStroke || '#1976d2';
                const finalChildTextColor = pos.text_color || THEME.childText || '#333333';
                
                console.log('=== CHILD NODE COLOR DEBUG ===');
                console.log('- Child position:', { x: childX, y: childY });
                console.log('- Child dimensions:', { width: childWidth, height: childHeight });
                console.log('- Final fill color:', finalChildFill);
                console.log('- Final stroke color:', finalChildStroke);
                console.log('- Final text color:', finalChildTextColor);
                console.log('- pos.fill:', pos.fill);
                console.log('- THEME.childFill:', THEME.childFill);
                console.log('- THEME.childNodeFill:', THEME.childNodeFill);
                console.log('=== END CHILD DEBUG ===');
                
                // Draw rectangular node
                svg.append('rect')
                    .attr('x', childX - childWidth / 2)
                    .attr('y', childY - childHeight / 2)
                    .attr('width', childWidth)
                    .attr('height', childHeight)
                    .attr('rx', 6) // Rounded corners
                    .attr('ry', 6)
                    .attr('fill', finalChildFill)
                    .attr('stroke', finalChildStroke)
                    .attr('stroke-width', pos.stroke_width || 2);
                
        svg.append('text')
                    .attr('x', childX)
                    .attr('y', childY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
                    .attr('fill', finalChildTextColor)
                    .attr('font-size', THEME.fontChild || '14px')
                    .text(pos.text || 'Child');
            }
        });
        
    // Mindmap rendered successfully
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
