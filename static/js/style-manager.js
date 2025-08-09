/**
 * MindGraph Style Manager
 * Centralized style management system for all diagram types.
 * Provides clean, professional, and flexible theme handling.
 * 
 * This is a robust implementation that ensures the style manager
 * is always available and properly initialized.
 */
class StyleManager {
    constructor() {
        // Initialize default themes for all diagram types
        this.defaultThemes = {
            bubble_map: {
                topicFill: '#1976d2',  // Deep blue background
                topicText: '#ffffff',   // White text for contrast
                topicStroke: '#000000', // Black border for topic nodes
                topicStrokeWidth: 3,
                attributeFill: '#e3f2fd', // Light blue for feature nodes
                attributeText: '#333333', // Dark text for readability
                attributeStroke: '#000000',  // Black border
                attributeStrokeWidth: 2,
                fontTopic: 20,
                fontAttribute: 14
            },
            double_bubble_map: {
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
                centralTopicFill: '#e3f2fd',
                centralTopicText: '#000000',
                centralTopicStroke: '#35506b',
                centralTopicStrokeWidth: 3,
                mainBranchFill: '#e3f2fd',
                mainBranchText: '#333333',
                mainBranchStroke: '#4e79a7',
                mainBranchStrokeWidth: 2,
                subBranchFill: '#f8f9fa',
                subBranchText: '#666666',
                subBranchStroke: '#6c757d',
                subBranchStrokeWidth: 1,
                fontCentralTopic: 20,
                fontMainBranch: 16,
                fontSubBranch: 12
            },
            concept_map: {
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
                topicFill: '#e3f2fd',
                topicText: '#000000',
                topicStroke: '#35506b',
                topicStrokeWidth: 3,
                partFill: '#e3f2fd',
                partText: '#333333',
                partStroke: '#4e79a7',
                partStrokeWidth: 2,
                subpartFill: '#f8f9fa',
                subpartText: '#666666',
                subpartStroke: '#6c757d',
                subpartStrokeWidth: 1,
                fontTopic: 18,
                fontPart: 16,
                fontSubpart: 12
            },
            tree_map: {
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
                fontRoot: 20,
                fontBranch: 16,
                fontLeaf: 14
            },
            venn_diagram: {
                set1Fill: '#ff6b6b',   // Red for first set
                set1Text: '#ffffff',    // White text
                set1Stroke: '#c44569',  // Darker red border
                set1StrokeWidth: 2,
                set2Fill: '#4ecdc4',   // Teal for second set
                set2Text: '#ffffff',    // White text
                set2Stroke: '#26a69a',  // Darker teal border
                set2StrokeWidth: 2,
                set3Fill: '#45b7d1',   // Blue for third set
                set3Text: '#ffffff',    // White text
                set3Stroke: '#2c3e50',  // Darker blue border
                set3StrokeWidth: 2,
                intersectionFill: '#a8e6cf', // Light green for intersections
                intersectionText: '#333333',  // Dark text
                fontSet: 16,
                fontIntersection: 14
            },
            flowchart: {
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
        
        console.log('StyleManager initialized successfully');
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
        
        // Apply color theme if specified (but preserve our custom styling for bubble maps)
        if (userTheme && userTheme.colorTheme && this.colorThemes[userTheme.colorTheme]) {
            // For bubble maps, only apply color theme if explicitly requested
            if (diagramType === 'bubble_map' || diagramType === 'double_bubble_map') {
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
                updated.centralTopicFill = colorTheme.primary;
                updated.mainBranchFill = colorTheme.secondary;
                updated.centralTopicText = this.getContrastingTextColor(colorTheme.primary);
                updated.mainBranchText = this.getContrastingTextColor(colorTheme.secondary);
                break;
            case 'tree_map':
            case 'venn_diagram':
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
