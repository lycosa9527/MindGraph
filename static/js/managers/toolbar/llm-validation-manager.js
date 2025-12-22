/**
 * LLM Validation Manager
 * ======================
 * 
 * Handles LLM response validation, topic identification, and node extraction.
 * Validates LLM specs for all 12 diagram types.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class LLMValidationManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor;
        this.validator = new DiagramValidator();
        this.llmResults = {}; // Store for consistency analysis
        
        // Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'LLMValidationManager';
        
        // Store callback references for cleanup
        this._eventCallbacks = {};
        
        this.setupEventListeners();
        this.logger.info('LLMValidationManager', 'LLM Validation Manager initialized');
    }
    
    /**
     * Setup Event Bus listeners
     */
    setupEventListeners() {
        // Store callbacks for later cleanup
        this._eventCallbacks.identifyTopic = (data) => {
            this.logger.debug('LLMValidationManager', 'Topic identification requested', {
                nodesCount: data.nodes?.length || 0
            });
            const topic = this.identifyMainTopic(data.nodes);
            this.eventBus.emit('llm:topic_identified', { topic });
        };
        
        this._eventCallbacks.extractNodes = () => {
            this.logger.debug('LLMValidationManager', 'Node extraction requested');
            const nodes = this.extractExistingNodes();
            this.eventBus.emit('llm:nodes_extracted', { nodes });
        };
        
        this._eventCallbacks.validateSpec = (data) => {
            this.logger.debug('LLMValidationManager', 'Spec validation requested', {
                model: data.model,
                expectedType: data.expectedType
            });
            const result = this._validateLLMSpec(data.model, data.spec, data.expectedType);
            this.eventBus.emit('llm:spec_validated', { 
                model: data.model,
                result 
            });
        };
        
        this._eventCallbacks.analyzeConsistency = (data) => {
            this.logger.debug('LLMValidationManager', 'Consistency analysis requested');
            this.llmResults = data.llmResults || {};
            this._logLLMConsistencyAnalysis();
            this.eventBus.emit('llm:consistency_analyzed', {});
        };
        
        // Register listeners with owner tracking
        this.eventBus.onWithOwner('llm:identify_topic_requested', this._eventCallbacks.identifyTopic, this.ownerId);
        this.eventBus.onWithOwner('llm:extract_nodes_requested', this._eventCallbacks.extractNodes, this.ownerId);
        this.eventBus.onWithOwner('llm:validate_spec_requested', this._eventCallbacks.validateSpec, this.ownerId);
        this.eventBus.onWithOwner('llm:analyze_consistency_requested', this._eventCallbacks.analyzeConsistency, this.ownerId);
        
        this.logger.debug('LLMValidationManager', 'Event Bus listeners registered with owner tracking');
    }
    
    /**
     * Identify the main topic from existing nodes
     * Uses diagram-specific structure first, then falls back to heuristics
     * 
     * EXTRACTED FROM: toolbar-manager.js lines 2078-2363
     */
    identifyMainTopic(nodes) {
        logger.info('LLMValidationManager', '=== IDENTIFYING MAIN TOPIC ===', {
            timestamp: new Date().toISOString(),
            nodeCount: nodes.length,
            diagramType: this.editor?.diagramType,
            hasSpec: !!this.editor?.currentSpec
        });
        
        if (nodes.length === 0) {
            logger.warn('LLMValidationManager', 'No nodes provided, returning empty string');
            return '';
        }
        
        if (nodes.length === 1) {
            logger.info('LLMValidationManager', `Single node detected: "${nodes[0].text}"`);
            return nodes[0].text;
        }
        
        const diagramType = this.editor.diagramType;
        const spec = this.editor.currentSpec;
        
        // Strategy 1: For diagrams with topic field, prioritize spec (source of truth)
        // The spec is updated by updateNodeText when user edits the topic
        if (diagramType === 'bubble_map' || diagramType === 'circle_map' || 
            diagramType === 'tree_map') {
            
            logger.info('LLMValidationManager', `Strategy 1: Diagram type "${diagramType}" - checking spec.topic`);
            
            // Check spec first (updated by updateNodeText)
            if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
                logger.info('LLMValidationManager', `✓ Main topic from spec.topic: "${spec.topic}"`);
                return spec.topic;
            }
            
            // Fallback: Check DOM if spec is not available
            // CRITICAL: Circle map uses 'center', not 'topic'!
            const topicNode = nodes.find(node => 
                node.nodeType === 'topic' || node.nodeType === 'center'
            );
            if (topicNode && topicNode.text && !this.validator.isPlaceholderText(topicNode.text)) {
                logger.info('LLMValidationManager', `✓ Main topic from DOM node (type: ${topicNode.nodeType}): "${topicNode.text}"`);
                return topicNode.text;
            }
            
            logger.debug('LLMValidationManager', 'Strategy 1 failed, continuing to next strategy');
        }
        
        // Strategy 1e: For Brace Map, check spec.whole (not spec.topic!)
        if (diagramType === 'brace_map') {
            logger.info('LLMValidationManager', 'Strategy 1e: Brace map - checking spec.whole');
            
            // Check spec first (updated by updateNodeText)
            if (spec && spec.whole && !this.validator.isPlaceholderText(spec.whole)) {
                logger.info('LLMValidationManager', `✓ Main topic from spec.whole: "${spec.whole}"`);
                return spec.whole;
            }
            
            // Fallback: Check DOM if spec is not available
            const wholeNode = nodes.find(node => node.nodeType === 'topic');
            if (wholeNode && wholeNode.text && !this.validator.isPlaceholderText(wholeNode.text)) {
                logger.info('LLMValidationManager', `✓ Main topic from DOM node (whole): "${wholeNode.text}"`);
                return wholeNode.text;
            }
            
            logger.debug('LLMValidationManager', 'Strategy 1e failed, continuing to next strategy');
        }
        
        // Strategy 1-flow: For Flow Map, check spec.title (NOT spec.topic)
        // Flow Map uses 'title' field, similar to how Circle Map uses 'center' nodeType
        if (diagramType === 'flow_map') {
            // Check spec first (updated by updateFlowMapText)
            if (spec && spec.title && !this.validator.isPlaceholderText(spec.title)) {
                return spec.title;
            }
            // Fallback: Check DOM if spec is not available
            const titleNode = nodes.find(node => node.nodeType === 'title');
            if (titleNode && titleNode.text && !this.validator.isPlaceholderText(titleNode.text)) {
                return titleNode.text;
            }
        }
        
        // Strategy 1-multiflow: For Multi-Flow Map, check spec.event (NOT spec.topic)
        // Multi-Flow Map uses 'event' field for the central event
        if (diagramType === 'multi_flow_map') {
            // Check spec first (updated by updateMultiFlowMapText)
            if (spec && spec.event && !this.validator.isPlaceholderText(spec.event)) {
                return spec.event;
            }
            // Fallback: Check DOM if spec is not available
            const eventNode = nodes.find(node => node.nodeType === 'event');
            if (eventNode && eventNode.text && !this.validator.isPlaceholderText(eventNode.text)) {
                return eventNode.text;
            }
        }
        
        // Strategy 1b: For double bubble maps, ALWAYS read from currentSpec first
        // CONSISTENCY FIX: Like bridge_map, use spec as source of truth
        if (diagramType === 'double_bubble_map') {
            logger.info('LLMValidationManager', 'Strategy 1b: Double bubble map - checking spec.left and spec.right');
            
            if (spec && spec.left && spec.right) {
                // Check if topics are placeholders
                const leftIsPlaceholder = this.validator.isPlaceholderText(spec.left);
                const rightIsPlaceholder = this.validator.isPlaceholderText(spec.right);
                
                if (!leftIsPlaceholder && !rightIsPlaceholder) {
                    const combinedTopic = `${spec.left} vs ${spec.right}`;
                    logger.info('LLMValidationManager', `✓ Main topic from spec: "${combinedTopic}"`, {
                        left: spec.left,
                        right: spec.right
                    });
                    return combinedTopic;
                } else {
                    logger.warn('LLMValidationManager', `Double bubble map: Topics are placeholders (left: ${leftIsPlaceholder}, right: ${rightIsPlaceholder})`);
                }
            }
            logger.warn('LLMValidationManager', 'Double bubble map: No valid left/right topics in spec');
        }
        
        // Strategy 1c: For bridge maps, ALWAYS read from currentSpec
        // ROOT CAUSE FIX: DOM node array order ≠ pair index order
        // currentSpec.analogies[0] is the source of truth (updated by updateBridgeMapText)
        if (diagramType === 'bridge_map') {
            logger.info('LLMValidationManager', 'Strategy 1c: Bridge map - checking spec.analogies[0]');
            
            if (spec && spec.analogies && spec.analogies.length > 0) {
                const firstPair = spec.analogies[0];
                if (firstPair.left && firstPair.right) {
                    // Check if items are placeholders
                    const leftIsPlaceholder = this.validator.isPlaceholderText(firstPair.left);
                    const rightIsPlaceholder = this.validator.isPlaceholderText(firstPair.right);
                    
                    if (!leftIsPlaceholder && !rightIsPlaceholder) {
                        const mainTopic = `${firstPair.left}/${firstPair.right}`;
                        logger.info('LLMValidationManager', `✓ Main topic from spec.analogies[0]: "${mainTopic}"`, {
                            left: firstPair.left,
                            right: firstPair.right,
                            relatingFactor: spec.relatingFactor || 'not set'
                        });
                        return mainTopic;
                    } else {
                        logger.warn('LLMValidationManager', `Bridge map: First pair items are placeholders (left: ${leftIsPlaceholder}, right: ${rightIsPlaceholder})`);
                    }
                }
            }
            logger.warn('LLMValidationManager', 'Bridge map: No valid analogies in spec');
        }
        
        // Strategy 1d: For MindMap, prioritize spec first
        // CONSISTENCY FIX: Read from spec before geometric detection
        if (diagramType === 'mindmap') {
            logger.info('LLMValidationManager', 'Strategy 1d: MindMap - checking spec.topic');
            
            // First, try to get from spec (source of truth)
            if (spec && spec.topic && !this.validator.isPlaceholderText(spec.topic)) {
                logger.info('LLMValidationManager', `✓ Main topic from spec.topic: "${spec.topic}"`);
                return spec.topic;
            }
            
            logger.debug('LLMValidationManager', 'Spec topic not available, falling back to geometric center detection');
            
            // Fallback: Find the node closest to center by position
            const svg = d3.select('#d3-container svg');
            if (!svg.empty()) {
                const width = parseFloat(svg.attr('width')) || 800;
                const height = parseFloat(svg.attr('height')) || 600;
                const centerX = width / 2;
                const centerY = height / 2;
                
                // Find the node closest to center
                let centralNode = nodes[0];
                let minDistance = Infinity;
                
                nodes.forEach(node => {
                    const distance = Math.sqrt(
                        Math.pow(node.x - centerX, 2) + 
                        Math.pow(node.y - centerY, 2)
                    );
                    
                    if (distance < minDistance) {
                        minDistance = distance;
                        centralNode = node;
                    }
                });
                
                // Return the text from the central node (skip if placeholder)
                if (centralNode && centralNode.text && !this.validator.isPlaceholderText(centralNode.text)) {
                    return centralNode.text;
                }
            }
        }
        
        // Strategy 2: Use diagram-specific structure from spec (fallback)
        if (spec) {
            let mainTopic = null;
            
            switch (diagramType) {
                case 'bubble_map':
                    // For bubble map, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'circle_map':
                    // For circle map, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'tree_map':
                case 'mindmap':
                    // For tree/mind maps, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'brace_map':
                    // For brace map, the main topic is spec.whole (skip placeholders)
                    mainTopic = spec.whole && !this.validator.isPlaceholderText(spec.whole) ? spec.whole : null;
                    break;
                    
                case 'double_bubble_map':
                    // For double bubble map, use the left topic as primary (skip placeholders)
                    const leftTopic = spec.left && !this.validator.isPlaceholderText(spec.left) ? spec.left : null;
                    const rightTopic = spec.right && !this.validator.isPlaceholderText(spec.right) ? spec.right : null;
                    mainTopic = leftTopic || rightTopic;
                    break;
                    
                case 'multi_flow_map':
                    // For multi-flow map, the main topic is spec.event (skip placeholders)
                    mainTopic = spec.event && !this.validator.isPlaceholderText(spec.event) ? spec.event : null;
                    break;
                    
                case 'flow_map':
                    // For flow map, use the title or first step (skip placeholders)
                    const title = spec.title && !this.validator.isPlaceholderText(spec.title) ? spec.title : null;
                    const firstStep = spec.steps && spec.steps[0] && !this.validator.isPlaceholderText(spec.steps[0]) ? spec.steps[0] : null;
                    mainTopic = title || firstStep;
                    break;
                    
                case 'concept_map':
                    // For concept map, the main topic is spec.topic (skip placeholders)
                    mainTopic = spec.topic && !this.validator.isPlaceholderText(spec.topic) ? spec.topic : null;
                    break;
                    
                case 'bridge_map':
                    // For bridge map, extract from actual SVG nodes (Strategy 1c above)
                    // This fallback uses spec only if node extraction failed
                    if (spec.analogies && spec.analogies.length > 0) {
                        const firstPair = spec.analogies[0];
                        const leftItem = firstPair.left && !this.validator.isPlaceholderText(firstPair.left) ? firstPair.left : null;
                        const rightItem = firstPair.right && !this.validator.isPlaceholderText(firstPair.right) ? firstPair.right : null;
                        if (leftItem && rightItem) {
                            mainTopic = `${leftItem}/${rightItem}`;
                        }
                    }
                    break;
            }
            
            if (mainTopic) {
                return mainTopic;
            }
        }
        
        // Strategy 2: Find node closest to center of canvas (geometric fallback)
        const svg = d3.select('#d3-container svg');
        if (!svg.empty()) {
            const width = parseFloat(svg.attr('width')) || 800;
            const height = parseFloat(svg.attr('height')) || 600;
            const centerX = width / 2;
            const centerY = height / 2;
            
            // Calculate distance from center for each node (skip placeholders)
            let closestNode = null;
            let minDistance = Infinity;
            
            nodes.forEach(node => {
                if (!this.validator.isPlaceholderText(node.text)) {
                    const distance = Math.sqrt(
                        Math.pow(node.x - centerX, 2) + 
                        Math.pow(node.y - centerY, 2)
                    );
                    
                    if (distance < minDistance) {
                        minDistance = distance;
                        closestNode = node;
                    }
                }
            });
            
            if (closestNode) {
                return closestNode.text;
            }
        }
        
        // Strategy 3: Fallback - find first meaningful node (skip placeholders)
        const meaningfulNode = nodes.find(n => 
            n.text && 
            n.text.trim().length > 1 && 
            !this.validator.isPlaceholderText(n.text)
        );
        
        // Last resort: return first node's text (even if placeholder - user needs to edit it)
        return meaningfulNode ? meaningfulNode.text : (nodes[0]?.text || '');
    }
    
    /**
     * Extract existing nodes from the current diagram
     * 
     * EXTRACTED FROM: toolbar-manager.js lines 2368-2458
     */
    extractExistingNodes() {
        logger.info('LLMValidationManager', '=== EXTRACTING EXISTING NODES ===', {
            timestamp: new Date().toISOString(),
            diagramType: this.editor?.diagramType
        });
        
        const nodes = [];
        let skippedPlaceholders = 0;
        let skippedEmpty = 0;
        
        // Define placeholder/template text patterns to skip
        const placeholderPatterns = [
            /^New Node$/i,
            /^New (Left|Right|Item|Concept|Step|Substep|Category|Child|Part|Subpart|Cause|Effect|Attribute|Context|Branch)$/i,
            /^Item [A-Z0-9]+$/i,  // Item 1, Item A, Item B, etc.
            /^Item \d+$/i,        // Item 1, Item 2, Item 3, etc.
            /^Branch\s*\d+$/i,    // Branch 1, Branch 2, Branch 3, Branch 4, etc.
            /^as$/i,              // Bridge map relating factor default
            /^Main Topic$/i,
            /^Central Topic$/i,   // Central topic placeholder
            /^Topic [A-Z]?$/i,
            /^主题$/,
            /^中心主题$/,          // Chinese "Central Topic"
            /^新节点$/,
            /^新分支$/,            // Chinese "New Branch"
            /^分支\d+$/,           // Chinese "Branch 1", "Branch 2", etc.
            /^项目[A-Z0-9]+$/
        ];
        
        // Find all text elements in the SVG
        d3.selectAll('#d3-container text').each(function() {
            const textElement = d3.select(this);
            // Use extractTextFromSVG to handle both single-line and multi-line (tspan) text
            const text = (typeof window.extractTextFromSVG === 'function') 
                ? window.extractTextFromSVG(textElement).trim() 
                : textElement.text().trim();
            
            // Skip empty or placeholder text
            if (!text || text.length === 0) {
                skippedEmpty++;
                return;
            }
            
            // Check if this is placeholder text
            const isPlaceholder = placeholderPatterns.some(pattern => pattern.test(text));
            if (isPlaceholder) {
                skippedPlaceholders++;
                logger.debug('LLMValidationManager', `Skipping placeholder node: "${text}"`);
                return;
            }
            
            const x = parseFloat(textElement.attr('x')) || 0;
            const y = parseFloat(textElement.attr('y')) || 0;
            
            // Capture data-node-type and data-node-id from the text element itself
            // (these attributes help identify the central topic vs. children/branches)
            const nodeType = textElement.attr('data-node-type') || '';
            const nodeId = textElement.attr('data-node-id') || '';
            
            const nodeData = {
                text: text,
                x: x,
                y: y,
                nodeType: nodeType,
                nodeId: nodeId
            };
            
            nodes.push(nodeData);
            
            // VERBOSE LOG: Each node extracted
            logger.info('LLMValidationManager', `✓ Node extracted: "${text}"`, {
                index: nodes.length,
                nodeType: nodeType || 'unknown',
                nodeId: nodeId || 'unknown',
                position: { x, y },
                textLength: text.length
            });
        });
        
        // VERBOSE LOG: Summary of extraction
        logger.info('LLMValidationManager', '=== NODE EXTRACTION COMPLETE ===', {
            totalNodesExtracted: nodes.length,
            skippedEmpty: skippedEmpty,
            skippedPlaceholders: skippedPlaceholders,
            extractedNodes: nodes.map((n, i) => ({
                index: i + 1,
                text: n.text.substring(0, 50) + (n.text.length > 50 ? '...' : ''),
                type: n.nodeType || 'unknown',
                position: { x: Math.round(n.x), y: Math.round(n.y) }
            }))
        });
        
        return nodes;
    }
    
    /**
     * Validate LLM spec structure for inconsistencies
     * 
     * EXTRACTED FROM: toolbar-manager.js lines 1808-1938
     */
    _validateLLMSpec(model, spec, expectedDiagramType) {
        const issues = [];
        const missingFields = [];
        const invalidFields = [];
        
        // Basic validation
        if (!spec || typeof spec !== 'object') {
            return {
                isValid: false,
                issues: ['Spec is not an object'],
                missingFields: [],
                invalidFields: ['spec']
            };
        }
        
        // Diagram-specific validation
        switch (expectedDiagramType) {
            case 'bubble_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.attributes || !Array.isArray(spec.attributes)) {
                    invalidFields.push('attributes');
                } else if (spec.attributes.length === 0) {
                    issues.push('Empty attributes array');
                }
                break;
                
            case 'circle_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.context || !Array.isArray(spec.context)) {
                    invalidFields.push('context');
                } else if (spec.context.length === 0) {
                    issues.push('Empty context array');
                }
                break;
                
            case 'mindmap':
            case 'mind_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.children || !Array.isArray(spec.children)) {
                    invalidFields.push('children');
                } else if (spec.children.length === 0) {
                    issues.push('Empty children array');
                }
                break;
                
            case 'tree_map':
                if (!spec.topic) missingFields.push('topic');
                if (!spec.children || !Array.isArray(spec.children)) {
                    invalidFields.push('children');
                } else if (spec.children.length === 0) {
                    issues.push('Empty children array');
                }
                break;
                
            case 'brace_map':
                if (!spec.whole) missingFields.push('whole');
                if (!spec.parts || !Array.isArray(spec.parts)) {
                    invalidFields.push('parts');
                } else if (spec.parts.length === 0) {
                    issues.push('Empty parts array');
                }
                break;
                
            case 'bridge_map':
                if (!spec.analogies || !Array.isArray(spec.analogies)) {
                    invalidFields.push('analogies');
                } else if (spec.analogies.length === 0) {
                    issues.push('Empty analogies array');
                } else {
                    // Check each analogy has left and right
                    spec.analogies.forEach((analogy, i) => {
                        if (!analogy.left) missingFields.push(`analogies[${i}].left`);
                        if (!analogy.right) missingFields.push(`analogies[${i}].right`);
                    });
                }
                break;
                
            case 'double_bubble_map':
                if (!spec.left) missingFields.push('left');
                if (!spec.right) missingFields.push('right');
                if (!spec.similarities || !Array.isArray(spec.similarities)) {
                    invalidFields.push('similarities');
                }
                if (!spec.left_differences || !Array.isArray(spec.left_differences)) {
                    invalidFields.push('left_differences');
                }
                if (!spec.right_differences || !Array.isArray(spec.right_differences)) {
                    invalidFields.push('right_differences');
                }
                break;
                
            case 'flow_map':
                if (!spec.title) missingFields.push('title');
                if (!spec.steps || !Array.isArray(spec.steps)) {
                    invalidFields.push('steps');
                } else if (spec.steps.length === 0) {
                    issues.push('Empty steps array');
                }
                break;
                
            case 'multi_flow_map':
                if (!spec.event) missingFields.push('event');
                if (!spec.causes || !Array.isArray(spec.causes)) {
                    invalidFields.push('causes');
                }
                if (!spec.effects || !Array.isArray(spec.effects)) {
                    invalidFields.push('effects');
                }
                break;
                
            case 'concept_map':
                if (!spec.nodes || !Array.isArray(spec.nodes)) {
                    invalidFields.push('nodes');
                } else if (spec.nodes.length === 0) {
                    issues.push('Empty nodes array');
                }
                if (!spec.connections || !Array.isArray(spec.connections)) {
                    invalidFields.push('connections');
                }
                break;
        }
        
        const isValid = missingFields.length === 0 && invalidFields.length === 0 && issues.length === 0;
        
        return {
            isValid: isValid,
            issues: issues,
            missingFields: missingFields,
            invalidFields: invalidFields
        };
    }
    
    /**
     * Log consistency analysis comparing all LLM results
     * 
     * EXTRACTED FROM: toolbar-manager.js lines 1943-2036
     */
    _logLLMConsistencyAnalysis() {
        const successful = Object.entries(this.llmResults)
            .filter(([_, result]) => result.success)
            .map(([model, result]) => ({ model, ...result }));
        
        if (successful.length < 2) return;
        
        logger.info('LLMValidationManager', '=== LLM CONSISTENCY ANALYSIS ===', {
            timestamp: new Date().toISOString(),
            totalModels: successful.length,
            models: successful.map(r => r.model)
        });
        
        // Compare specs
        const specComparison = {
            models: successful.map(r => r.model),
            specs: {}
        };
        
        successful.forEach(({ model, result, validation }) => {
            const spec = result.spec;
            specComparison.specs[model] = {
                diagram_type: result.diagram_type,
                spec_keys: spec ? Object.keys(spec) : [],
                validation: validation,
                structure: {}
            };
            
            // Extract key structural info
            if (spec) {
                if (spec.topic) specComparison.specs[model].structure.topic = spec.topic;
                if (spec.children) specComparison.specs[model].structure.childrenCount = spec.children.length;
                if (spec.nodes) specComparison.specs[model].structure.nodesCount = spec.nodes.length;
                if (spec.categories) specComparison.specs[model].structure.categoriesCount = spec.categories.length;
                if (spec.parts) specComparison.specs[model].structure.partsCount = spec.parts.length;
                if (spec.analogies) specComparison.specs[model].structure.analogiesCount = spec.analogies.length;
                if (spec.steps) specComparison.specs[model].structure.stepsCount = spec.steps.length;
            }
        });
        
        logger.info('LLMValidationManager', 'Spec comparison across models:', specComparison);
        
        // Identify inconsistencies
        const inconsistencies = [];
        
        // Check if all have same number of children/nodes
        const childCounts = successful
            .map(r => r.result.spec?.children?.length || r.result.spec?.nodes?.length || 0)
            .filter(c => c > 0);
        
        if (childCounts.length > 1) {
            const min = Math.min(...childCounts);
            const max = Math.max(...childCounts);
            if (max - min > 2) {
                inconsistencies.push({
                    type: 'content_count_variance',
                    message: `Large variance in content count: ${min} to ${max}`,
                    models: successful.map((r, i) => ({
                        model: r.model,
                        count: childCounts[i]
                    }))
                });
            }
        }
        
        // Check for validation failures
        const validationIssues = successful.filter(r => r.validation && !r.validation.isValid);
        if (validationIssues.length > 0) {
            inconsistencies.push({
                type: 'validation_failures',
                message: `${validationIssues.length} model(s) have validation issues`,
                models: validationIssues.map(r => ({
                    model: r.model,
                    issues: r.validation.issues,
                    missingFields: r.validation.missingFields,
                    invalidFields: r.validation.invalidFields
                }))
            });
        }
        
        // Log inconsistencies
        if (inconsistencies.length > 0) {
            // Check if there are actual validation failures (real problems)
            const hasValidationFailures = inconsistencies.some(i => i.type === 'validation_failures');
            
            // Only count variance is expected behavior, use INFO level
            // Validation failures are actual problems, use WARN level
            if (hasValidationFailures) {
                logger.warn('LLMValidationManager', '⚠️ LLM INCONSISTENCIES DETECTED', {
                    timestamp: new Date().toISOString(),
                    inconsistencyCount: inconsistencies.length,
                    inconsistencies: inconsistencies
                });
            } else {
                // Only content count variance - this is normal, use INFO
                logger.info('LLMValidationManager', 'ℹ️ LLM content variance (normal)', {
                    timestamp: new Date().toISOString(),
                    varianceCount: inconsistencies.length,
                    variances: inconsistencies
                });
            }
        } else {
            logger.info('LLMValidationManager', '✓ All LLM results are consistent', {
                timestamp: new Date().toISOString(),
                modelsCompared: successful.length
            });
        }
    }
    
    /**
     * Cleanup method - remove Event Bus listeners
     */
    destroy() {
        this.logger.debug('LLMValidationManager', 'Destroying manager and cleaning up listeners');
        
        // Remove all Event Bus listeners using Listener Registry
        if (this.eventBus && this.ownerId) {
            this.eventBus.removeAllListenersForOwner(this.ownerId);
            this.logger.debug('LLMValidationManager', 'Event listeners successfully removed');
        }
        
        // Nullify references
        this.editor = null;
        this.validator = null;
        this.llmResults = null;
        this._eventCallbacks = null;
        
        this.logger.debug('LLMValidationManager', 'Cleanup complete');
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.LLMValidationManager = LLMValidationManager;
}

