/**
 * DiagramValidator
 * 
 * Validates diagram completeness before entering Learning Mode.
 * Checks for empty nodes and placeholder text patterns.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class DiagramValidator {
    constructor() {
        this.logger = window.frontendLogger || console;
        
        // Chinese placeholder patterns (from language-manager.js)
        this.chinesePlaceholders = [
            /^分支\s*\d+$/,           // 分支1, 分支2
            /^子项\s*[\d.]+$/,        // 子项1.1, 子项2.3
            /^子节点\s*[\d.]+$/,      // 子节点1.1
            /^子\s*[\d.]+$/,          // 子1.1
            /^新.*$/,                 // 新节点, 新属性, 新步骤, 新原因, 新结果, etc.
            /^属性\s*\d+$/,           // 属性1, 属性2
            /^步骤\s*\d+$/,           // 步骤1, 步骤2
            /^子步骤\s*[\d.]+$/,      // 子步骤1.1, 子步骤2.2 (Flow Map)
            /^原因\s*\d+$/,           // 原因1
            /^结果\s*\d+$/,           // 结果1
            /^联想\s*\d+$/,           // 联想1, 联想2 (Circle Map context nodes)
            /^事件流程$/,             // 事件流程 (Flow Map title)
            /^事件$/,                 // 事件 (Multi-Flow Map event)
            /^主题\s*\d+$/,           // 主题1
            /^主题$/,                 // 主题 (Circle Map default)
            /^主题[A-Z]$/,            // 主题A, 主题B (Double Bubble Map)
            /^相似点\s*\d+$/,         // 相似点1, 相似点2 (Double Bubble Map)
            /^不同点[A-Z]\d+$/,       // 不同点A1, 不同点B2 (Double Bubble Map)
            /^如同$/,                 // 如同 (Bridge Map relating factor)
            /^事物[A-Z]\d+$/,         // 事物A1, 事物B1 (Bridge Map)
            /^项目[\d.]+$/,           // 项目1.1, 项目2.3 (Tree Map)
            /^根主题$/,               // 根主题 (Tree Map)
            /^类别\s*\d+$/,           // 类别1, 类别2 (Tree Map)
            /^分类\s*\d+$/,           // 分类1
            /^叶子\s*\d+$/,           // 叶子1
            /^部分\s*\d+$/,           // 部分1
            /^子部分\s*\d+$/,         // 子部分1
            /^左\s*\d+$/,             // 左1
            /^右\s*\d+$/,             // 右1
            /^中心主题$/,             // 中心主题
            /^主要主题$/,             // 主要主题
            /^要点\s*\d+$/,           // 要点1
            /^概念\s*\d+$/,           // 概念1
            /^关联$/,                 // 关联
        ];
        
        // English placeholder patterns
        this.englishPlaceholders = [
            /^Branch\s+\d+$/i,        // Branch 1, Branch 2
            /^Child\s+[\d.]+$/i,      // Child 1.1, Child 2.3
            /^New\s+.*$/i,            // New Node, New Attribute, New Step, etc.
            /^Attribute\s+\d+$/i,     // Attribute 1, Attribute 2
            /^Step\s+\d+$/i,          // Step 1, Step 2
            /^Substep\s+[\d.]+$/i,    // Substep 1.1, Substep 2.2 (Flow Map)
            /^Cause\s+\d+$/i,         // Cause 1
            /^Effect\s+\d+$/i,        // Effect 1
            /^Context\s+\d+$/i,       // Context 1, Context 2 (Circle Map context nodes)
            /^Process$/i,             // Process (Flow Map title)
            /^Main\s+Event$/i,        // Main Event (Multi-Flow Map event)
            /^Topic\s+\d+$/i,         // Topic 1
            /^Topic\s+[A-Z]$/i,       // Topic A, Topic B (Double Bubble Map)
            /^Similarity\s+\d+$/i,    // Similarity 1, 2 (Double Bubble Map)
            /^Difference\s+[A-Z]\d+$/i, // Difference A1, B2 (Double Bubble Map)
            /^as$/i,                  // as (Bridge Map relating factor)
            /^Item\s+\d+$/i,          // Item 1, Item 2 (Bridge Map)
            /^Item\s+[A-Z]$/i,        // Item A, Item B (Bridge Map)
            /^Item\s+[\d.]+$/i,       // Item 1.1, Item 2.3 (Tree Map)
            /^Root\s+Topic$/i,        // Root Topic (Tree Map)
            /^Category\s+\d+$/i,      // Category 1 (Tree Map)
            /^Leaf\s+\d+$/i,          // Leaf 1
            /^Part\s+\d+$/i,          // Part 1
            /^Subpart\s+\d+$/i,       // Subpart 1
            /^Left\s+\d+$/i,          // Left 1
            /^Right\s+\d+$/i,         // Right 1
            /^Main\s+Topic$/i,        // Main Topic
            /^Central\s+Topic$/i,     // Central Topic
            /^Point\s+\d+$/i,         // Point 1
            /^Concept\s+\d+$/i,       // Concept 1
            /^Relation(ship)?$/i,     // Relation, Relationship
        ];
        
        this.allPlaceholders = [...this.chinesePlaceholders, ...this.englishPlaceholders];
    }
    
    /**
     * Validates the current diagram in the SVG canvas
     * @param {string} diagramType - Current diagram type (mind_map, bubble_map, etc.)
     * @returns {Object} Validation result: { isValid, invalidNodes, reason }
     */
    validateDiagram(diagramType) {
        this.logger.debug('DiagramValidator', `Validating diagram type: ${diagramType}`);
        
        const container = d3.select('#d3-container svg');
        if (container.empty()) {
            return {
                isValid: false,
                invalidNodes: [],
                reason: 'No diagram found in canvas'
            };
        }
        
        // Get all text elements with data-node-id attribute
        const allNodeTexts = container.selectAll('text[data-node-id]');
        
        if (allNodeTexts.empty() || allNodeTexts.size() === 0) {
            return {
                isValid: false,
                invalidNodes: [],
                reason: 'No nodes found in diagram'
            };
        }
        
        const invalidNodes = [];
        const totalNodes = allNodeTexts.size();
        
        // Capture validator instance to use inside .each()
        const validator = this;
        
        // Check each node
        allNodeTexts.each(function() {
            const textElement = d3.select(this);
            const nodeId = textElement.attr('data-node-id');
            const nodeType = textElement.attr('data-node-type');
            // Use extractTextFromSVG to handle both single-line and multi-line (tspan) text
            const textContent = (typeof window.extractTextFromSVG === 'function') 
                ? window.extractTextFromSVG(textElement).trim() 
                : textElement.text().trim();
            
            // CRITICAL FIX: Skip dimension nodes - they are OPTIONAL for all diagram types
            // Users can leave them blank and LLM will auto-select the best dimension
            if (nodeType === 'dimension') {
                validator.logger.log('DiagramValidator', `  ⏭️  Skipping dimension node validation (optional field)`);
                return; // Skip validation for dimension nodes
            }
            
            // Check for empty text
            if (!textContent || textContent.length === 0) {
                invalidNodes.push({
                    id: nodeId,
                    type: nodeType,
                    reason: 'empty',
                    text: ''
                });
                return;
            }
            
            // 🆕 Removed placeholder validation - users can start with template text
            // ThinkGuide and LLMs can help build diagrams from scratch!
        });
        
        // Generate validation result
        if (invalidNodes.length === 0) {
            this.logger.debug('DiagramValidator', `✅ Validation passed! ${totalNodes} nodes all valid.`);
            return {
                isValid: true,
                invalidNodes: [],
                totalNodes: totalNodes,
                reason: 'All nodes are complete'
            };
        } else {
            const emptyCount = invalidNodes.filter(n => n.reason === 'empty').length;
            const placeholderCount = invalidNodes.filter(n => n.reason === 'placeholder').length;
            
            let reason = '';
            if (emptyCount > 0 && placeholderCount > 0) {
                reason = `Found ${emptyCount} empty node(s) and ${placeholderCount} placeholder(s)`;
            } else if (emptyCount > 0) {
                reason = `Found ${emptyCount} empty node(s)`;
            } else {
                reason = `Found ${placeholderCount} placeholder(s)`;
            }
            
            this.logger.debug('DiagramValidator', `❌ Validation failed: ${reason}`);
            
            // Log details of invalid nodes only in debug mode (reduces console noise)
            // To enable: add ?debug=1 to URL or run: localStorage.setItem('mindgraph_debug', 'true')
            if (this.logger.debugMode) {
                invalidNodes.forEach(node => {
                    this.logger.debug('DiagramValidator', `  ❌ Invalid node: [${node.id}] "${node.text}" (${node.reason})`);
                });
            }
            
            return {
                isValid: false,
                invalidNodes: invalidNodes,
                totalNodes: totalNodes,
                reason: reason
            };
        }
    }
    
    /**
     * Checks if text matches placeholder patterns
     * @param {string} text - Text content to check
     * @returns {boolean} True if text is a placeholder
     */
    isPlaceholderText(text) {
        if (!text || text.trim().length === 0) {
            return false; // Empty text is handled separately
        }
        
        const trimmedText = text.trim();
        
        // Check against all placeholder patterns
        for (const pattern of this.allPlaceholders) {
            if (pattern.test(trimmedText)) {
                return true;
            }
        }
        
        return false;
    }
    
    /**
     * Validates and enables/disables the Learning button
     * @param {HTMLElement} learningBtn - The Learning Mode button element
     * @param {string} diagramType - Current diagram type
     * @returns {Object} Validation result
     */
    validateAndUpdateButton(learningBtn, diagramType) {
        const result = this.validateDiagram(diagramType);
        
        // Update Learning button
        if (learningBtn) {
            if (result.isValid) {
                learningBtn.disabled = false;
                learningBtn.classList.remove('disabled');
                this.logger.debug('DiagramValidator', '✅ Learning button enabled');
            } else {
                learningBtn.disabled = true;
                learningBtn.classList.add('disabled');
                this.logger.debug('DiagramValidator', `❌ Learning button disabled: ${result.reason}`);
            }
        } else {
            this.logger.warn('DiagramValidator', 'Learning button not found');
        }
        
        // ThinkGuide is ALWAYS available - no validation needed!
        // It can help build diagrams from scratch, so don't disable it
        const thinkingBtn = document.getElementById('thinking-btn');
        if (thinkingBtn) {
            thinkingBtn.disabled = false;
            thinkingBtn.classList.remove('disabled');
            this.logger.debug('DiagramValidator', '✅ ThinkGuide always enabled (no validation required)');
        }
        
        return result;
    }
    
    /**
     * Gets a user-friendly validation message
     * @param {Object} validationResult - Result from validateDiagram()
     * @param {string} language - 'en' or 'zh'
     * @returns {string} User-friendly message
     */
    getValidationMessage(validationResult, language = 'en') {
        const { isValid, invalidNodes, totalNodes, reason } = validationResult;
        
        if (isValid) {
            if (language === 'zh') {
                return `✅ 图示已完成！共 ${totalNodes} 个节点，全部有效。`;
            } else {
                return `✅ Diagram complete! All ${totalNodes} nodes are valid.`;
            }
        } else {
            const emptyCount = invalidNodes.filter(n => n.reason === 'empty').length;
            const placeholderCount = invalidNodes.filter(n => n.reason === 'placeholder').length;
            
            if (language === 'zh') {
                if (emptyCount > 0 && placeholderCount > 0) {
                    return `❌ 请先完成图示：发现 ${emptyCount} 个空节点和 ${placeholderCount} 个占位符`;
                } else if (emptyCount > 0) {
                    return `❌ 请先完成图示：发现 ${emptyCount} 个空节点`;
                } else {
                    return `❌ 请先完成图示：发现 ${placeholderCount} 个占位符`;
                }
            } else {
                if (emptyCount > 0 && placeholderCount > 0) {
                    return `❌ Please complete diagram: Found ${emptyCount} empty node(s) and ${placeholderCount} placeholder(s)`;
                } else if (emptyCount > 0) {
                    return `❌ Please complete diagram: Found ${emptyCount} empty node(s)`;
                } else {
                    return `❌ Please complete diagram: Found ${placeholderCount} placeholder(s)`;
                }
            }
        }
    }
}

// Make available globally
window.DiagramValidator = DiagramValidator;

