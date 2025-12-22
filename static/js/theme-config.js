/**
 * Centralized Theme Configuration
 * All styling configurations for diagrams are defined here in one place.
 * This makes it easy to modify colors, fonts, borders, and sizes.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

const THEME_CONFIG = {
    // Bubble Map Configuration
    bubble_map: {
        // Background color for the entire canvas
        background: '#f5f5f5',        // Light grey background
        // Topic Node (Central Node)
        topic: {
            fill: '#1976d2',           // Deep blue background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 3,            // Border thickness
            fontSize: 20,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        },
        // Feature Nodes (Attribute Nodes)
        attribute: {
            fill: '#e3f2fd',          // Light blue background
            text: '#333333',           // Dark text for readability
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 14,              // Font size in pixels
            fontWeight: 'normal'       // Font weight
        }
    },

    // Double Bubble Map Configuration
    double_bubble_map: {
        // Central Topic Node
        centralTopic: {
            fill: '#1976d2',           // Deep blue background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 3,            // Border thickness
            fontSize: 18,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        },
        // Left Topic Node
        leftTopic: {
            fill: '#1976d2',           // Deep blue background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 16,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        },
        // Right Topic Node
        rightTopic: {
            fill: '#1976d2',           // Deep blue background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 16,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        },
        // Feature Nodes (Attributes)
        attribute: {
            fill: '#e3f2fd',          // Light blue background
            text: '#333333',           // Dark text for readability
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 12,              // Font size in pixels
            fontWeight: 'normal'       // Font weight
        }
    },

    // Tree Map Configuration
    tree_map: {
        root: {
            fill: '#1976d2',           // Deep blue background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 3,            // Border thickness
            fontSize: 20,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        },
        branch: {
            fill: '#e3f2fd',          // Light blue background
            text: '#333333',           // Dark text for readability
            stroke: '#1976d2',         // Blue border
            strokeWidth: 2,            // Border thickness
            fontSize: 16,              // Font size in pixels
            fontWeight: 'normal'       // Font weight
        },
        leaf: {
            fill: '#f8f9fa',          // Very light blue background
            text: '#333333',           // Dark text for readability
            stroke: '#1976d2',         // Blue border
            strokeWidth: 1,            // Border thickness
            fontSize: 14,              // Font size in pixels
            fontWeight: 'normal'       // Font weight
        }
    },



    // Flowchart Configuration
    flowchart: {
        start: {
            fill: '#4caf50',          // Green background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 14,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        },
        process: {
            fill: '#2196f3',          // Blue background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 14,              // Font size in pixels
            fontWeight: 'normal'       // Font weight
        },
        decision: {
            fill: '#ff9800',          // Orange background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 14,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        },
        end: {
            fill: '#f44336',          // Red background
            text: '#ffffff',           // White text for contrast
            stroke: '#000000',         // Black border
            strokeWidth: 2,            // Border thickness
            fontSize: 14,              // Font size in pixels
            fontWeight: 'bold'         // Font weight
        }
    }
};

/**
 * Get theme configuration for a specific diagram type
 * @param {string} diagramType - The type of diagram
 * @returns {object} Theme configuration object
 */
function getThemeConfig(diagramType) {
    return THEME_CONFIG[diagramType] || {};
}

/**
 * Convert theme config to D3-compatible format
 * @param {string} diagramType - The type of diagram
 * @returns {object} D3-compatible theme object
 */
function getD3Theme(diagramType) {
    const config = getThemeConfig(diagramType);
    const theme = {};
    
    // Handle top-level properties (like background)
    if (config.background) {
        theme.background = config.background;
    }
    
    // Convert nested config to flat D3 format
    Object.keys(config).forEach(category => {
        // Skip top-level properties (they're not categories)
        if (typeof config[category] !== 'object' || config[category] === null) {
            return;
        }
        
        const categoryConfig = config[category];
        Object.keys(categoryConfig).forEach(property => {
            const value = categoryConfig[property];
            
            // Convert property names to D3 format
            let d3Property;
            switch (property) {
                case 'fill':
                    d3Property = `${category}Fill`;
                    break;
                case 'text':
                    d3Property = `${category}Text`;
                    break;
                case 'stroke':
                    d3Property = `${category}Stroke`;
                    break;
                case 'strokeWidth':
                    d3Property = `${category}StrokeWidth`;
                    break;
                case 'fontSize':
                    // Convert fontSize to the correct D3 property names
                    if (category === 'topic') {
                        d3Property = 'fontTopic';
                    } else if (category === 'attribute') {
                        d3Property = 'fontAttribute';
                    } else {
                        d3Property = `font${category.charAt(0).toUpperCase() + category.slice(1)}`;
                    }
                    break;
                case 'fontWeight':
                    d3Property = `${category}FontWeight`;
                    break;
                default:
                    d3Property = `${category}${property.charAt(0).toUpperCase() + property.slice(1)}`;
            }
            
            // Special handling for double bubble map
            if (diagramType === 'double_bubble_map') {
                if (category === 'attribute') {
                    // Map attribute properties to both sim and diff properties
                    const simProperty = d3Property.replace('attribute', 'sim');
                    const diffProperty = d3Property.replace('attribute', 'diff');
                    theme[simProperty] = value;
                    theme[diffProperty] = value;
                } else if (category === 'centralTopic' || category === 'leftTopic' || category === 'rightTopic') {
                    // Map topic properties to the generic topicFill/topicStroke that the renderer expects
                    if (property === 'fill') {
                        theme.topicFill = value;
                    } else if (property === 'stroke') {
                        theme.topicStroke = value;
                    } else if (property === 'text') {
                        theme.topicText = value;
                    } else if (property === 'strokeWidth') {
                        theme.topicStrokeWidth = value;
                    } else if (property === 'fontSize') {
                        theme.fontTopic = value;
                    }
                } else {
                    theme[d3Property] = value;
                }
            } else {
                theme[d3Property] = value;
            }
        });
    });
    
    return theme;
}

// Make available globally
if (typeof window !== 'undefined') {
    window.THEME_CONFIG = THEME_CONFIG;
    window.getThemeConfig = getThemeConfig;
    window.getD3Theme = getD3Theme;
}
