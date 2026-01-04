/**
 * MindGraph Style Manager
 * Centralized style management system for all diagram types.
 * Provides clean, professional, and flexible theme handling.
 * 
 * This is a robust implementation that ensures the style manager
 * is always available and properly initialized.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */
class StyleManager {
    constructor() {
        // Initialize default themes for all diagram types
        this.defaultThemes = {
                    bubble_map: {
            background: '#f5f5f5',    // Light grey background for entire canvas
            topicFill: '#1976d2',  // Deep blue background
            topicText: '#ffffff',   // White text for contrast
            topicStroke: '#000000', // Black border for topic nodes
            topicStrokeWidth: 2,
            attributeFill: '#e3f2fd', // Light blue for feature nodes
            attributeText: '#333333', // Dark text for readability
            attributeStroke: '#000000',  // Black border
            attributeStrokeWidth: 2,
            fontTopic: 20,
            fontAttribute: 14
        },
            double_bubble_map: {
                background: '#f5f5f5',         // Light grey background
                centralTopicFill: '#1976d2',  // Deeper blue
                centralTopicText: '#ffffff',   // White text for contrast
                centralTopicStroke: '#000000', // Black border for central topic
                centralTopicStrokeWidth: 3,
                leftTopicFill: '#1976d2',     // Deeper blue
                leftTopicText: '#ffffff',      // White text for contrast
                leftTopicStroke: '#000000',   // Black border for left topic
                leftTopicStrokeWidth: 2,
                rightTopicFill: '#1976d2',    // Deeper blue
                rightTopicText: '#ffffff',     // White text for contrast
                rightTopicStroke: '#000000',  // Black border for right topic
                rightTopicStrokeWidth: 2,
                attributeFill: '#e3f2fd', // Light blue for feature nodes
                attributeText: '#333333',
                attributeStroke: '#000000',  // Black border
                attributeStrokeWidth: 2,
                fontCentralTopic: 18,
                fontTopic: 16,
                fontAttribute: 12
            },
            mindmap: {
                background: '#f5f5f5',         // Light grey background
                centralTopicFill: '#1976d2',   // Deep blue for central topic (like brace maps)
                centralTopicText: '#ffffff',   // White text for contrast (like brace maps)
                centralTopicStroke: '#0d47a1', // Darker blue border (like brace maps)
                centralTopicStrokeWidth: 3,
                branchFill: '#e3f2fd',         // Light blue for branches (like brace map parts)
                branchText: '#333333',         // Dark text for readability
                branchStroke: '#4e79a7',       // Medium blue border (like brace map parts)
                branchStrokeWidth: 2,
                childFill: '#bbdefb',          // Lighter blue for children (like brace map subparts)
                childText: '#333333',          // Dark text for readability
                childStroke: '#90caf9',        // Light blue border (like brace map subparts)
                childStrokeWidth: 1,
                fontTopic: 18,
                fontBranch: 16,
                fontChild: 12,
                linkStroke: '#4e79a7',
                linkStrokeWidth: 2
            },
            concept_map: {
                background: '#f5f5f5',    // Light grey background for entire canvas
                topicFill: '#e3f2fd',
                topicText: '#000000',
                topicStroke: '#35506b',
                topicStrokeWidth: 3,
                conceptFill: '#e3f2fd',
                conceptText: '#333333',
                conceptStroke: '#4e79a7',
                conceptStrokeWidth: 2,
                relationshipColor: '#666666',
                relationshipStrokeWidth: 2,
                fontTopic: 18,
                fontConcept: 14
            },
            brace_map: {
                background: '#f5f5f5',         // Light grey background
                topicFill: '#1976d2',
                topicText: '#ffffff',
                topicStroke: '#0d47a1',
                topicStrokeWidth: 3,
                partFill: '#e3f2fd',
                partText: '#333333',
                partStroke: '#4e79a7',
                partStrokeWidth: 2,
                subpartFill: '#bbdefb',
                subpartText: '#333333',
                subpartStroke: '#90caf9',
                subpartStrokeWidth: 1,
                braceColor: '#666666',          // Gray for brace lines
                dimensionLabelColor: '#1976d2', // Dark blue for dimension label (classroom visibility)
                fontTopic: 18,
                fontPart: 16,
                fontSubpart: 12
            },
            tree_map: {
                background: '#f5f5f5',         // Light grey background
                rootFill: '#1976d2',
                rootText: '#ffffff',
                rootStroke: '#0d47a1',
                rootStrokeWidth: 2,
                branchFill: '#e3f2fd',
                branchText: '#333333',
                branchStroke: '#1976d2',
                branchStrokeWidth: 1.5,
                // Children nodes now use rectangle borders and vertical alignment
                leafFill: '#ffffff',
                leafText: '#333333',
                leafStroke: '#c8d6e5',
                leafStrokeWidth: 1,
                dimensionLabelColor: '#1976d2', // Dark blue for dimension label (classroom visibility)
                fontRoot: 20,
                fontBranch: 16,
                fontLeaf: 14
            },

            flowchart: {
                background: '#f5f5f5',         // Light grey background
                startFill: '#4caf50',   // Green for start
                startText: '#ffffff',    // White text
                startStroke: '#388e3c',  // Darker green border
                startStrokeWidth: 2,
                processFill: '#2196f3',  // Blue for process
                processText: '#ffffff',  // White text
                processStroke: '#1976d2', // Darker blue border
                processStrokeWidth: 2,
                decisionFill: '#ff9800', // Orange for decision
                decisionText: '#ffffff',  // White text
                decisionStroke: '#f57c00', // Darker orange border
                decisionStrokeWidth: 2,
                endFill: '#f44336',     // Red for end
                endText: '#ffffff',      // White text
                endStroke: '#d32f2f',   // Darker red border
                endStrokeWidth: 2,
                fontNode: 14,
                fontEdge: 12
            },
            bridge_map: {
                background: '#f5f5f5',         // Light grey background
                bridgeLineColor: '#666666',    // Gray for the main bridge line
                analogyTextColor: '#333333',   // Dark gray for analogy text
                analogyFontSize: 14,           // Font size for analogy items
                dimensionLabelColor: '#1976d2', // Dark blue for dimension label (classroom visibility)
                firstPairFill: '#1976d2',      // Deep blue for first pair boxes
                firstPairText: '#ffffff',      // White text for first pair
                firstPairStroke: '#0d47a1',    // Darker blue border for first pair
                firstPairStrokeWidth: 2
            }
        };

        // Color themes for different styles
        this.colorThemes = {
            classic: {
                primary: '#4e79a7',
                secondary: '#f28e2c',
                accent: '#e15759',
                background: '#ffffff',
                text: '#2c3e50'
            },
            innovation: {
                primary: '#2ecc71',
                secondary: '#3498db',
                accent: '#e74c3c',
                background: '#ecf0f1',
                text: '#2c3e50'
            },
            elegant: {
                primary: '#e3f2fd',
                secondary: '#bbdefb',
                accent: '#90caf9',
                background: '#fafafa',
                text: '#37474f'
            }
        };

        // Ensure the style manager is globally available
        if (typeof window !== 'undefined') {
            window.styleManager = this;
        }
        
        // StyleManager initialized successfully
    }

    /**
     * Get a complete theme for a specific diagram type
     * @param {string} diagramType - The type of diagram
     * @param {object} userTheme - User-provided theme overrides
     * @param {object} backendTheme - Backend-provided theme overrides
     * @returns {object} Complete theme object
     */
    getTheme(diagramType, userTheme = null, backendTheme = null) {
        // Start with default theme for the diagram type
        const defaultTheme = this.defaultThemes[diagramType] || {};
        
        // Create a new theme object to avoid mutations
        let theme = { ...defaultTheme };
        
        // Merge backend theme if provided
        if (backendTheme) {
            theme = this.mergeBackendTheme(theme, backendTheme);
        }
        
        // Merge user theme if provided
        if (userTheme) {
            theme = this.mergeUserTheme(theme, userTheme);
        }
        
        // Apply color theme if specified (but preserve our custom styling for bubble maps and mindmaps)
        if (userTheme && userTheme.colorTheme && this.colorThemes[userTheme.colorTheme]) {
            // For bubble maps and mindmaps, only apply color theme if explicitly requested
            if (diagramType === 'bubble_map' || diagramType === 'double_bubble_map' || diagramType === 'mindmap') {
                // Only apply if it's not our default styling
                if (userTheme.colorTheme !== 'default') {
                    theme = this.applyColorTheme(theme, userTheme.colorTheme, diagramType);
                }
            } else {
                theme = this.applyColorTheme(theme, userTheme.colorTheme, diagramType);
            }
        }
        
        // Ensure readability
        theme = this.ensureReadability(theme);
        
        return theme;
    }

    /**
     * Merge backend theme with current theme
     * @param {object} theme - Current theme
     * @param {object} backendTheme - Backend theme
     * @returns {object} Merged theme
     */
    mergeBackendTheme(theme, backendTheme) {
        const merged = { ...theme };
        
        // Handle nested theme structure
        if (backendTheme.topic) {
            merged.topicFill = backendTheme.topic.fill || merged.topicFill;
            merged.topicText = backendTheme.topic.text || merged.topicText;
            merged.topicStroke = backendTheme.topic.stroke || merged.topicStroke;
        }
        
        // Handle flat theme structure
        Object.keys(backendTheme).forEach(key => {
            if (backendTheme[key] !== undefined && backendTheme[key] !== null) {
                merged[key] = backendTheme[key];
            }
        });
        
        return merged;
    }

    /**
     * Merge user theme with current theme
     * @param {object} theme - Current theme
     * @param {object} userTheme - User theme
     * @returns {object} Merged theme
     */
    mergeUserTheme(theme, userTheme) {
        const merged = { ...theme };
        
        // Handle specific user overrides
        Object.keys(userTheme).forEach(key => {
            if (userTheme[key] !== undefined && userTheme[key] !== null) {
                merged[key] = userTheme[key];
            }
        });
        
        return merged;
    }

    /**
     * Apply a color theme to the current theme
     * @param {object} theme - Current theme
     * @param {string} colorThemeName - Name of color theme
     * @param {string} diagramType - Type of diagram
     * @returns {object} Theme with applied color theme
     */
    applyColorTheme(theme, colorThemeName, diagramType) {
        const colorTheme = this.colorThemes[colorThemeName];
        if (!colorTheme) return theme;
        
        const updated = { ...theme };
        
        // Apply colors based on diagram type
        switch (diagramType) {
            case 'bubble_map':
            case 'double_bubble_map':
            case 'concept_map':
            case 'brace_map':
                updated.topicFill = colorTheme.primary;
                updated.attributeFill = colorTheme.secondary;
                updated.topicText = this.getContrastingTextColor(colorTheme.primary);
                updated.attributeText = this.getContrastingTextColor(colorTheme.secondary);
                break;
            case 'mindmap':
                updated.centralNodeFill = colorTheme.primary;
                updated.branchFill = colorTheme.secondary;
                updated.centralNodeText = this.getContrastingTextColor(colorTheme.primary);
                updated.branchText = this.getContrastingTextColor(colorTheme.secondary);
                // Also update legacy property names for backward compatibility
                updated.centralTopicFill = colorTheme.primary;
                updated.mainBranchFill = colorTheme.secondary;
                updated.centralTopicText = this.getContrastingTextColor(colorTheme.primary);
                updated.mainBranchText = this.getContrastingTextColor(colorTheme.secondary);
                break;
            case 'tree_map':

            case 'flowchart':
                updated.nodeFill = colorTheme.primary;
                updated.nodeText = this.getContrastingTextColor(colorTheme.primary);
                break;
        }
        
        return updated;
    }

    /**
     * Ensure text colors are readable on their backgrounds
     * @param {object} theme - Theme to check
     * @returns {object} Theme with ensured readability
     */
    ensureReadability(theme) {
        const updated = { ...theme };
        
        // Check all fill/text pairs
        const pairs = [
            ['topicFill', 'topicText'],
            ['attributeFill', 'attributeText'],
            ['centralTopicFill', 'centralTopicText'],
            ['mainBranchFill', 'mainBranchText'],
            ['conceptFill', 'conceptText'],
            ['partFill', 'partText'],
            ['nodeFill', 'nodeText'],
            ['circleFill', 'circleText']
        ];
        
        pairs.forEach(([fillKey, textKey]) => {
            if (updated[fillKey] && !updated[textKey]) {
                updated[textKey] = this.getContrastingTextColor(updated[fillKey]);
            }
        });
        
        return updated;
    }

    /**
     * Get contrasting text color for a background color
     * @param {string} backgroundColor - Background color in hex format
     * @returns {string} Contrasting text color
     */
    getContrastingTextColor(backgroundColor) {
        if (!backgroundColor) return '#000000';
        
        // Convert hex to RGB
        const hex = backgroundColor.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16);
        const g = parseInt(hex.substr(2, 2), 16);
        const b = parseInt(hex.substr(4, 2), 16);
        
        // Calculate luminance
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        
        // Return contrasting color
        return luminance > 0.5 ? '#000000' : '#ffffff';
    }

    /**
     * Check if a color is light
     * @param {string} color - Color in hex format
     * @returns {boolean} True if light
     */
    isLightBackground(color) {
        if (!color) return false;
        
        const hex = color.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16);
        const g = parseInt(hex.substr(2, 2), 16);
        const b = parseInt(hex.substr(4, 2), 16);
        
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return luminance > 0.5;
    }

    /**
     * Check if a color is dark
     * @param {string} color - Color in hex format
     * @returns {boolean} True if dark
     */
    isDarkBackground(color) {
        return !this.isLightBackground(color);
    }

    /**
     * Update a specific color in a theme
     * @param {object} theme - Theme to update
     * @param {string} element - Element to update (e.g., 'topicFill')
     * @param {string} color - New color
     * @returns {object} Updated theme
     */
    updateColor(theme, element, color) {
        const updated = { ...theme };
        updated[element] = color;
        
        // Ensure readability
        if (element.includes('Fill') && !element.includes('Text')) {
            const textElement = element.replace('Fill', 'Text');
            if (!updated[textElement]) {
                updated[textElement] = this.getContrastingTextColor(color);
            }
        }
        
        return updated;
    }

    /**
     * Get available color themes
     * @returns {object} Available color themes
     */
    getAvailableColorThemes() {
        return Object.keys(this.colorThemes);
    }

    /**
     * Add a new color theme
     * @param {string} name - Theme name
     * @param {object} colors - Color definitions
     */
    addColorTheme(name, colors) {
        this.colorThemes[name] = colors;
    }

    /**
     * Get default theme for a diagram type
     * @param {string} diagramType - Diagram type
     * @returns {object} Default theme
     */
    getDefaultTheme(diagramType) {
        return { ...this.defaultThemes[diagramType] } || {};
    }
    
    /**
     * Store imported theme for use during diagram render
     * Used by .mg file import to restore saved styles
     * @param {string} diagramType - Type of diagram
     * @param {object} theme - Theme object with colors and fonts
     */
    setImportedTheme(diagramType, theme) {
        if (!this.importedThemes) {
            this.importedThemes = {};
        }
        this.importedThemes[diagramType] = theme;
        console.log('[StyleManager] Stored imported theme for', diagramType);
    }
    
    /**
     * Get theme for a diagram type (checks imported first, then default)
     * @param {string} diagramType - Type of diagram
     * @returns {object} Theme object
     */
    getTheme(diagramType) {
        // Check for imported theme first
        if (this.importedThemes && this.importedThemes[diagramType]) {
            const imported = this.importedThemes[diagramType];
            // Clear after use (one-time import)
            delete this.importedThemes[diagramType];
            console.log('[StyleManager] Using imported theme for', diagramType);
            return imported;
        }
        // Fall back to default
        return this.getDefaultTheme(diagramType);
    }

    /**
     * Validate a theme object
     * @param {object} theme - Theme to validate
     * @returns {boolean} True if valid
     */
    validateTheme(theme) {
        if (!theme || typeof theme !== 'object') return false;
        
        // Check for required properties based on theme type
        const requiredProps = ['topicFill', 'topicText'];
        return requiredProps.every(prop => theme.hasOwnProperty(prop));
    }
}

// Create and export the style manager instance
const styleManager = new StyleManager();

// Ensure global availability
if (typeof window !== 'undefined') {
    window.styleManager = styleManager;
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = styleManager;
}
