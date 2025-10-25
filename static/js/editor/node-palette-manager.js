/**
 * Node Palette Manager
 * ====================
 * 
 * Manages the Node Palette feature for all diagram types.
 * Handles multi-LLM node generation, selection, and diagram integration.
 * 
 * Features:
 * - SSE streaming from 4 LLMs (qwen, deepseek, hunyuan, kimi)
 * - Infinite scroll with smart stopping (200 nodes or 12 batches)
 * - Real-time node selection with animations
 * - Support for multiple diagram types with appropriate terminology
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class NodePaletteManager {
    constructor() {
        this.nodes = [];
        this.selectedNodes = new Set();
        this.currentBatch = 0;
        this.sessionId = null;
        this.centerTopic = null;
        this.diagramData = null;
        this.diagramType = null;  // Track diagram type
        this.isLoadingBatch = false;  // Prevent duplicate batch requests
        
        // Tab management for double bubble map and multi flow map
        this.currentTab = null;  // Will be set dynamically based on diagram type
        this.tabNodes = {};  // Will be initialized dynamically
        this.tabSelectedNodes = {};  // Will be initialized dynamically
        this.tabScrollPositions = {};  // Will be initialized dynamically
        this.lastScrollPosition = 0;  // For non-tab diagrams scroll persistence
        
        // Stage management for tree maps (multi-stage workflow)
        this.currentStage = null;  // 'dimensions', 'categories', or 'children'
        this.stageData = {};  // Store stage-specific data (selected dimension, categories, etc.)
        this.lockedTabs = new Set();  // Track which tabs are locked after progression
        this.stageGeneration = 0;  // Increment on stage change to invalidate old batches
        this.currentBatchAbortController = null;  // AbortController for current batch request
        
        // Diagram type metadata - node types and array names
        this.diagramMetadata = {
            'circle_map': {
                arrayName: 'context',
                nodeName: 'context node',
                nodeNamePlural: 'context nodes',
                nodeType: 'context'
            },
            'bubble_map': {
                arrayName: 'attributes',
                nodeName: 'attribute',
                nodeNamePlural: 'attributes',
                nodeType: 'attribute'
            },
            'double_bubble_map': {
                // Multi-array support with tabs
                arrays: {
                    'similarities': {
                        nodeName: 'similarity',
                        nodeNamePlural: 'similarities',
                        nodeType: 'similarity'
                    },
                    'left_differences': {
                        nodeName: 'left difference',
                        nodeNamePlural: 'left differences',
                        nodeType: 'left_difference'
                    },
                    'right_differences': {
                        nodeName: 'right difference',
                        nodeNamePlural: 'right differences',
                        nodeType: 'right_difference'
                    }
                },
                // Default array for backward compatibility
                arrayName: 'similarities',
                nodeName: 'similarity',
                nodeNamePlural: 'similarities',
                nodeType: 'similarity',
                useTabs: true  // Enable tab UI
            },
            'tree_map': {
                // Multi-stage workflow with tabs for dimensions -> categories -> children
                arrays: {
                    'dimensions': {
                        nodeName: 'dimension',
                        nodeNamePlural: 'dimensions',
                        nodeType: 'dimension'
                    },
                    'categories': {
                        nodeName: 'category',
                        nodeNamePlural: 'categories',
                        nodeType: 'category'
                    },
                    'children': {
                        nodeName: 'child',
                        nodeNamePlural: 'children',
                        nodeType: 'child'
                    }
                },
                // Default array for backward compatibility
                arrayName: 'items',
                nodeName: 'item',
                nodeNamePlural: 'items',
                nodeType: 'leaf',
                useTabs: true,  // Enable tab UI
                useStages: true  // Enable multi-stage workflow
            },
            'mindmap': {
                // Multi-stage workflow: branches (Stage 1) -> children (Stage 2, dynamic tabs per branch)
                arrays: {
                    'branches': {
                        nodeName: 'branch',
                        nodeNamePlural: 'branches',
                        nodeType: 'branch',
                        parentField: 'topic'  // branches connect to topic
                    },
                    'children': {
                        nodeName: 'child',
                        nodeNamePlural: 'children',
                        nodeType: 'child',
                        parentField: 'branch'  // children connect to branch
                    }
                },
                // Default array for backward compatibility
                arrayName: 'children',
                nodeName: 'branch',
                nodeNamePlural: 'branches',
                nodeType: 'branch',
                useTabs: true,  // Enable tab UI
                useStages: true  // Enable multi-stage workflow (branches -> children)
            },
            'flow_map': {
                // Multi-stage workflow: dimensions → steps → substeps (per step)
                arrays: {
                    'dimensions': {
                        nodeName: 'dimension',
                        nodeNamePlural: 'dimensions',
                        nodeType: 'dimension'
                    },
                    'steps': {
                        nodeName: 'step',
                        nodeNamePlural: 'steps',
                        nodeType: 'step'
                    },
                    'substeps': {
                        nodeName: 'substep',
                        nodeNamePlural: 'substeps',
                        nodeType: 'substep',
                        parentField: 'step'  // substeps connect to steps
                    }
                },
                arrayName: 'steps',
                nodeName: 'step',
                nodeNamePlural: 'steps',
                nodeType: 'step',
                useTabs: true,  // Enable tab UI for multi-stage
                useStages: true  // Enable 3-stage workflow (dimensions → steps → substeps)
            },
            'multi_flow_map': {
                // Multi-array support with tabs
                arrays: {
                    'causes': {
                        nodeName: 'cause',
                        nodeNamePlural: 'causes',
                        nodeType: 'cause'
                    },
                    'effects': {
                        nodeName: 'effect',
                        nodeNamePlural: 'effects',
                        nodeType: 'effect'
                    }
                },
                // Default array for backward compatibility
                arrayName: 'effects',
                nodeName: 'effect',
                nodeNamePlural: 'effects',
                nodeType: 'effect',
                useTabs: true  // Enable tab UI
            },
            'brace_map': {
                arrays: {
                    'dimensions': {
                        nodeName: 'dimension',
                        nodeNamePlural: 'dimensions',
                        nodeType: 'dimension'
                    },
                    'parts': {
                        nodeName: 'part',
                        nodeNamePlural: 'parts',
                        nodeType: 'part'
                    }
                    // Dynamic tabs for sub-parts will be added at runtime
                },
                arrayName: 'parts',  // Default for backward compatibility
                nodeName: 'part',
                nodeNamePlural: 'parts',
                nodeType: 'part',
                useTabs: true,  // Enable tabs for multi-stage workflow
                useStages: true  // Enable stage-based generation
            },
            'bridge_map': {
                arrayName: 'analogies',
                nodeName: 'analogy',
                nodeNamePlural: 'analogies',
                nodeType: 'analogy'
            },
            'concept_map': {
                arrayName: 'concepts',
                nodeName: 'concept',
                nodeNamePlural: 'concepts',
                nodeType: 'concept'
            }
        };
        
        console.log('[NodePalette] Initialized with support for:', Object.keys(this.diagramMetadata).join(', '));
    }
    
    /**
     * Get diagram-specific metadata (node terminology, array names, etc.)
     */
    getMetadata(diagramType = null) {
        const type = diagramType || this.diagramType || 'circle_map';
        return this.diagramMetadata[type] || this.diagramMetadata['circle_map'];
    }
    
    /**
     * Check if a node text is a template placeholder.
     * Uses centralized DiagramValidator for comprehensive pattern matching.
     * 
     * @param {string} text - Node text to check
     * @returns {boolean} True if text matches placeholder pattern
     */
    isPlaceholder(text) {
        if (!text || typeof text !== 'string') {
            return false;
        }
        
        // Use DiagramValidator's centralized placeholder detection
        // Access validator through editor's toolbar manager
        const validator = window.currentEditor?.toolbarManager?.validator;
        if (!validator) {
            console.warn('[NodePalette] DiagramValidator not found, using fallback placeholder detection');
            // Fallback: basic pattern matching that covers common placeholders
            return /^(Context|背景|New|新|属性|Attribute)\s*\d*$/i.test(text.trim());
        }
        
        return validator.isPlaceholderText(text);
    }
    
    /**
     * Check if current diagram uses tabs (double bubble map, multi flow map, tree map)
     */
    usesTabs() {
        const metadata = this.getMetadata();
        return metadata.useTabs === true;
    }
    
    /**
     * Check if current diagram uses multi-stage workflow (tree map)
     */
    usesStages() {
        const metadata = this.getMetadata();
        return metadata.useStages === true;
    }
    
    /**
     * Check if a tab is locked (cannot be modified in tree map workflow)
     */
    isTabLocked(tabName) {
        return this.lockedTabs.has(tabName);
    }
    
    /**
     * Lock a tab (prevent further modifications)
     */
    lockTab(tabName) {
        this.lockedTabs.add(tabName);
        console.log(`[NodePalette] Tab locked: ${tabName}`);
        this.updateTabLockUI(tabName);
    }
    
    /**
     * Update UI to show tab as locked (read-only mode)
     * User can still click to view but cannot modify selections
     */
    updateTabLockUI(tabName) {
        const tabBtn = document.getElementById(`tab-${tabName}`);
        if (tabBtn) {
            tabBtn.classList.add('locked');
            // Don't disable - allow viewing in read-only mode
            // tabBtn.disabled = true;
            // Add lock icon if not already present
            if (!tabBtn.querySelector('.lock-icon')) {
                const lockIcon = document.createElement('span');
                lockIcon.className = 'lock-icon';
                lockIcon.innerHTML = ' 🔒';
                tabBtn.appendChild(lockIcon);
            }
        }
    }
    
    /**
     * Advance to next stage in tree map workflow
     * Called when user clicks "Next" button
     */
    async advanceToNextStage() {
        if (!this.usesStages()) {
            console.warn('[NodePalette] advanceToNextStage called on non-staged diagram');
            return;
        }
        
        console.log(`[NodePalette-TreeMap] Advancing from stage: ${this.currentStage}`);
        
        // Validate that user has selected something
        if (this.selectedNodes.size === 0) {
            const metadata = this.getMetadata();
            const currentArrayMetadata = metadata.arrays[this.currentTab];
            const nodeName = currentArrayMetadata?.nodeNamePlural || 'items';
            alert(`Please select at least one ${nodeName.slice(0, -1)} before proceeding.`);
            return;
        }
        
        // Get selected node texts
        const selectedTexts = Array.from(this.selectedNodes).map(nodeId => {
            const node = this.nodes.find(n => n.id === nodeId);
            return node ? node.text : null;
        }).filter(text => text !== null);
        
        console.log(`[NodePalette-TreeMap] Selected ${selectedTexts.length} items:`, selectedTexts);
        
        // Determine next stage and update state
        if (this.currentStage === 'dimensions') {
            // Stage 1 → Stage 2: User selected a dimension
            const selectedDimension = selectedTexts[0]; // User should select only one dimension
            
            // Lock dimension tab
            this.lockTab('dimensions');
            
            // Save selected dimension to stage data
            this.stageData.dimension = selectedDimension;
            
            // Move to categories stage
            this.currentStage = 'categories';
            this.currentTab = 'categories';
            this.stageGeneration++;  // Invalidate old batches from previous stage
            
            // Abort any in-flight batch from previous stage
            if (this.currentBatchAbortController) {
                console.log('[NodePalette-TreeMap] Aborting in-flight batch from previous stage');
                this.currentBatchAbortController.abort();
                this.currentBatchAbortController = null;
            }
            this.isLoadingBatch = false;  // Allow new batch to start immediately
            
            console.log(`[NodePalette-TreeMap] Stage 1→2: Dimension selected: "${selectedDimension}" | Stage generation: ${this.stageGeneration}`);
            
            // Clear current nodes and reset batch count for new stage
            this.nodes = [];
            this.tabNodes.categories = [];
            this.selectedNodes.clear();
            this.tabSelectedNodes.categories = new Set();
            this.currentBatch = 0;
            
            // Show stage transition animation
            this.showStageTransition('Stage 2: Generate Categories');
            
            // Update button text
            this.updateStageProgressButton();
            
            // Switch to categories tab (will auto-load if empty)
            this.switchTab('categories');
            
        } else if (this.currentStage === 'categories') {
            // Stage 2 → Stage 3: User selected categories
            const selectedCategories = selectedTexts;
            
            // Lock categories tab
            this.lockTab('categories');
            
            // Save selected categories to stage data
            this.stageData.categories = selectedCategories;
            
            // Move to children stage
            this.currentStage = 'children';
            this.stageGeneration++;  // Invalidate old batches from previous stage
            
            // Abort any in-flight batch from previous stage
            if (this.currentBatchAbortController) {
                console.log('[NodePalette-TreeMap] Aborting in-flight batch from previous stage');
                this.currentBatchAbortController.abort();
                this.currentBatchAbortController = null;
            }
            this.isLoadingBatch = false;  // Allow new batch to start immediately
            
            console.log(`[NodePalette-TreeMap] Stage 2→3: Categories selected: ${selectedCategories.length} items`);
            console.log(`[NodePalette-TreeMap] Categories:`, selectedCategories);
            
            // DYNAMIC TAB CREATION: Create one tab per category
            console.log(`[NodePalette-TreeMap] Creating ${selectedCategories.length} dynamic tabs for categories...`);
            
            // Initialize tab storage for each category
            const newTabNodes = {};
            const newTabSelectedNodes = {};
            const newTabScrollPositions = {};
            
            selectedCategories.forEach(categoryName => {
                newTabNodes[categoryName] = [];
                newTabSelectedNodes[categoryName] = new Set();
                newTabScrollPositions[categoryName] = 0;
            });
            
            // Merge with existing tabs (keep dimensions and categories locked tabs)
            this.tabNodes = {
                dimensions: this.tabNodes.dimensions || [],
                categories: this.tabNodes.categories || [],
                ...newTabNodes
            };
            this.tabSelectedNodes = {
                dimensions: this.tabSelectedNodes.dimensions || new Set(),
                categories: this.tabSelectedNodes.categories || new Set(),
                ...newTabSelectedNodes
            };
            this.tabScrollPositions = {
                dimensions: this.tabScrollPositions.dimensions || 0,
                categories: this.tabScrollPositions.categories || 0,
                ...newTabScrollPositions
            };
            
            // Set current tab to first category
            this.currentTab = selectedCategories[0];
            console.log(`[NodePalette-TreeMap] Current tab set to: ${this.currentTab}`);
            
            // Clear current nodes and reset batch count
            this.nodes = [];
            this.selectedNodes.clear();
            this.currentBatch = 0;
            
            // Rebuild tabs UI with dynamic category tabs
            this.showDynamicCategoryTabsUI(selectedCategories);
            
            // Attach listeners for new tabs
            this.attachTabButtonListeners();
            
            // Show stage transition animation
            this.showStageTransition(`Stage 3: Add Items to ${selectedCategories.length} Categories`);
            
            // Update button text
            this.updateStageProgressButton();
            
            // Fire N catapults simultaneously (one per category)
            console.log(`[NodePalette-TreeMap] 🚀 Firing ${selectedCategories.length} catapults simultaneously!`);
            await this.loadAllCategoryTabsInitial(selectedCategories);
            
        } else if (this.currentStage === 'children') {
            // Stage 3 → Complete: User selected children, ready to add to diagram
            console.log(`[NodePalette-TreeMap] Stage 3: Children selected, completing workflow`);
            
            // Lock children tab
            this.lockTab('children');
            
            // At this point, user can call finish() to add nodes to diagram
            // Or they can continue selecting children for other categories
            // For now, we'll just let them click "Finish" to complete
        }
        
        // Update button text
        this.updateStageProgressButton();
    }
    
    /**
     * Advance Brace Map to next stage (similar to tree map workflow)
     */
    async advanceBraceMapToNextStage() {
        if (this.diagramType !== 'brace_map') {
            console.error('[NodePalette-BraceMap] advanceBraceMapToNextStage() called for non-brace-map diagram!');
            return;
        }
        
        console.log(`[NodePalette-BraceMap] Advancing from stage: ${this.currentStage}`);
        
        // Validate that user has selected something
        if (this.selectedNodes.size === 0) {
            const metadata = this.getMetadata();
            const currentArrayMetadata = metadata.arrays[this.currentTab];
            const nodeName = currentArrayMetadata?.nodeNamePlural || 'items';
            alert(`Please select at least one ${nodeName.slice(0, -1)} before proceeding.`);
            return;
        }
        
        // Get selected node texts
        const selectedTexts = Array.from(this.selectedNodes).map(nodeId => {
            const node = this.nodes.find(n => n.id === nodeId);
            return node ? node.text : null;
        }).filter(text => text !== null);
        
        console.log(`[NodePalette-BraceMap] Selected ${selectedTexts.length} items:`, selectedTexts);
        
        // Determine next stage and update state
        if (this.currentStage === 'dimensions') {
            // Stage 1 → Stage 2: User selected a dimension
            const selectedDimension = selectedTexts[0]; // User should select only one dimension
            
            // Lock dimension tab
            this.lockTab('dimensions');
            
            // Save selected dimension to stage data
            this.stageData.dimension = selectedDimension;
            
            // Move to parts stage
            this.currentStage = 'parts';
            this.currentTab = 'parts';
            this.stageGeneration++;  // Invalidate old batches from previous stage
            
            // Abort any in-flight batch from previous stage
            if (this.currentBatchAbortController) {
                console.log('[NodePalette-BraceMap] Aborting in-flight batch from previous stage');
                this.currentBatchAbortController.abort();
                this.currentBatchAbortController = null;
            }
            this.isLoadingBatch = false;  // Allow new batch to start immediately
            
            console.log(`[NodePalette-BraceMap] Stage 1→2: Dimension selected: "${selectedDimension}" | Stage generation: ${this.stageGeneration}`);
            
            // Clear current nodes and reset batch count for new stage
            this.nodes = [];
            this.tabNodes.parts = [];
            this.selectedNodes.clear();
            this.tabSelectedNodes.parts = new Set();
            this.currentBatch = 0;
            
            // Show stage transition animation
            this.showStageTransition('Stage 2: Generate Parts');
            
            // Update button text
            this.updateStageProgressButton();
            
            // Switch to parts tab (will auto-load if empty)
            this.switchTab('parts');
            
        } else if (this.currentStage === 'parts') {
            // Stage 2 → Stage 3: User selected parts
            const selectedParts = selectedTexts;
            
            // Lock parts tab
            this.lockTab('parts');
            
            // Save selected parts to stage data
            this.stageData.parts = selectedParts;
            
            // Move to subparts stage
            this.currentStage = 'subparts';
            this.stageGeneration++;  // Invalidate old batches from previous stage
            
            // Abort any in-flight batch from previous stage
            if (this.currentBatchAbortController) {
                console.log('[NodePalette-BraceMap] Aborting in-flight batch from previous stage');
                this.currentBatchAbortController.abort();
                this.currentBatchAbortController = null;
            }
            this.isLoadingBatch = false;  // Allow new batch to start immediately
            
            console.log(`[NodePalette-BraceMap] Stage 2→3: Parts selected: ${selectedParts.length} items`);
            console.log(`[NodePalette-BraceMap] Parts:`, selectedParts);
            
            // DYNAMIC TAB CREATION: Create one tab per part
            console.log(`[NodePalette-BraceMap] Creating ${selectedParts.length} dynamic tabs for parts...`);
            
            // Initialize tab storage for each part
            const newTabNodes = {};
            const newTabSelectedNodes = {};
            const newTabScrollPositions = {};
            
            selectedParts.forEach(partName => {
                newTabNodes[partName] = [];
                newTabSelectedNodes[partName] = new Set();
                newTabScrollPositions[partName] = 0;
            });
            
            // Merge with existing tabs (keep dimensions and parts locked tabs)
            this.tabNodes = {
                dimensions: this.tabNodes.dimensions || [],
                parts: this.tabNodes.parts || [],
                ...newTabNodes
            };
            this.tabSelectedNodes = {
                dimensions: this.tabSelectedNodes.dimensions || new Set(),
                parts: this.tabSelectedNodes.parts || new Set(),
                ...newTabSelectedNodes
            };
            this.tabScrollPositions = {
                dimensions: this.tabScrollPositions.dimensions || 0,
                parts: this.tabScrollPositions.parts || 0,
                ...newTabScrollPositions
            };
            
            // Switch UI to dynamic part tabs
            this.showDynamicCategoryTabsUI(selectedParts);
            
            // Attach listeners for new tabs
            this.attachTabButtonListeners();
            
            // Set current tab to first part
            this.currentTab = selectedParts[0];
            this.switchTab(selectedParts[0]);
            
            // Update button text
            this.updateStageProgressButton();
            
            // Fire N catapults simultaneously (one per part)
            console.log(`[NodePalette-BraceMap] 🚀 Firing ${selectedParts.length} catapults simultaneously!`);
            await this.loadAllCategoryTabsInitial(selectedParts);
            
        } else if (this.currentStage === 'subparts') {
            // Stage 3 → Complete: User selected subparts, ready to add to diagram
            console.log(`[NodePalette-BraceMap] Stage 3: Subparts selected, completing workflow`);
            
            // Lock subparts tab
            this.lockTab('subparts');
            
            // At this point, user can call finish() to add nodes to diagram
            // Or they can continue selecting subparts for other parts
            // For now, we'll just let them click "Finish" to complete
        }
        
        // Update button text
        this.updateStageProgressButton();
    }
    
    /**
     * Advance Mindmap to next stage (similar to tree map workflow)
     */
    async advanceMindMapToNextStage() {
        if (this.diagramType !== 'mindmap') {
            console.warn('[NodePalette] advanceMindMapToNextStage called on non-mindmap diagram');
            return;
        }
        
        // Get selected nodes text
        const selectedTexts = Array.from(this.selectedNodes)
            .map(id => this.nodes.find(n => n.id === id))
            .filter(node => node && node.text)
            .map(node => node.text);
        
        if (selectedTexts.length === 0) {
            alert('Please select at least one branch before proceeding.');
            return;
        }
        
        if (this.currentStage === 'branches') {
            // Stage 1 → Stage 2: User selected branches
            const selectedBranches = selectedTexts;
            
            // Lock branches tab
            this.lockTab('branches');
            
            // Save selected branches to stage data
            this.stageData.branches = selectedBranches;
            
            // Move to children stage
            this.currentStage = 'children';
            
            console.log(`[NodePalette-Mindmap] Stage 1→2: Branches selected: ${selectedBranches.length} items`);
            console.log(`[NodePalette-Mindmap] Branches:`, selectedBranches);
            
            // DYNAMIC TAB CREATION: Create one tab per branch
            console.log(`[NodePalette-Mindmap] Creating ${selectedBranches.length} dynamic tabs for branches...`);
            
            // Initialize tab storage for each branch
            const newTabNodes = {};
            const newTabSelectedNodes = {};
            const newTabScrollPositions = {};
            selectedBranches.forEach(branchName => {
                newTabNodes[branchName] = [];
                newTabSelectedNodes[branchName] = new Set();
                newTabScrollPositions[branchName] = 0;
            });
            
            // Preserve locked tab data
            this.tabNodes = {
                branches: this.tabNodes.branches || [],
                ...newTabNodes
            };
            this.tabSelectedNodes = {
                branches: this.tabSelectedNodes.branches || new Set(),
                ...newTabSelectedNodes
            };
            this.tabScrollPositions = {
                branches: 0,
                ...newTabScrollPositions
            };
            
            // Switch to first branch tab
            this.currentTab = selectedBranches[0];
            
            // Clear current nodes
            this.nodes = [];
            this.selectedNodes.clear();
            
            // Update UI to show dynamic tabs
            this.showDynamicCategoryTabsUI(selectedBranches);
            this.attachTabButtonListeners();
            this.updateTabButtons();
            
            // Load ALL branch tabs simultaneously - fire catapults for each!
            console.log(`[NodePalette-Mindmap] Loading ALL ${selectedBranches.length} branch tabs in parallel...`);
            await this.loadAllBranchTabsInitial(selectedBranches);
            
        } else if (this.currentStage === 'children') {
            // Stage 2 → Complete: User selected children, ready to add to diagram
            console.log(`[NodePalette-Mindmap] Stage 2: Children selected, completing workflow`);
            
            // Lock children tab
            this.lockTab(this.currentTab);
            
            // At this point, user can call finish() to add nodes to diagram
            // Or they can continue selecting children for other branches
            // For now, we'll just let them click "Finish" to complete
        }
        
        // Update button text
        this.updateStageProgressButton();
    }
    
    /**
     * Advance Flow Map to next stage (similar to tree map workflow)
     */
    async advanceFlowMapToNextStage() {
        if (this.diagramType !== 'flow_map') {
            console.error('[NodePalette-FlowMap] advanceFlowMapToNextStage() called for non-flow-map diagram!');
            return;
        }
        
        console.log(`[NodePalette-FlowMap] Advancing from stage: ${this.currentStage}`);
        
        // Validate that user has selected something
        if (this.selectedNodes.size === 0) {
            const metadata = this.getMetadata();
            const currentArrayMetadata = metadata.arrays[this.currentTab];
            const nodeName = currentArrayMetadata?.nodeNamePlural || 'items';
            alert(`Please select at least one ${nodeName.slice(0, -1)} before proceeding.`);
            return;
        }
        
        if (this.currentStage === 'dimensions') {
            // Stage 1 → Stage 2: User selected a dimension
            
            // Validate: exactly 1 dimension should be selected
            if (this.selectedNodes.size !== 1) {
                alert('Please select exactly ONE dimension to proceed.');
                return;
            }
            
            const selectedDimension = Array.from(this.selectedNodes)
                .map(id => this.nodes.find(n => n.id === id))
                .filter(node => node && node.text)
                .map(node => node.text)[0];
            
            console.log(`[NodePalette-FlowMap] Stage 1 → Stage 2: Dimension selected = "${selectedDimension}"`);
            
            // Update stage
            this.currentStage = 'steps';
            this.stageData.dimension = selectedDimension;
            this.stageGeneration++;  // Invalidate old batches from previous stage
            
            // Abort any in-flight batch from previous stage
            if (this.currentBatchAbortController) {
                console.log('[NodePalette-FlowMap] Aborting in-flight batch from previous stage');
                this.currentBatchAbortController.abort();
                this.currentBatchAbortController = null;
            }
            this.isLoadingBatch = false;  // Allow new batch to start immediately
            
            // Lock dimensions tab
            this.lockTab('dimensions');
            
            // Clear current nodes and reset batch count for new stage
            this.nodes = [];
            this.tabNodes.steps = [];
            this.selectedNodes.clear();
            this.tabSelectedNodes.steps = new Set();
            this.currentBatch = 0;
            
            // Show stage transition
            this.showStageTransition(`Stage 2: Generate Steps based on "${selectedDimension}"`);
            
            // Update button text
            this.updateStageProgressButton();
            
            // Switch to steps tab (will auto-load if empty)
            this.switchTab('steps');
            
        } else if (this.currentStage === 'steps') {
            // Stage 2 → Stage 3: User selected steps
            
            const selectedSteps = Array.from(this.selectedNodes)
                .map(id => this.nodes.find(n => n.id === id))
                .filter(node => node && node.text)
                .map(node => node.text);
            
            console.log(`[NodePalette-FlowMap] Stage 2 → Stage 3: ${selectedSteps.length} steps selected`);
            console.log(`[NodePalette-FlowMap]   Steps: ${selectedSteps.join(', ')}`);
            
            // Update stage
            this.currentStage = 'substeps';
            this.stageData.steps = selectedSteps;
            this.stageGeneration++;  // Invalidate old batches from previous stage
            
            // Abort any in-flight batch from previous stage
            if (this.currentBatchAbortController) {
                console.log('[NodePalette-FlowMap] Aborting in-flight batch from previous stage');
                this.currentBatchAbortController.abort();
                this.currentBatchAbortController = null;
            }
            this.isLoadingBatch = false;  // Allow new batch to start immediately
            
            // Lock steps tab
            this.lockTab('steps');
            
            // Clear selected nodes
            this.selectedNodes.clear();
            
            // Create tabs for each selected step (dynamic tabs)
            const dynamicTabNodes = {};
            const dynamicTabSelectedNodes = {};
            const dynamicTabScrollPositions = {};
            
            selectedSteps.forEach(stepName => {
                dynamicTabNodes[stepName] = [];
                dynamicTabSelectedNodes[stepName] = new Set();
                dynamicTabScrollPositions[stepName] = 0;
            });
            
            // Include locked tabs from previous stages
            this.tabNodes = {
                dimensions: this.tabNodes.dimensions || [],
                steps: this.tabNodes.steps || [],
                ...dynamicTabNodes
            };
            this.tabSelectedNodes = {
                dimensions: this.tabSelectedNodes.dimensions || new Set(),
                steps: this.tabSelectedNodes.steps || new Set(),
                ...dynamicTabSelectedNodes
            };
            this.tabScrollPositions = {
                dimensions: 0,
                steps: 0,
                ...dynamicTabScrollPositions
            };
            
            console.log(`[NodePalette-FlowMap] Created ${selectedSteps.length} dynamic step tabs:`, selectedSteps);
            
            // Set current tab to first step
            this.currentTab = selectedSteps[0];
            
            // Show dynamic tabs UI
            this.showDynamicCategoryTabsUI(selectedSteps);
            
            // Attach listeners for new tabs
            this.attachTabButtonListeners();
            
            // Set current tab to first step
            this.currentTab = selectedSteps[0];
            this.switchTab(selectedSteps[0]);
            
            // Update button text
            this.updateStageProgressButton();
            
            // Fire N catapults simultaneously (one per step)
            console.log(`[NodePalette-FlowMap] 🚀 Firing ${selectedSteps.length} catapults simultaneously!`);
            await this.loadAllCategoryTabsInitial(selectedSteps);
            
        } else if (this.currentStage === 'substeps') {
            // Stage 3 → Complete: User selected substeps, ready to add to diagram
            console.log(`[NodePalette-FlowMap] Stage 3: Substeps selected, completing workflow`);
            
            // Lock substeps tab
            this.lockTab('substeps');
            
            // At this point, user can call finish() to add nodes to diagram
            // Or they can continue selecting substeps for other steps
            // For now, we'll just let them click "Finish" to complete
        }
        
        // Update button text
        this.updateStageProgressButton();
    }
    
    /**
     * Update the Finish/Next button based on current stage
     */
    updateStageProgressButton() {
        const finishBtn = document.querySelector('.node-palette-finish-btn');
        if (!finishBtn || !this.usesStages()) return;
        
        if (this.diagramType === 'tree_map') {
            if (this.currentStage === 'dimensions') {
                finishBtn.textContent = '📐 Next: Select Dimension →';
            } else if (this.currentStage === 'categories') {
                finishBtn.textContent = '📂 Next: Select Categories →';
            } else if (this.currentStage === 'children') {
                finishBtn.textContent = '✅ Finish Selection';
            }
        } else if (this.diagramType === 'brace_map') {
            if (this.currentStage === 'dimensions') {
                finishBtn.textContent = '📐 Next: Select Dimension →';
            } else if (this.currentStage === 'parts') {
                finishBtn.textContent = '🧩 Next: Select Parts →';
            } else if (this.currentStage === 'subparts') {
                finishBtn.textContent = '✅ Finish Selection';
            }
        } else if (this.diagramType === 'mindmap') {
            if (this.currentStage === 'branches') {
                finishBtn.textContent = '🌿 Next: Select Branches →';
            } else if (this.currentStage === 'children') {
                finishBtn.textContent = '✅ Finish Selection';
            }
        } else if (this.diagramType === 'flow_map') {
            if (this.currentStage === 'dimensions') {
                finishBtn.textContent = '📐 Next: Select Dimension →';
            } else if (this.currentStage === 'steps') {
                finishBtn.textContent = '📝 Next: Select Steps →';
            } else if (this.currentStage === 'substeps') {
                finishBtn.textContent = '✅ Finish Selection';
            }
        }
    }
    
    /**
     * Show stage transition animation
     * @param {string} stageName - Name of the stage being entered
     */
    showStageTransition(stageName) {
        console.log(`[NodePalette-TreeMap] Stage transition: ${stageName}`);
        
        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'stage-transition-overlay';
        overlay.innerHTML = `
            <div class="stage-transition-content">
                <div class="stage-transition-icon">🚀</div>
                <div class="stage-transition-text">${stageName}</div>
                <div class="stage-transition-subtext">Firing catapults...</div>
            </div>
        `;
        
        // Add to palette container
        const container = document.getElementById('node-palette-container');
        if (container) {
            container.appendChild(overlay);
            
            // Fade in
            setTimeout(() => {
                overlay.style.opacity = '1';
            }, 10);
            
            // Fade out after 1.5 seconds
            setTimeout(() => {
                overlay.style.opacity = '0';
                setTimeout(() => {
                    overlay.remove();
                }, 300);
            }, 1500);
        }
    }
    
    /**
     * Switch between tabs with elegant transition (double bubble only)
     */
    switchTab(tabName) {
        if (!this.usesTabs()) return;
        
        // Verify DOM state matches internal state (defensive check for desync)
        const similaritiesBtn = document.getElementById('tab-similarities');
        const differencesBtn = document.getElementById('tab-differences');
        
        const isDomSimilaritiesActive = similaritiesBtn?.classList.contains('active');
        const isDomDifferencesActive = differencesBtn?.classList.contains('active');
        
        // Check if internal state matches DOM state
        const expectedDomState = this.currentTab === 'similarities' ? isDomSimilaritiesActive : isDomDifferencesActive;
        const isDesync = !expectedDomState;
        
        if (isDesync) {
            console.warn(`[NodePalette] STATE DESYNC DETECTED!`);
            console.warn(`  Internal state: currentTab="${this.currentTab}"`);
            console.warn(`  DOM state: similarities=${isDomSimilaritiesActive}, differences=${isDomDifferencesActive}`);
            console.warn(`  User clicked: ${tabName}`);
            console.warn(`  Allowing switch to proceed to fix desync...`);
        }
        
        // Don't switch if already on this tab AND DOM is synced
        // But DO switch if there's a desync (to fix it)
        if (this.currentTab === tabName && !isDesync) {
            console.log(`[NodePalette] Already on ${tabName} tab, ignoring`);
            return;
        }
        
        console.log('[NodePalette] ========================================');
        console.log(`[NodePalette] TAB SWITCH: ${this.currentTab} → ${tabName}`);
        console.log('[NodePalette] ========================================');
        
        // Save current tab state (preserve user progress)
        const container = document.getElementById('node-palette-container');
        const currentScrollPos = container ? container.scrollTop : 0;
        
        console.log(`[NodePalette] Saving ${this.currentTab} state:`);
        console.log(`  - Nodes: ${this.nodes.length}`);
        console.log(`  - Selected: ${this.selectedNodes.size}`);
        console.log(`  - Scroll position: ${currentScrollPos}px`);
        
        this.tabNodes[this.currentTab] = [...this.nodes];
        this.tabSelectedNodes[this.currentTab] = new Set(this.selectedNodes);
        this.tabScrollPositions[this.currentTab] = currentScrollPos;
        
        // Fade out current grid
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.style.opacity = '0';
            grid.style.transform = 'translateY(10px)';
        }
        
        // Wait for fade out, then switch
        setTimeout(() => {
            // Switch to new tab
            this.currentTab = tabName;
            
            // Restore new tab state
            this.nodes = [...(this.tabNodes[tabName] || [])];
            
            // CRITICAL: Restore tab-specific selections to global selectedNodes
            // This ensures the UI shows correct selection state
            this.selectedNodes = new Set(this.tabSelectedNodes[tabName] || new Set());
            const savedScrollPos = this.tabScrollPositions[tabName] || 0;
            
            console.log(`[NodePalette] Restored ${tabName} state:`);
            console.log(`  - Nodes: ${this.nodes.length}`);
            console.log(`  - Selected: ${this.selectedNodes.size}`);
            console.log(`  - Selected IDs: ${Array.from(this.selectedNodes).join(', ') || 'none'}`);
            console.log(`  - Scroll position: ${savedScrollPos}px`);
            
            // Update UI
            this.renderTabNodes();
            this.updateTabButtons();
            this.updateSelectionCounter();
            
            // Restore scroll position for this tab
            if (container) {
                container.scrollTop = savedScrollPos;
            }
            
            // If the new tab has no nodes yet, CATAPULT!
            if (this.nodes.length === 0) {
                console.log(`[NodePalette] New tab empty, CATAPULT for ${tabName}...`);
                this.currentBatch = 0; // Reset batch counter for this tab
                this.loadNextBatch();
            }
            
            // Fade in new grid
            if (grid) {
                setTimeout(() => {
                    grid.style.transition = 'opacity 0.3s, transform 0.3s';
                    grid.style.opacity = '1';
                    grid.style.transform = 'translateY(0)';
                }, 10);
            }
            
            console.log(`[NodePalette] ✓ Tab switch complete: ${tabName}`);
        }, 300);
    }
    
    /**
     * Render nodes for current tab
     */
    renderTabNodes() {
        const grid = document.getElementById('node-palette-grid');
        if (!grid) return;
        
        // Clear grid
        grid.innerHTML = '';
        
        // Render nodes with explicit mode filtering
        this.nodes.forEach(node => {
            // For tab-based diagrams: verify node mode matches current tab
            if (this.usesTabs() && node.mode) {
                if (node.mode !== this.currentTab) {
                    console.warn(`[NodePalette] Skipping node with wrong mode - tab: ${this.currentTab}, node: ${node.mode}, id: ${node.id}`);
                    return; // Skip
                }
            }
            
            this.renderNodeCardOnly(node);
        });
    }
    
    /**
     * Update tab button states with elegant animations
     */
    updateTabButtons() {
        const tabsContainer = document.querySelector('.palette-tabs');
        if (!tabsContainer || !this.tabNodes) return;
        
        const tabNames = Object.keys(this.tabNodes);
        if (tabNames.length === 0) return;
        
        // Get all tab buttons dynamically
        const tabButtons = {};
        tabNames.forEach(name => {
            tabButtons[name] = document.getElementById(`tab-${name}`);
        });
        
        // Update active state for all tabs
        tabNames.forEach(name => {
            const button = tabButtons[name];
            if (button) {
                if (this.currentTab === name) {
                    button.classList.add('active');
                } else {
                    button.classList.remove('active');
                }
            }
        });
        
        // Update sliding indicator via data attribute
        tabsContainer.setAttribute('data-active', this.currentTab);
        
        // Dynamically calculate indicator width and position
        if (tabNames.length >= 2 && tabButtons[tabNames[0]] && tabButtons[tabNames[1]]) {
            const firstBtn = tabButtons[tabNames[0]];
            const secondBtn = tabButtons[tabNames[1]];
            const firstWidth = firstBtn.offsetWidth;
            const secondWidth = secondBtn.offsetWidth;
            const gap = 8; // Must match CSS gap
            
            // Set CSS variables for dynamic positioning
            if (this.currentTab === tabNames[0]) {
                tabsContainer.style.setProperty('--tab-indicator-width', `${firstWidth}px`);
                tabsContainer.style.setProperty('--tab-indicator-offset', `0px`);
            } else {
                tabsContainer.style.setProperty('--tab-indicator-width', `${secondWidth}px`);
                tabsContainer.style.setProperty('--tab-indicator-offset', `${firstWidth + gap}px`);
            }
        }
        
        // Update tab counters
        this.updateTabCounters();
    }
    
    /**
     * Update node counters in tab badges
     */
    updateTabCounters() {
        // Get all tab names from tabNodes
        const tabNames = Object.keys(this.tabNodes);
        
        tabNames.forEach(tabName => {
            const countElement = document.getElementById(`count-${tabName}`);
            if (countElement) {
                const count = this.tabNodes[tabName]?.length || 0;
                
                // Add suffix for differences tab in double bubble map
                let suffix = '';
                if (this.diagramType === 'double_bubble_map' && tabName === 'differences') {
                    suffix = ' pairs';
                }
                
                countElement.textContent = count > 0 ? `${count}${suffix}` : `0${suffix}`;
            }
        });
    }
    
    /**
     * Attach tab button click listeners
     */
    attachTabButtonListeners() {
        // Get all tab names from tabNodes
        const tabNames = Object.keys(this.tabNodes);
        
        tabNames.forEach(tabName => {
            const button = document.getElementById(`tab-${tabName}`);
            if (button) {
                // Remove old listener if exists (prevent duplicates)
                button.replaceWith(button.cloneNode(true));
                const newButton = document.getElementById(`tab-${tabName}`);
                
                newButton.addEventListener('click', () => {
                    console.log(`[NodePalette] User clicked ${tabName} tab`);
                    this.switchTab(tabName);
                });
            }
        });
        
        console.log(`[NodePalette] Attached listeners for tabs: ${tabNames.join(', ')}`);
    }
    
    /**
     * Show tabs UI (for double bubble map and multi flow map)
     */
    showTabsUI() {
        const tabsContainer = document.getElementById('node-palette-tabs');
        const paletteTabsDiv = tabsContainer?.querySelector('.palette-tabs');
        
        if (!tabsContainer || !paletteTabsDiv) {
            console.error('[NodePalette] Tabs container not found in DOM');
            return;
        }
        
        // Determine tab configuration based on diagram type
        let tabs = [];
        if (this.diagramType === 'double_bubble_map') {
            tabs = [
                { id: 'similarities', label: '🔗 Similarities', counterId: 'count-similarities', counterSuffix: '' },
                { id: 'differences', label: '⚖️ Differences', counterId: 'count-differences', counterSuffix: ' pairs' }
            ];
        } else if (this.diagramType === 'multi_flow_map') {
            tabs = [
                { id: 'causes', label: '⬅️ Causes', counterId: 'count-causes', counterSuffix: '' },
                { id: 'effects', label: '➡️ Effects', counterId: 'count-effects', counterSuffix: '' }
            ];
        } else if (this.diagramType === 'tree_map') {
            tabs = [
                { id: 'dimensions', label: '📐 Dimensions', counterId: 'count-dimensions', counterSuffix: '' },
                { id: 'categories', label: '📂 Categories', counterId: 'count-categories', counterSuffix: '' },
                { id: 'children', label: '📄 Items', counterId: 'count-children', counterSuffix: '' }
            ];
        } else if (this.diagramType === 'brace_map') {
            tabs = [
                { id: 'dimensions', label: '📐 Dimensions', counterId: 'count-dimensions', counterSuffix: '' },
                { id: 'parts', label: '🧩 Parts', counterId: 'count-parts', counterSuffix: '' }
            ];
        } else if (this.diagramType === 'mindmap') {
            tabs = [
                { id: 'branches', label: '🌿 Branches', counterId: 'count-branches', counterSuffix: '' }
            ];
        } else if (this.diagramType === 'flow_map') {
            tabs = [
                { id: 'dimensions', label: '📐 Dimensions', counterId: 'count-dimensions', counterSuffix: '' },
                { id: 'steps', label: '📝 Steps', counterId: 'count-steps', counterSuffix: '' }
            ];
        } else {
            console.warn('[NodePalette] Unknown diagram type for tabs:', this.diagramType);
            return;
        }
        
        // Clear existing tabs
        paletteTabsDiv.innerHTML = '';
        
        // Generate tab buttons
        tabs.forEach((tab, index) => {
            const button = document.createElement('button');
            button.id = `tab-${tab.id}`;
            button.className = `tab-button${index === 0 ? ' active' : ''}`;
            button.innerHTML = `
                ${tab.label}
                <span id="${tab.counterId}" class="tab-counter">0${tab.counterSuffix}</span>
            `;
            paletteTabsDiv.appendChild(button);
        });
        
        // Set data-active to first tab
        paletteTabsDiv.setAttribute('data-active', tabs[0].id);
        
        // Show container
        tabsContainer.style.display = 'flex';
        
        console.log(`[NodePalette] Tab switcher UI shown for ${this.diagramType} with ${tabs.length} tabs`);
    }
    
    /**
     * Show dynamic category tabs UI for Tree Map Stage 3 or Brace Map Stage 3
     * Creates one tab per selected category/part
     */
    showDynamicCategoryTabsUI(selectedCategories) {
        const tabsContainer = document.getElementById('node-palette-tabs');
        const paletteTabsDiv = tabsContainer?.querySelector('.palette-tabs');
        
        if (!tabsContainer || !paletteTabsDiv) {
            console.error('[NodePalette] Tabs container not found in DOM');
            return;
        }
        
        // Build tabs based on diagram type
        let tabs = [];
        let dynamicLabel = '📄';
        let logPrefix = '';
        
        if (this.diagramType === 'tree_map') {
            // Tree Map: Dimensions (locked) + Categories (locked) + Category tabs (active)
            tabs = [
                { id: 'dimensions', label: '📐 Dimensions', counterId: 'count-dimensions', counterSuffix: '', locked: true },
                { id: 'categories', label: '📂 Categories', counterId: 'count-categories', counterSuffix: '', locked: true }
            ];
            dynamicLabel = '📄';
            logPrefix = 'TreeMap';
        } else if (this.diagramType === 'brace_map') {
            // Brace Map: Dimensions (locked) + Parts (locked) + Part tabs (active)
            tabs = [
                { id: 'dimensions', label: '📐 Dimensions', counterId: 'count-dimensions', counterSuffix: '', locked: true },
                { id: 'parts', label: '🧩 Parts', counterId: 'count-parts', counterSuffix: '', locked: true }
            ];
            dynamicLabel = '🔧';
            logPrefix = 'BraceMap';
        } else if (this.diagramType === 'mindmap') {
            // Mindmap: Branches (locked) + Branch tabs (active)
            tabs = [
                { id: 'branches', label: '🌿 Branches', counterId: 'count-branches', counterSuffix: '', locked: true }
            ];
            dynamicLabel = '🌱';
            logPrefix = 'Mindmap';
        } else if (this.diagramType === 'flow_map') {
            // Flow Map: Dimensions (locked) + Steps (locked) + Step tabs (active)
            tabs = [
                { id: 'dimensions', label: '📐 Dimensions', counterId: 'count-dimensions', counterSuffix: '', locked: true },
                { id: 'steps', label: '📝 Steps', counterId: 'count-steps', counterSuffix: '', locked: true }
            ];
            dynamicLabel = '▶️';
            logPrefix = 'FlowMap';
        }
        
        // Add dynamic category/part/branch/step tabs
        selectedCategories.forEach((categoryName, index) => {
            tabs.push({
                id: categoryName,
                label: `${dynamicLabel} ${categoryName}`,
                counterId: `count-${categoryName}`,
                counterSuffix: '',
                locked: false
            });
        });
        
        // Clear existing tabs
        paletteTabsDiv.innerHTML = '';
        
        // Generate tab buttons
        tabs.forEach((tab, index) => {
            const button = document.createElement('button');
            button.id = `tab-${tab.id}`;
            // First category/part tab should be active
            const isActive = (tab.id === selectedCategories[0]);
            button.className = `tab-button${isActive ? ' active' : ''}${tab.locked ? ' locked' : ''}`;
            
            let innerHTML = `${tab.label}`;
            
            // Add lock icon if locked
            if (tab.locked) {
                innerHTML += ' <span class="lock-icon">🔒</span>';
            }
            
            // Add counter
            innerHTML += `<span id="${tab.counterId}" class="tab-counter">0${tab.counterSuffix}</span>`;
            
            button.innerHTML = innerHTML;
            paletteTabsDiv.appendChild(button);
        });
        
        // Set data-active to first category/part
        paletteTabsDiv.setAttribute('data-active', selectedCategories[0]);
        
        // Show container
        tabsContainer.style.display = 'flex';
        
        console.log(`[NodePalette-${logPrefix}] Dynamic tabs UI shown: ${tabs.length} tabs (2 locked + ${selectedCategories.length} dynamic tabs)`);
    }
    
    /**
     * Hide tabs UI (for other diagram types)
     */
    hideTabsUI() {
        const tabsContainer = document.getElementById('node-palette-tabs');
        if (tabsContainer) {
            tabsContainer.style.display = 'none';
        }
    }
    
    /**
     * Preload Node Palette data in background WITHOUT showing panel
     * Called by ThinkGuide when it opens to save time later
     */
    async preload(centerTopic, diagramData, sessionId, educationalContext, diagramType) {
        console.log('[NodePalette] ===== PRELOAD INITIATED =====');
        console.log(`[NodePalette] Topic: "${centerTopic}"`);
        console.log(`[NodePalette] Type: ${diagramType}`);
        
        // Store session info (same as start, but use provided sessionId)
        this.centerTopic = centerTopic;
        this.diagramData = diagramData;
        this.thinkingSessionId = sessionId;
        this.educationalContext = educationalContext;
        this.diagramType = diagramType;
        this.sessionId = sessionId;  // Use ThinkGuide's session ID for continuity
        
        // Initialize tabs for double bubble map and multi flow map
        if (this.usesTabs()) {
            // Determine tab names based on diagram type
            let firstTab, secondTab;
            if (this.diagramType === 'double_bubble_map') {
                firstTab = 'similarities';
                secondTab = 'differences';
            } else if (this.diagramType === 'multi_flow_map') {
                firstTab = 'causes';
                secondTab = 'effects';
            } else {
                // Fallback for future tab-enabled diagrams
                firstTab = 'tab1';
                secondTab = 'tab2';
            }
            
            this.currentTab = firstTab;
            this.tabNodes = {
                [firstTab]: [],
                [secondTab]: []
            };
            this.tabSelectedNodes = {
                [firstTab]: new Set(),
                [secondTab]: new Set()
            };
            this.tabScrollPositions = {
                [firstTab]: 0,
                [secondTab]: 0
            };
            
            console.log(`[NodePalette] Tabs initialized for ${this.diagramType}: ${firstTab} and ${secondTab}`);
        }
        
        // Fire the catapult in background!
        console.log('[NodePalette] Firing catapult in background (no UI shown)...');
        
        if (this.usesTabs()) {
            // Double bubble / multi flow: load both tabs
            console.log(`[NodePalette] Tab-based diagram detected - firing BOTH catapults!`);
            await this.loadBothTabsInitial();
        } else {
            // Other diagrams: load single batch
            await this.loadNextBatch();
        }
        
        console.log('[NodePalette] ===== PRELOAD COMPLETE =====');
        if (this.tabNodes) {
            const tabNames = Object.keys(this.tabNodes);
            tabNames.forEach(tabName => {
                const count = this.tabNodes[tabName]?.length || 0;
                console.log(`[NodePalette] ${tabName} tab: ${count} nodes cached`);
            });
        }
        console.log(`[NodePalette] Total: ${this.nodes.length} nodes cached and ready!`);
    }
    
    async start(centerTopic, diagramData, sessionId, educationalContext, diagramType = 'circle_map') {
        /**
         * Initialize Node Palette and load first batch.
         * 
         * @param {string} centerTopic - Center node text from diagram
         * @param {Object} diagramData - Current diagram data
         * @param {string} sessionId - Session ID from ThinkGuide
         * @param {Object} educationalContext - Educational context from ThinkGuide (grade, subject, etc.)
         * @param {string} diagramType - Type of diagram (circle_map, bubble_map, etc.)
         */
        this.diagramType = diagramType || window.currentEditor?.diagramType || 'circle_map';
        
        // Check if this is the same session (user coming back) or a new session
        const isSameSession = this.sessionId === sessionId;
        const previousSessionId = this.sessionId;
        
        this.sessionId = sessionId || `palette_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.centerTopic = centerTopic;
        this.diagramData = diagramData;
        this.educationalContext = educationalContext || {}; // Store ThinkGuide context
        
        // Only clear state if it's a NEW session (different sessionId)
        if (!isSameSession) {
            console.log('[NodePalette] NEW session detected - clearing previous state');
            console.log(`[NodePalette]   Previous session: ${previousSessionId || 'none'}`);
            console.log(`[NodePalette]   New session: ${this.sessionId}`);
            this.resetState();
        } else {
            console.log('[NodePalette] SAME session detected - preserving nodes and selections');
            console.log(`[NodePalette]   Session: ${this.sessionId}`);
            console.log(`[NodePalette]   Existing nodes: ${this.nodes.length}`);
            console.log(`[NodePalette]   Selected nodes: ${this.selectedNodes.size}`);
            // Keep existing nodes, selections, and batch count
            // This allows user to return and continue selecting
        }
        
        const metadata = this.getMetadata();
        const existingNodes = diagramData?.children?.length || diagramData?.[metadata.arrayName]?.length || 0;
        
        console.log('[NodePalette] ========================================');
        console.log('[NodePalette] STARTING NODE PALETTE');
        console.log('[NodePalette] ========================================');
        console.log(`[NodePalette] Diagram type: ${this.diagramType}`);
        console.log(`[NodePalette] Node type: ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette] Target array: spec.${metadata.arrayName}`);
        console.log(`[NodePalette] Center topic: "${centerTopic}"`);
        console.log(`[NodePalette] Existing ${metadata.nodeNamePlural}: ${existingNodes}`);
        console.log(`[NodePalette] Educational context:`, educationalContext);
        
        // Show Node Palette panel, hide diagram
        console.log(`[NodePalette] Hiding ${this.diagramType}, showing Palette UI`);
        this.showPalettePanel();
        
        // Only reset scroll if NOT returning to same session (preserve scroll position)
        const container = document.getElementById('node-palette-container');
        if (container && !isSameSession) {
            container.scrollTop = 0;
            console.log('[NodePalette] Reset scroll to top (new session)');
        }
        
        // Setup scroll listener
        this.setupScrollListener();
        
        // Initialize tabs for double bubble map, multi flow map, and tree map
        if (this.usesTabs()) {
            // Determine tab names based on diagram type
            let firstTab, secondTab, thirdTab;
            
            if (this.diagramType === 'double_bubble_map') {
                firstTab = 'similarities';
                secondTab = 'differences';
            } else if (this.diagramType === 'multi_flow_map') {
                firstTab = 'causes';
                secondTab = 'effects';
            } else if (this.diagramType === 'tree_map') {
                // Tree map: 3-stage workflow
                firstTab = 'dimensions';
                secondTab = 'categories';
                thirdTab = 'children';
                
                // Determine initial stage based on diagram data
                const hasDimension = diagramData && diagramData.dimension;
                const hasCategories = diagramData && diagramData.children && diagramData.children.length > 0;
                
                // Filter out placeholder categories to get real ones
                const realCategories = hasCategories 
                    ? diagramData.children.filter(cat => cat.text && !this.isPlaceholder(cat.text))
                    : [];
                
                if (!hasDimension) {
                    // No dimension selected - start from dimension selection
                    this.currentStage = 'dimensions';
                    this.currentTab = 'dimensions';
                    console.log('[NodePalette-TreeMap] Stage 1: Dimension Selection');
                } else if (realCategories.length === 0) {
                    // Dimension selected but no real categories - generate categories
                    this.currentStage = 'categories';
                    this.currentTab = 'categories';
                    this.stageData.dimension = diagramData.dimension;
                    console.log('[NodePalette-TreeMap] Stage 2: Category Generation | Dimension:', diagramData.dimension);
                } else {
                    // Has categories - stay in Stage 3 (children generation)
                    this.currentStage = 'children';
                    this.stageData.dimension = diagramData.dimension;
                    
                    // Extract category names from children (these will be our dynamic tabs)
                    const categoryNames = realCategories.map(cat => cat.text);
                    this.stageData.categories = categoryNames;
                    
                    // Set current tab to first category (NOT 'children')
                    this.currentTab = categoryNames[0];
                    
                    console.log('[NodePalette-TreeMap] Stage 3: Reopening with existing categories');
                    console.log(`[NodePalette-TreeMap]   Dimension: ${diagramData.dimension}`);
                    console.log(`[NodePalette-TreeMap]   Categories: ${categoryNames.join(', ')}`);
                    console.log(`[NodePalette-TreeMap]   Current tab: ${this.currentTab}`);
                }
            } else if (this.diagramType === 'brace_map') {
                // Brace map: 3-stage workflow (dimensions → parts → subparts per part)
                firstTab = 'dimensions';
                secondTab = 'parts';
                
                // Determine initial stage based on diagram data
                const hasDimension = diagramData && diagramData.dimension && typeof diagramData.dimension === 'string' && diagramData.dimension.trim().length > 0;
                const hasParts = diagramData && diagramData.parts && diagramData.parts.length > 0;
                
                // Filter out empty parts (support both 'text' and 'name' fields)
                const realParts = hasParts 
                    ? diagramData.parts.filter(part => {
                        const text = part.text || part.name || '';
                        return text.trim().length > 0;
                    })
                    : [];
                
                if (!hasDimension) {
                    // Stage 1: Dimension Selection
                    this.currentStage = 'dimensions';
                    this.currentTab = 'dimensions';
                    console.log('[NodePalette-BraceMap] Stage 1: Dimension Selection');
                } else if (realParts.length === 0) {
                    // Stage 2: Parts Generation based on selected dimension
                    this.currentStage = 'parts';
                    this.currentTab = 'parts';
                    this.stageData.dimension = diagramData.dimension;
                    console.log('[NodePalette-BraceMap] Stage 2: Parts Generation | Dimension:', diagramData.dimension);
                } else {
                    // Stage 3: Sub-Parts Generation (REOPEN CASE)
                    this.currentStage = 'subparts';
                    this.stageData.dimension = diagramData.dimension;
                    
                    // Extract part names from diagram data (support both 'text' and 'name' fields)
                    const partNames = realParts.map(part => part.text || part.name || '');
                    this.stageData.parts = partNames;
                    
                    // Set current tab to first part
                    this.currentTab = partNames[0];
                    
                    console.log(`[NodePalette-BraceMap] Stage 3: Reopening with ${partNames.length} parts`);
                    console.log(`[NodePalette-BraceMap]   Parts: ${partNames.join(', ')}`);
                    console.log(`[NodePalette-BraceMap]   Current tab: ${this.currentTab}`);
                }
            } else if (this.diagramType === 'mindmap') {
                // Mindmap: Multi-stage workflow (branches -> children)
                firstTab = 'branches';
                secondTab = 'children';
                
                // Determine initial stage based on diagram data
                const hasBranches = diagramData && diagramData.children && diagramData.children.length > 0;
                
                // Filter out empty branches AND placeholder text (e.g., "Branch 1", "分支1")
                const placeholderPatterns = [
                    /^Branch\s*\d+$/i,
                    /^分支\s*\d+$/,
                    /^新分支\s*\d*$/,
                    /^New Branch\s*\d*$/i
                ];
                
                const realBranches = hasBranches 
                    ? diagramData.children.filter(branch => {
                        const text = (branch.label || branch.text || '').trim();
                        
                        // Skip if empty
                        if (text.length === 0) return false;
                        
                        // Skip if matches placeholder pattern
                        if (placeholderPatterns.some(pattern => pattern.test(text))) {
                            console.log(`[NodePalette-Mindmap] Skipping placeholder branch: "${text}"`);
                            return false;
                        }
                        
                        return true;
                    })
                    : [];
                
                if (realBranches.length === 0) {
                    // Stage 1: Branch Generation
                    this.currentStage = 'branches';
                    this.currentTab = 'branches';
                    console.log('[NodePalette-Mindmap] Stage 1: Branch Generation (no real branches detected)');
                } else {
                    // Stage 2: Children Generation (REOPEN CASE)
                    this.currentStage = 'children';
                    
                    // Extract branch names from diagram data
                    const branchNames = realBranches.map(branch => branch.label || branch.text || '');
                    this.stageData.branches = branchNames;
                    
                    // Set current tab to first branch
                    this.currentTab = branchNames[0];
                    
                    console.log(`[NodePalette-Mindmap] Stage 2: Reopening with ${branchNames.length} real branches`);
                    console.log(`[NodePalette-Mindmap]   Branches: ${branchNames.join(', ')}`);
                    console.log(`[NodePalette-Mindmap]   Current tab: ${this.currentTab}`);
                }
            } else if (this.diagramType === 'flow_map') {
                // Flow Map: Multi-stage workflow (dimensions -> steps -> substeps)
                firstTab = 'dimensions';
                secondTab = 'steps';
                
                // Determine initial stage based on diagram data
                const hasDimension = diagramData && diagramData.dimension && diagramData.dimension.trim().length > 0;
                const hasSteps = diagramData && diagramData.steps && diagramData.steps.length > 0;
                
                // Filter out empty steps
                const realSteps = hasSteps 
                    ? diagramData.steps.filter(step => {
                        const text = step.text || step.name || '';
                        return text.trim().length > 0;
                    })
                    : [];
                
                if (!hasDimension) {
                    // Stage 1: Dimension Selection
                    this.currentStage = 'dimensions';
                    this.currentTab = 'dimensions';
                    console.log('[NodePalette-FlowMap] Stage 1: Dimension Selection');
                } else if (realSteps.length === 0) {
                    // Stage 2: Steps Generation based on selected dimension
                    this.currentStage = 'steps';
                    this.currentTab = 'steps';
                    this.stageData.dimension = diagramData.dimension;
                    console.log('[NodePalette-FlowMap] Stage 2: Steps Generation | Dimension:', diagramData.dimension);
                } else {
                    // Stage 3: Sub-Steps Generation (REOPEN CASE)
                    this.currentStage = 'substeps';
                    this.stageData.dimension = diagramData.dimension;
                    
                    // Extract step names from diagram data (support both 'text' and 'name' fields)
                    const stepNames = realSteps.map(step => step.text || step.name || '');
                    this.stageData.steps = stepNames;
                    
                    // Set current tab to first step
                    this.currentTab = stepNames[0];
                    
                    console.log(`[NodePalette-FlowMap] Stage 3: Reopening with ${stepNames.length} steps`);
                    console.log(`[NodePalette-FlowMap]   Steps: ${stepNames.join(', ')}`);
                    console.log(`[NodePalette-FlowMap]   Current tab: ${this.currentTab}`);
                }
            } else {
                // Fallback for future tab-enabled diagrams
                firstTab = 'tab1';
                secondTab = 'tab2';
            }
            
            // Set current tab if not using multi-stage workflow (tree_map, brace_map, mindmap, flow_map set it in stage detection above)
            if (!this.usesStages() || (this.diagramType !== 'tree_map' && this.diagramType !== 'brace_map' && this.diagramType !== 'mindmap' && this.diagramType !== 'flow_map')) {
                this.currentTab = firstTab;
            }
            
            // Only initialize if not already initialized (preserve preloaded data!)
            if (!this.tabNodes || !this.tabNodes[firstTab]) {
                if (this.diagramType === 'tree_map') {
                    // Tree map: Check if Stage 3 with existing categories
                    if (this.currentStage === 'children' && this.stageData.categories && this.stageData.categories.length > 0) {
                        // Stage 3: Initialize dynamic category tabs
                        const categoryNames = this.stageData.categories;
                        const dynamicTabNodes = {};
                        const dynamicTabSelectedNodes = {};
                        const dynamicTabScrollPositions = {};
                        
                        categoryNames.forEach(categoryName => {
                            dynamicTabNodes[categoryName] = [];
                            dynamicTabSelectedNodes[categoryName] = new Set();
                            dynamicTabScrollPositions[categoryName] = 0;
                        });
                        
                        // Include locked tabs from previous stages
                        this.tabNodes = {
                            dimensions: [],
                            categories: [],
                            ...dynamicTabNodes
                        };
                        this.tabSelectedNodes = {
                            dimensions: new Set(),
                            categories: new Set(),
                            ...dynamicTabSelectedNodes
                        };
                        this.tabScrollPositions = {
                            dimensions: 0,
                            categories: 0,
                            ...dynamicTabScrollPositions
                        };
                        
                        console.log(`[NodePalette-TreeMap] Initialized ${categoryNames.length} dynamic category tabs:`, categoryNames);
                    } else {
                        // Stage 1 or 2: Initialize 3 initial tabs
                        this.tabNodes = {
                            [firstTab]: [],
                            [secondTab]: [],
                            [thirdTab]: []
                        };
                        this.tabSelectedNodes = {
                            [firstTab]: new Set(),
                            [secondTab]: new Set(),
                            [thirdTab]: new Set()
                        };
                        this.tabScrollPositions = {
                            [firstTab]: 0,
                            [secondTab]: 0,
                            [thirdTab]: 0
                        };
                        
                        console.log('[NodePalette-TreeMap] Initialized 3 initial tabs: dimensions, categories, children');
                    }
                } else if (this.diagramType === 'brace_map') {
                    // Brace map: Check if Stage 2 with existing parts
                    if (this.currentStage === 'subparts' && this.stageData.parts && this.stageData.parts.length > 0) {
                        // Stage 3: Initialize dynamic part tabs
                        const partNames = this.stageData.parts;
                        const dynamicTabNodes = {};
                        const dynamicTabSelectedNodes = {};
                        const dynamicTabScrollPositions = {};
                        
                        partNames.forEach(partName => {
                            dynamicTabNodes[partName] = [];
                            dynamicTabSelectedNodes[partName] = new Set();
                            dynamicTabScrollPositions[partName] = 0;
                        });
                        
                        // Include locked tabs from previous stages
                        this.tabNodes = {
                            dimensions: [],
                            parts: [],
                            ...dynamicTabNodes
                        };
                        this.tabSelectedNodes = {
                            dimensions: new Set(),
                            parts: new Set(),
                            ...dynamicTabSelectedNodes
                        };
                        this.tabScrollPositions = {
                            dimensions: 0,
                            parts: 0,
                            ...dynamicTabScrollPositions
                        };
                        
                        console.log(`[NodePalette-BraceMap] Initialized ${partNames.length} dynamic part tabs:`, partNames);
                    } else {
                        // Stage 1 or Stage 2: Initialize dimensions and parts tabs
                        this.tabNodes = {
                            dimensions: [],
                            parts: []
                        };
                        this.tabSelectedNodes = {
                            dimensions: new Set(),
                            parts: new Set()
                        };
                        this.tabScrollPositions = {
                            dimensions: 0,
                            parts: 0
                        };
                        
                        console.log('[NodePalette-BraceMap] Initialized dimensions and parts tabs (Stage 1 or 2)');
                    }
                } else if (this.diagramType === 'mindmap') {
                    // Mindmap: Check if Stage 2 with existing branches
                    if (this.currentStage === 'children' && this.stageData.branches && this.stageData.branches.length > 0) {
                        // Stage 2: Initialize dynamic branch tabs
                        const branchNames = this.stageData.branches;
                        const dynamicTabNodes = {};
                        const dynamicTabSelectedNodes = {};
                        const dynamicTabScrollPositions = {};
                        
                        branchNames.forEach(branchName => {
                            dynamicTabNodes[branchName] = [];
                            dynamicTabSelectedNodes[branchName] = new Set();
                            dynamicTabScrollPositions[branchName] = 0;
                        });
                        
                        // Include locked tab from previous stage
                        this.tabNodes = {
                            branches: [],
                            ...dynamicTabNodes
                        };
                        this.tabSelectedNodes = {
                            branches: new Set(),
                            ...dynamicTabSelectedNodes
                        };
                        this.tabScrollPositions = {
                            branches: 0,
                            ...dynamicTabScrollPositions
                        };
                        
                        console.log(`[NodePalette-Mindmap] Initialized ${branchNames.length} dynamic branch tabs:`, branchNames);
                    } else {
                        // Stage 1: Initialize branches tab only
                        this.tabNodes = {
                            branches: []
                        };
                        this.tabSelectedNodes = {
                            branches: new Set()
                        };
                        this.tabScrollPositions = {
                            branches: 0
                        };
                        
                        console.log('[NodePalette-Mindmap] Initialized branches tab (Stage 1)');
                    }
                } else if (this.diagramType === 'flow_map') {
                    // Flow Map: Multi-stage workflow (dimensions -> steps -> substeps)
                    if (this.currentStage === 'substeps' && this.stageData.steps && this.stageData.steps.length > 0) {
                        // Stage 3: Initialize tabs for each selected step
                        const stepNames = this.stageData.steps;
                        
                        const dynamicTabNodes = {};
                        const dynamicTabSelectedNodes = {};
                        const dynamicTabScrollPositions = {};
                        
                        stepNames.forEach(stepName => {
                            dynamicTabNodes[stepName] = [];
                            dynamicTabSelectedNodes[stepName] = new Set();
                            dynamicTabScrollPositions[stepName] = 0;
                        });
                        
                        // Include locked tabs from previous stages
                        this.tabNodes = {
                            dimensions: [],
                            steps: [],
                            ...dynamicTabNodes
                        };
                        this.tabSelectedNodes = {
                            dimensions: new Set(),
                            steps: new Set(),
                            ...dynamicTabSelectedNodes
                        };
                        this.tabScrollPositions = {
                            dimensions: 0,
                            steps: 0,
                            ...dynamicTabScrollPositions
                        };
                        
                        console.log(`[NodePalette-FlowMap] Initialized ${stepNames.length} dynamic step tabs:`, stepNames);
                    } else if (this.currentStage === 'steps') {
                        // Stage 2: Initialize dimensions and steps tabs
                        this.tabNodes = {
                            dimensions: [],
                            steps: []
                        };
                        this.tabSelectedNodes = {
                            dimensions: new Set(),
                            steps: new Set()
                        };
                        this.tabScrollPositions = {
                            dimensions: 0,
                            steps: 0
                        };
                        
                        console.log('[NodePalette-FlowMap] Initialized dimensions and steps tabs (Stage 2)');
                    } else {
                        // Stage 1: Initialize dimensions tab only
                        this.tabNodes = {
                            dimensions: []
                        };
                        this.tabSelectedNodes = {
                            dimensions: new Set()
                        };
                        this.tabScrollPositions = {
                            dimensions: 0
                        };
                        
                        console.log('[NodePalette-FlowMap] Initialized dimensions tab (Stage 1)');
                    }
                } else {
                    // Other diagrams: 2 tabs (double_bubble_map, multi_flow_map)
                    this.tabNodes = {
                        [firstTab]: [],
                        [secondTab]: []
                    };
                    this.tabSelectedNodes = {
                        [firstTab]: new Set(),
                        [secondTab]: new Set()
                    };
                    this.tabScrollPositions = {
                        [firstTab]: 0,
                        [secondTab]: 0
                    };
                }
            }
            
            // Show tabs UI
            // For Tree Map Stage 3 with categories, show dynamic tabs
            if (this.diagramType === 'tree_map' && this.currentStage === 'children' && this.stageData.categories && this.stageData.categories.length > 0) {
                this.showDynamicCategoryTabsUI(this.stageData.categories);
            } else if (this.diagramType === 'brace_map' && this.currentStage === 'subparts' && this.stageData.parts && this.stageData.parts.length > 0) {
                // For Brace Map Stage 3 with parts, show dynamic part tabs
                this.showDynamicCategoryTabsUI(this.stageData.parts);  // Reuse tree map's dynamic tab UI
            } else if (this.diagramType === 'mindmap' && this.currentStage === 'children' && this.stageData.branches && this.stageData.branches.length > 0) {
                // For Mindmap Stage 2 with branches, show dynamic branch tabs
                this.showDynamicCategoryTabsUI(this.stageData.branches);  // Reuse tree map's dynamic tab UI
            } else if (this.diagramType === 'flow_map' && this.currentStage === 'substeps' && this.stageData.steps && this.stageData.steps.length > 0) {
                // For Flow Map Stage 3 with steps, show dynamic step tabs
                this.showDynamicCategoryTabsUI(this.stageData.steps);  // Reuse tree map's dynamic tab UI
            } else {
                this.showTabsUI();
            }
            
            // Attach tab button listeners
            this.attachTabButtonListeners();
            
            // Synchronize tab button states with currentTab
            // Use setTimeout to ensure DOM is ready after showTabsUI
            setTimeout(() => {
                this.updateTabButtons();
                console.log('[NodePalette] Tab buttons synchronized after initialization');
                
                // For Tree Map Stage 3: Lock dimensions and categories tabs
                if (this.diagramType === 'tree_map' && this.currentStage === 'children') {
                    this.lockTab('dimensions');
                    this.lockTab('categories');
                    console.log('[NodePalette-TreeMap] Locked dimensions and categories tabs (Stage 3)');
                }
                
                // For Brace Map Stage 3: Lock dimensions and parts tabs
                if (this.diagramType === 'brace_map' && this.currentStage === 'subparts') {
                    this.lockTab('dimensions');
                    this.lockTab('parts');
                    console.log('[NodePalette-BraceMap] Locked dimensions and parts tabs (Stage 3)');
                } else if (this.diagramType === 'brace_map' && this.currentStage === 'parts') {
                    this.lockTab('dimensions');
                    console.log('[NodePalette-BraceMap] Locked dimensions tab (Stage 2)');
                }
                
                // For Mindmap Stage 2: Lock branches tab
                if (this.diagramType === 'mindmap' && this.currentStage === 'children') {
                    this.lockTab('branches');
                    console.log('[NodePalette-Mindmap] Locked branches tab (Stage 2)');
                }
                
                // For Flow Map Stage 3: Lock dimensions and steps tabs
                if (this.diagramType === 'flow_map' && this.currentStage === 'substeps') {
                    this.lockTab('dimensions');
                    this.lockTab('steps');
                    console.log('[NodePalette-FlowMap] Locked dimensions and steps tabs (Stage 3)');
                } else if (this.diagramType === 'flow_map' && this.currentStage === 'steps') {
                    this.lockTab('dimensions');
                    console.log('[NodePalette-FlowMap] Locked dimensions tab (Stage 2)');
                }
            }, 50);
            
            console.log(`[NodePalette] Tabs initialized for ${this.diagramType}: ${firstTab} and ${secondTab}`);
        } else {
            // Hide tabs for other diagram types
            this.hideTabsUI();
        }
        
        // Check if data was preloaded (nodes already exist)
        let hasPreloadedData = this.nodes.length > 0;
        if (this.tabNodes && Object.keys(this.tabNodes).length > 0) {
            // Check if any tab has nodes (works for double bubble & multi flow)
            hasPreloadedData = hasPreloadedData || Object.values(this.tabNodes).some(arr => arr?.length > 0);
        }
        
        if (hasPreloadedData) {
            // Data was preloaded! Just render it (instant display!)
            console.log('[NodePalette] ===== PRELOADED DATA DETECTED =====');
            console.log(`[NodePalette] Nodes ready: ${this.nodes.length}`);
            if (this.tabNodes) {
                // Log all tab names dynamically
                Object.keys(this.tabNodes).forEach(tabName => {
                    const count = this.tabNodes[tabName]?.length || 0;
                    console.log(`[NodePalette] ${tabName}: ${count}`);
                });
                
                // CRITICAL: For tab-based diagrams, load nodes from current tab BEFORE restoring
                if (this.currentTab && this.tabNodes[this.currentTab]) {
                    this.nodes = [...this.tabNodes[this.currentTab]];
                    console.log(`[NodePalette] Loaded ${this.nodes.length} nodes from ${this.currentTab} tab for display`);
                    
                    // Also restore tab-specific selections
                    if (this.tabSelectedNodes && this.tabSelectedNodes[this.currentTab]) {
                        this.selectedNodes = new Set(this.tabSelectedNodes[this.currentTab]);
                        console.log(`[NodePalette] Restored ${this.selectedNodes.size} selections from ${this.currentTab} tab`);
                    }
                }
            }
            console.log('[NodePalette] Skipping catapult, rendering immediately!');
            this.restoreUI();
        } else if (isSameSession && this.nodes.length > 0) {
            // Returning to same session - restore existing nodes in UI
            this.restoreUI();
        } else {
            // New session - load first batch
            if (this.diagramType === 'tree_map' && this.usesStages()) {
                // Tree maps: Auto-load current stage only
                console.log(`[NodePalette-TreeMap] Auto-loading ${this.currentStage} stage...`);
                
                // Update button text for tree map stages
                this.updateStageProgressButton();
                
                // For Stage 3 (children), load the current category tab
                if (this.currentStage === 'children' && this.stageData.categories && this.stageData.categories.length > 0) {
                    console.log(`[NodePalette-TreeMap] Stage 3: Loading current category tab "${this.currentTab}"`);
                    
                    // Set loading state and show catapult animation
                    this.isLoadingBatch = true;
                    this.currentBatch = 1;
                    this.showCatapultLoading();
                    
                    const lang = window.languageManager?.getCurrentLanguage() || 'en';
                    const loadingMsg = lang === 'zh' ? 
                        `正在为「${this.currentTab}」生成项目 (4个AI模型)...` : 
                        `Generating items for "${this.currentTab}" (4 AI models)...`;
                    this.updateCatapultLoading(loadingMsg, 0, 4);
                    
                    try {
                        await this.loadCategoryTabBatch(this.currentTab);
                        this.hideCatapultLoading();
                    } catch (error) {
                        console.error(`[NodePalette-TreeMap] Error loading category tab "${this.currentTab}":`, error);
                        this.hideCatapultLoading();
                    }
                    
                    this.isLoadingBatch = false;
                } else {
                    // For Stage 1 or 2, use normal batch loading
                    await this.loadNextBatch();
                }
            } else if (this.diagramType === 'brace_map' && this.usesStages()) {
                // Brace maps: Auto-load current stage only (similar to tree map)
                console.log(`[NodePalette-BraceMap] Auto-loading ${this.currentStage} stage...`);
                
                // Update button text for brace map stages
                this.updateStageProgressButton();
                
                // For Stage 3 (subparts), load the current part tab
                if (this.currentStage === 'subparts' && this.stageData.parts && this.stageData.parts.length > 0) {
                    console.log(`[NodePalette-BraceMap] Stage 3: Loading current part tab "${this.currentTab}"`);
                    
                    // Set loading state and show catapult animation
                    this.isLoadingBatch = true;
                    this.currentBatch = 1;
                    this.showCatapultLoading();
                    
                    const lang = window.languageManager?.getCurrentLanguage() || 'en';
                    const loadingMsg = lang === 'zh' ? 
                        `正在为「${this.currentTab}」生成子部分 (4个AI模型)...` : 
                        `Generating subparts for "${this.currentTab}" (4 AI models)...`;
                    this.updateCatapultLoading(loadingMsg, 0, 4);
                    
                    try {
                        await this.loadCategoryTabBatch(this.currentTab);
                        this.hideCatapultLoading();
                    } catch (error) {
                        console.error(`[NodePalette-BraceMap] Error loading part tab "${this.currentTab}":`, error);
                        this.hideCatapultLoading();
                    }
                    
                    this.isLoadingBatch = false;
                } else {
                    // For Stage 1 or 2, use normal batch loading
                    await this.loadNextBatch();
                }
            } else if (this.diagramType === 'mindmap' && this.usesStages()) {
                // Mindmaps: Auto-load current stage only (similar to tree map)
                console.log(`[NodePalette-Mindmap] Auto-loading ${this.currentStage} stage...`);
                
                // Update button text for mindmap stages
                this.updateStageProgressButton();
                
                // For Stage 2 (children), load the current branch tab
                if (this.currentStage === 'children' && this.stageData.branches && this.stageData.branches.length > 0) {
                    console.log(`[NodePalette-Mindmap] Stage 2: Loading current branch tab "${this.currentTab}"`);
                    
                    // Set loading state and show catapult animation
                    this.isLoadingBatch = true;
                    this.currentBatch = 1;
                    this.showCatapultLoading();
                    
                    const lang = window.languageManager?.getCurrentLanguage() || 'en';
                    const loadingMsg = lang === 'zh' ? 
                        `正在为「${this.currentTab}」生成子节点 (4个AI模型)...` : 
                        `Generating children for "${this.currentTab}" (4 AI models)...`;
                    this.updateCatapultLoading(loadingMsg, 0, 4);
                    
                    try {
                        await this.loadCategoryTabBatch(this.currentTab);
                        this.hideCatapultLoading();
                    } catch (error) {
                        console.error(`[NodePalette-Mindmap] Error loading branch tab "${this.currentTab}":`, error);
                        this.hideCatapultLoading();
                    }
                    
                    this.isLoadingBatch = false;
                } else {
                    // For Stage 1, use normal batch loading
                    await this.loadNextBatch();
                }
            } else if (this.diagramType === 'flow_map' && this.usesStages()) {
                // Flow maps: Auto-load current stage only (similar to tree map)
                console.log(`[NodePalette-FlowMap] Auto-loading ${this.currentStage} stage...`);
                
                // Update button text for flow map stages
                this.updateStageProgressButton();
                
                // For Stage 3 (substeps), load the current step tab
                if (this.currentStage === 'substeps' && this.stageData.steps && this.stageData.steps.length > 0) {
                    console.log(`[NodePalette-FlowMap] Stage 3: Loading current step tab "${this.currentTab}"`);
                    
                    // Set loading state and show catapult animation
                    this.isLoadingBatch = true;
                    this.currentBatch = 1;
                    this.showCatapultLoading();
                    
                    const lang = window.languageManager?.getCurrentLanguage() || 'en';
                    const loadingMsg = lang === 'zh' ? 
                        `正在为「${this.currentTab}」生成子步骤 (4个AI模型)...` : 
                        `Generating substeps for "${this.currentTab}" (4 AI models)...`;
                    this.updateCatapultLoading(loadingMsg, 0, 4);
                    
                    try {
                        await this.loadCategoryTabBatch(this.currentTab);
                        this.hideCatapultLoading();
                    } catch (error) {
                        console.error(`[NodePalette-FlowMap] Error loading step tab "${this.currentTab}":`, error);
                        this.hideCatapultLoading();
                    }
                    
                    this.isLoadingBatch = false;
                } else {
                    // For Stage 1 or 2, use normal batch loading
                    await this.loadNextBatch();
                }
            } else if (this.usesTabs()) {
                // For tab-based diagrams (double bubble, multi flow): load BOTH tabs
                const tabNames = Object.keys(this.tabNodes || {});
                console.log(`[NodePalette] Loading first batch for BOTH tabs (${tabNames.join(' + ')})...`);
                await this.loadBothTabsInitial();
            } else {
                // For other diagrams: load single batch
                console.log('[NodePalette] Loading first batch for new session...');
                await this.loadNextBatch();
            }
        }
    }
    
    resetState() {
        /**
         * Reset Node Palette batch and node data.
         * Does NOT reset session properties (sessionId, diagramType, etc.) 
         * as those are set at the start of each session.
         */
        this.nodes = [];
        this.selectedNodes.clear();
        this.currentBatch = 0;
        this.isLoadingBatch = false;
        
        // Clear tab data for double bubble maps (CRITICAL for proper cleanup)
        this.currentTab = null;
        this.tabNodes = null;
        this.tabSelectedNodes = null;
        this.tabScrollPositions = null;
        this.lastScrollPosition = 0;  // Clear non-tab scroll position
        
        // Clear the UI grid to remove old nodes from previous session
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.innerHTML = '';
            console.log('[NodePalette] UI grid cleared for new session');
        }
        
        // Reset scroll position to top (fixes scroll state persistence bug)
        const container = document.getElementById('node-palette-container');
        if (container) {
            container.scrollTop = 0;
            console.log('[NodePalette] Scroll position reset to top');
        }
        
        // Hide tab UI (will be re-shown if needed in start())
        this.hideTabsUI();
        
        // Clear any active loading animations
        this.hideBatchTransition();
        this.hideCatapultLoading();
        
        console.log('[NodePalette] State reset complete (nodes, selections, tabs, animations, scroll cleared)');
    }
    
    clearAll() {
        /**
         * Complete cleanup - reset everything including session properties.
         * Called when cancelling or completely exiting Node Palette.
         */
        this.resetState();
        this.sessionId = null;
        this.centerTopic = null;
        this.diagramData = null;
        this.diagramType = null;
    }
    
    restoreUI() {
        /**
         * Restore Node Palette UI from existing session data.
         * Re-renders all node cards and updates button state.
         * Restores scroll position from previous session.
         */
        console.log(`[NodePalette] Restoring ${this.nodes.length} existing nodes to grid`);
        
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.innerHTML = '';
            this.nodes.forEach(node => this.renderNodeCardOnly(node));
            console.log(`[NodePalette] ✓ Restored ${this.nodes.length} nodes with ${this.selectedNodes.size} selected`);
        }
        
        // Sync tab button states for double bubble map
        if (this.usesTabs()) {
            this.updateTabButtons();
            console.log(`[NodePalette] ✓ Tab buttons synchronized to current tab: ${this.currentTab}`);
        }
        
        // Restore scroll position (must happen after rendering nodes)
        const container = document.getElementById('node-palette-container');
        if (container) {
            // Use setTimeout to ensure DOM is fully rendered before scrolling
            setTimeout(() => {
                if (this.usesTabs() && this.currentTab && this.tabScrollPositions) {
                    const savedScrollPos = this.tabScrollPositions[this.currentTab] || 0;
                    container.scrollTop = savedScrollPos;
                    console.log(`[NodePalette] ✓ Restored ${this.currentTab} scroll position: ${savedScrollPos}px`);
                } else if (!this.usesTabs() && this.lastScrollPosition) {
                    container.scrollTop = this.lastScrollPosition;
                    console.log(`[NodePalette] ✓ Restored scroll position: ${this.lastScrollPosition}px`);
                }
            }, 50);
        }
        
        this.updateFinishButtonState();
    }
    
    showPalettePanel() {
        /**
         * Show Node Palette panel and hide Circle Map.
         * Respects ThinkGuide panel if it's visible (leaves space for it).
         */
        const d3Container = document.getElementById('d3-container');
        const palettePanel = document.getElementById('node-palette-panel');
        const thinkingPanel = document.getElementById('thinking-panel');
        
        if (d3Container) d3Container.style.display = 'none';
        if (palettePanel) {
            palettePanel.style.display = 'flex';
            palettePanel.style.opacity = '0';
            
            // Check if ThinkGuide panel is visible
            const isThinkGuideVisible = thinkingPanel && !thinkingPanel.classList.contains('collapsed');
            if (isThinkGuideVisible) {
                palettePanel.classList.add('thinkguide-visible');
                console.log('[NodePalette] ThinkGuide is visible, leaving space for it');
            } else {
                palettePanel.classList.remove('thinkguide-visible');
                console.log('[NodePalette] ThinkGuide is hidden, using full width');
            }
            
            // Fade in
            setTimeout(() => {
                palettePanel.style.transition = 'opacity 0.3s';
                palettePanel.style.opacity = '1';
            }, 10);
        }
        
        // Attach button listeners when panel opens
        this.attachFinishButtonListener();
        this.attachCancelButtonListener();
    }
    
    attachFinishButtonListener() {
        /**
         * Attach click listener to Finish/Next button.
         * For tree maps: "Next" button advances stages, "Finish" completes on final stage
         * Called when panel opens to ensure listener is active.
         */
        const finishBtn = document.getElementById('finish-selection-btn');
        if (finishBtn) {
            // Remove old listener if exists (prevent duplicates)
            finishBtn.replaceWith(finishBtn.cloneNode(true));
            const newBtn = document.getElementById('finish-selection-btn');
            
            // Store reference for updateStageProgressButton
            newBtn.classList.add('node-palette-finish-btn');
            
            newBtn.addEventListener('click', async () => {
                console.log('[NodePalette] Finish/Next button clicked!');
                
                // For diagrams with multi-stage workflows: route to stage progression or finish
                if (this.diagramType === 'tree_map' && this.usesStages()) {
                    if (this.currentStage === 'children') {
                        // Final stage: finish selection
                        console.log('[NodePalette-TreeMap] Final stage, finishing selection');
                        this.finishSelection();
                    } else {
                        // Not final stage: advance to next stage
                        console.log(`[NodePalette-TreeMap] Advancing from ${this.currentStage} to next stage`);
                        await this.advanceToNextStage();
                    }
                } else if (this.diagramType === 'brace_map' && this.usesStages()) {
                    if (this.currentStage === 'subparts') {
                        // Final stage: finish selection
                        console.log('[NodePalette-BraceMap] Final stage, finishing selection');
                        this.finishSelection();
                    } else {
                        // Not final stage: advance to next stage
                        console.log(`[NodePalette-BraceMap] Advancing from ${this.currentStage} to next stage`);
                        await this.advanceBraceMapToNextStage();
                    }
                } else if (this.diagramType === 'mindmap' && this.usesStages()) {
                    if (this.currentStage === 'children') {
                        // Final stage: finish selection
                        console.log('[NodePalette-Mindmap] Final stage, finishing selection');
                        this.finishSelection();
                    } else {
                        // Not final stage: advance to next stage
                        console.log(`[NodePalette-Mindmap] Advancing from ${this.currentStage} to next stage`);
                        await this.advanceMindMapToNextStage();
                    }
                } else if (this.diagramType === 'flow_map' && this.usesStages()) {
                    if (this.currentStage === 'substeps') {
                        // Final stage: finish selection
                        console.log('[NodePalette-FlowMap] Final stage, finishing selection');
                        this.finishSelection();
                    } else {
                        // Not final stage: advance to next stage
                        console.log(`[NodePalette-FlowMap] Advancing from ${this.currentStage} to next stage`);
                        await this.advanceFlowMapToNextStage();
                    }
                } else {
                    // Other diagrams: normal finish
                    this.finishSelection();
                }
            });
            console.log('[NodePalette] Finish/Next button listener attached');
        } else {
            console.error('[NodePalette] Finish button not found in DOM!');
        }
    }
    
    attachCancelButtonListener() {
        /**
         * Attach click listener to Cancel button.
         * Called when panel opens to ensure listener is active.
         */
        const cancelBtn = document.getElementById('cancel-palette-btn');
        if (cancelBtn) {
            // Remove old listener if exists (prevent duplicates)
            cancelBtn.replaceWith(cancelBtn.cloneNode(true));
            const newBtn = document.getElementById('cancel-palette-btn');
            
            newBtn.addEventListener('click', () => {
                console.log('[NodePalette] Cancel button clicked!');
                this.cancelPalette();
            });
            console.log('[NodePalette] Cancel button listener attached');
        } else {
            console.error('[NodePalette] Cancel button not found in DOM!');
        }
    }
    
    hidePalettePanel() {
        /**
         * Hide Node Palette panel and show Circle Map.
         * Saves scroll position before hiding for restoration on re-entry.
         */
        // Save scroll position before hiding (for tabs and non-tabs)
        const container = document.getElementById('node-palette-container');
        if (container && this.usesTabs() && this.currentTab) {
            const scrollPos = container.scrollTop;
            this.tabScrollPositions[this.currentTab] = scrollPos;
            console.log(`[NodePalette] Saved ${this.currentTab} scroll position: ${scrollPos}px`);
        } else if (container && !this.usesTabs()) {
            // For non-tab diagrams, save to a general scroll position
            this.lastScrollPosition = container.scrollTop;
            console.log(`[NodePalette] Saved scroll position: ${this.lastScrollPosition}px`);
        }
        
        const d3Container = document.getElementById('d3-container');
        const palettePanel = document.getElementById('node-palette-panel');
        
        if (palettePanel) {
            palettePanel.style.opacity = '0';
            setTimeout(() => {
                palettePanel.style.display = 'none';
                // Clean up ThinkGuide visibility class
                palettePanel.classList.remove('thinkguide-visible');
            }, 300);
        }
        if (d3Container) {
            d3Container.style.display = 'block';
            d3Container.style.opacity = '0';
            setTimeout(() => {
                d3Container.style.transition = 'opacity 0.3s';
                d3Container.style.opacity = '1';
            }, 10);
        }
    }
    
    async cancelPalette() {
        /**
         * Cancel Node Palette and return to canvas without adding nodes.
         * Clears all state and logs the cancellation event.
         */
        const metadata = this.getMetadata();
        
        console.log('[NodePalette-Cancel] ========================================');
        console.log('[NodePalette-Cancel] USER CLICKED CANCEL BUTTON');
        console.log('[NodePalette-Cancel] ========================================');
        console.log(`[NodePalette-Cancel] Diagram: ${this.diagramType} | Node type: ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Cancel] Selected: ${this.selectedNodes.size}/${this.nodes.length} | Batches: ${this.currentBatch}`);
        console.log(`[NodePalette-Cancel] Session ID: ${this.sessionId}`);
        console.log('[NodePalette-Cancel] Action: Returning to canvas WITHOUT adding nodes');
        
        // Log cancel event to backend
        console.log('[NodePalette-Cancel] Sending cancel event to backend...');
        try {
            const response = await auth.fetch('/thinking_mode/node_palette/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    diagram_type: this.diagramType,  // CRITICAL: Backend needs this to clean up generator
                    selected_node_count: this.selectedNodes.size,
                    total_nodes_generated: this.nodes.length,
                    batches_loaded: this.currentBatch
                })
            });
            console.log('[NodePalette-Cancel] Backend response:', response.status, response.statusText);
        } catch (e) {
            console.error('[NodePalette-Cancel] Failed to log cancel event:', e);
        }
        
        // Hide Node Palette panel
        console.log('[NodePalette-Cancel] Hiding Node Palette panel...');
        this.hideBatchTransition(); // Clean up any active transition
        this.hidePalettePanel();
        
        // Clear all state including session properties
        console.log('[NodePalette-Cancel] Clearing Node Palette state...');
        this.clearAll();
        
        // Clear grid
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.innerHTML = '';
            console.log('[NodePalette-Cancel] Cleared node grid');
        }
        
        console.log('[NodePalette-Cancel] ========================================');
        console.log('[NodePalette-Cancel] ✓ CANCELLED: Returned to canvas');
        console.log('[NodePalette-Cancel] ========================================');
    }
    
    setupScrollListener() {
        /**
         * Setup infinite scroll listener - triggers at 2/3 scroll position.
         */
        const container = document.getElementById('node-palette-container');
        if (!container) return;
        
        // Throttle scroll events
        let scrollTimeout;
        container.addEventListener('scroll', () => {
            if (scrollTimeout) clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this.onScroll();
            }, 150);
        });
    }
    
    onScroll() {
        /**
         * INFINITE SCROLL - Keep CATAPULT firing forever!
         * 
         * Every time user scrolls to 2/3 down the page, we CATAPULT again.
         * This fires 4 LLMs concurrently for batch 2, 3, 4, 5... no limits!
         * 
         * Each scroll trigger = 1 CATAPULT = 4 LLMs = ~60 new nodes
         */
        const container = document.getElementById('node-palette-container');
        if (!container) return;
        
        const scrollHeight = container.scrollHeight;
        const scrollTop = container.scrollTop;
        const clientHeight = container.clientHeight;
        
        // Calculate scroll progress (0 to 1)
        const scrollProgress = (scrollTop + clientHeight) / scrollHeight;
        
        // Trigger at 2/3 (0.67) - CATAPULT again! Infinite batches!
        if (scrollProgress >= 0.67 && !this.isLoadingBatch) {
            console.log('[NodePalette] 2/3 scroll reached! CATAPULT batch #' + (this.currentBatch + 1) + ' launching...');
            this.loadNextBatch();  // This calls catapult() -> 4 LLMs fire -> ~60 new nodes
        }
    }
    
    async loadBothTabsInitial() {
        /**
         * Load BOTH tabs simultaneously (double bubble map & multi flow map)
         * Each tab fires 4 LLMs concurrently = 8 LLMs total!
         */
        console.log('[NodePalette] Loading BOTH tabs in parallel (8 LLMs total)');
        
        this.isLoadingBatch = true;
        this.currentBatch = 1;
        
        // Determine tab names based on diagram type
        let firstTab, secondTab;
        if (this.diagramType === 'double_bubble_map') {
            firstTab = 'similarities';
            secondTab = 'differences';
        } else if (this.diagramType === 'multi_flow_map') {
            firstTab = 'causes';
            secondTab = 'effects';
        } else if (this.diagramType === 'tree_map') {
            firstTab = 'dimensions';
            secondTab = 'categories';
        } else if (this.diagramType === 'brace_map') {
            firstTab = 'dimensions';
            secondTab = 'parts';
        } else if (this.diagramType === 'mindmap') {
            firstTab = 'branches';
            secondTab = 'branches'; // Mindmap Stage 1: only load branches tab
        } else if (this.diagramType === 'flow_map') {
            firstTab = 'dimensions';
            secondTab = 'steps';
        } else {
            // Fallback
            firstTab = 'tab1';
            secondTab = 'tab2';
        }
        
        // Show standard catapult loading
        this.showCatapultLoading();
        
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        const loadingMsg = lang === 'zh' ? '正在加载两个标签 (8个AI模型)...' : 'Loading both tabs (8 AI models)...';
        this.updateCatapultLoading(loadingMsg, 0, 8);
        
        try {
            // CATAPULT! Fire 8 LLMs total (4 per tab) - both tabs load in parallel
            // Each catapult call will update the progress
            console.log(`[NodePalette] 🚀 Firing 2 parallel catapults: ${firstTab} + ${secondTab}`);
            const results = await Promise.all([
                this.loadTabBatch(firstTab),
                this.loadTabBatch(secondTab)
            ]);
            
            console.log('[NodePalette] ✅ Both tabs loaded successfully');
            console.log(`  - ${firstTab}: ${this.tabNodes[firstTab]?.length || 0} nodes`);
            console.log(`  - ${secondTab}: ${this.tabNodes[secondTab]?.length || 0} nodes`);
            console.log(`  - Total: ${(this.tabNodes[firstTab]?.length || 0) + (this.tabNodes[secondTab]?.length || 0)} nodes across both tabs`);
            
            // Update tab counters
            this.updateTabCounters();
            
            // Show completion
            const completeMsg = lang === 'zh' ? '两个标签已加载完成！' : 'Both tabs loaded!';
            this.updateCatapultLoading(completeMsg, 8, 8);
            setTimeout(() => this.hideCatapultLoading(), 800);
            
        } catch (error) {
            console.error('[NodePalette] Error loading both tabs:', error);
            this.hideCatapultLoading();
        } finally {
            this.isLoadingBatch = false;
        }
    }
    
    async loadAllCategoryTabsInitial(selectedCategories) {
        /**
         * Load ALL category/part tabs simultaneously (Tree Map Stage 3 / Brace Map Stage 3)
         * Each tab fires 4 LLMs concurrently = N*4 LLMs total!
         * 
         * @param {Array<string>} selectedCategories - Array of category/part names
         */
        const numCategories = selectedCategories.length;
        const totalLLMs = numCategories * 4;
        
        const logPrefix = this.diagramType === 'tree_map' ? 'TreeMap' : 'BraceMap';
        const itemType = this.diagramType === 'tree_map' ? 'category' : 'part';
        const itemTypePlural = this.diagramType === 'tree_map' ? 'categories' : 'parts';
        
        console.log(`[NodePalette-${logPrefix}] Loading ${numCategories} ${itemType} tabs in parallel (${totalLLMs} LLMs total)`);
        
        this.isLoadingBatch = true;
        this.currentBatch = 1;
        
        // Show catapult loading
        this.showCatapultLoading();
        
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        const categoryWord = lang === 'zh' ? (this.diagramType === 'tree_map' ? '类别' : '部分') : itemType;
        const loadingMsg = lang === 'zh' ? 
            `正在加载 ${numCategories} 个${categoryWord}标签 (${totalLLMs} 个AI模型)...` : 
            `Loading ${numCategories} ${itemType} tabs (${totalLLMs} AI models)...`;
        this.updateCatapultLoading(loadingMsg, 0, totalLLMs);
        
        try {
            // CATAPULT! Fire N*4 LLMs total - all categories/parts load in parallel
            console.log(`[NodePalette-${logPrefix}] 🚀 Firing ${numCategories} parallel catapults for ${itemTypePlural}:`, selectedCategories);
            
            // Create parallel catapult promises for each category/part
            const catapultPromises = selectedCategories.map(categoryName => 
                this.loadCategoryTabBatch(categoryName)
            );
            
            // Fire all catapults simultaneously!
            const results = await Promise.all(catapultPromises);
            
            console.log(`[NodePalette-${logPrefix}] ✅ All ${numCategories} ${itemType} tabs loaded successfully`);
            selectedCategories.forEach(categoryName => {
                const count = this.tabNodes[categoryName]?.length || 0;
                console.log(`  - ${categoryName}: ${count} nodes`);
            });
            
            const totalNodes = selectedCategories.reduce((sum, cat) => sum + (this.tabNodes[cat]?.length || 0), 0);
            console.log(`  - Total: ${totalNodes} nodes across all ${itemType} tabs`);
            
            // Update tab counters
            this.updateTabCounters();
            
            // Switch to first category/part tab and load its nodes
            if (selectedCategories.length > 0) {
                this.switchTab(selectedCategories[0]);
            }
            
            // Show completion
            const completeMsg = lang === 'zh' ? 
                `${numCategories} 个${categoryWord}标签已加载完成！` : 
                `All ${numCategories} ${itemType} tabs loaded!`;
            this.updateCatapultLoading(completeMsg, totalLLMs, totalLLMs);
            setTimeout(() => this.hideCatapultLoading(), 800);
            
        } catch (error) {
            console.error(`[NodePalette-${logPrefix}] Error loading ${itemType} tabs:`, error);
            this.hideCatapultLoading();
        } finally {
            this.isLoadingBatch = false;
        }
    }
    
    async loadAllBranchTabsInitial(selectedBranches) {
        /**
         * Load ALL branch tabs simultaneously (MindMap Stage 2)
         * Each tab fires 4 LLMs concurrently = N*4 LLMs total!
         * 
         * @param {Array<string>} selectedBranches - Array of branch names
         */
        const numBranches = selectedBranches.length;
        const totalLLMs = numBranches * 4;
        
        console.log(`[NodePalette-Mindmap] Loading ${numBranches} branch tabs in parallel (${totalLLMs} LLMs total)`);
        
        this.isLoadingBatch = true;
        this.currentBatch = 1;
        
        // Show catapult loading
        this.showCatapultLoading();
        
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        const branchWord = lang === 'zh' ? '分支' : 'branch';
        const branchesWord = lang === 'zh' ? '分支' : 'branches';
        const loadingMsg = lang === 'zh' ? 
            `正在加载 ${numBranches} 个${branchWord}标签 (${totalLLMs} 个AI模型)...` : 
            `Loading ${numBranches} ${branchWord} tabs (${totalLLMs} AI models)...`;
        this.updateCatapultLoading(loadingMsg, 0, totalLLMs);
        
        try {
            // CATAPULT! Fire N*4 LLMs total - all branches load in parallel
            console.log(`[NodePalette-Mindmap] 🚀 Firing ${numBranches} parallel catapults for ${branchesWord}:`, selectedBranches);
            
            // Create parallel catapult promises for each branch
            const catapultPromises = selectedBranches.map(branchName => 
                this.loadCategoryTabBatch(branchName)
            );
            
            // Fire all catapults simultaneously!
            const results = await Promise.all(catapultPromises);
            
            console.log(`[NodePalette-Mindmap] ✅ All ${numBranches} branch tabs loaded successfully`);
            selectedBranches.forEach(branchName => {
                const count = this.tabNodes[branchName]?.length || 0;
                console.log(`  - ${branchName}: ${count} nodes`);
            });
            
            const totalNodes = selectedBranches.reduce((sum, branch) => sum + (this.tabNodes[branch]?.length || 0), 0);
            console.log(`  - Total: ${totalNodes} nodes across all branch tabs`);
            
            // Update tab counters
            this.updateTabCounters();
            
            // Switch to first branch tab and load its nodes
            if (selectedBranches.length > 0) {
                this.switchTab(selectedBranches[0]);
            }
            
            // Show completion
            const completeMsg = lang === 'zh' ? 
                `${numBranches} 个${branchWord}标签已加载完成！` : 
                `All ${numBranches} ${branchWord} tabs loaded!`;
            this.updateCatapultLoading(completeMsg, totalLLMs, totalLLMs);
            setTimeout(() => this.hideCatapultLoading(), 800);
            
        } catch (error) {
            console.error('[NodePalette-Mindmap] Error loading branch tabs:', error);
            this.hideCatapultLoading();
        } finally {
            this.isLoadingBatch = false;
        }
    }
    
    async loadCategoryTabBatch(categoryName) {
        /**
         * Load a single category/part/branch/step tab's batch (used by stage progression)
         * Works for Tree Map (categories), Brace Map (parts), Mindmap (branches), and Flow Map (steps)
         * @param {string} categoryName - Name of the category/part/branch/step to generate children/subparts/substeps for
         */
        const logPrefix = this.diagramType === 'tree_map' ? 'TreeMap' : 
                         this.diagramType === 'brace_map' ? 'BraceMap' : 
                         this.diagramType === 'mindmap' ? 'Mindmap' : 'FlowMap';
        const itemType = this.diagramType === 'tree_map' ? 'category' : 
                        this.diagramType === 'brace_map' ? 'part' : 
                        this.diagramType === 'mindmap' ? 'branch' : 'step';
        
        console.log(`[NodePalette-${logPrefix}] CATAPULT for ${itemType} "${categoryName}" (4 LLMs launching)...`);
        
        const url = '/thinking_mode/node_palette/start';
        let payload;
        
        if (this.diagramType === 'tree_map') {
            payload = {
                session_id: this.sessionId,
                diagram_type: this.diagramType,
                diagram_data: this.diagramData,
                educational_context: this.educationalContext,
                stage: 'children',  // Stage 3: Children generation
                stage_data: {
                    dimension: this.stageData.dimension,
                    category_name: categoryName
                }
            };
        } else if (this.diagramType === 'brace_map') {
            payload = {
                session_id: this.sessionId,
                diagram_type: this.diagramType,
                diagram_data: this.diagramData,
                educational_context: this.educationalContext,
                stage: 'subparts',  // Stage 3: Sub-parts generation
                stage_data: {
                    dimension: this.stageData.dimension,
                    part_name: categoryName
                }
            };
        } else if (this.diagramType === 'mindmap') {
            payload = {
                session_id: this.sessionId,
                diagram_type: this.diagramType,
                diagram_data: this.diagramData,
                educational_context: this.educationalContext,
                stage: 'children',  // Stage 2: Children generation
                stage_data: {
                    branch_name: categoryName
                }
            };
        } else if (this.diagramType === 'flow_map') {
            payload = {
                session_id: this.sessionId,
                diagram_type: this.diagramType,
                diagram_data: this.diagramData,
                educational_context: this.educationalContext,
                stage: 'substeps',  // Stage 3: Sub-steps generation
                stage_data: {
                    dimension: this.stageData.dimension,
                    step_name: categoryName
                }
            };
        }
        
        try {
            // CATAPULT! Fire 4 LLMs concurrently for this category/part
            // Don't show individual loading animation (parent shows overall)
            const nodeCount = await this.catapult(url, payload, categoryName, false);
            
            console.log(`[NodePalette-${logPrefix}] ${itemType.charAt(0).toUpperCase() + itemType.slice(1)} "${categoryName}" loaded: ${nodeCount} nodes`);
            
        } catch (error) {
            console.error(`[NodePalette-${logPrefix}] Error loading ${itemType} "${categoryName}":`, error);
        }
    }
    
    async loadTabBatch(mode) {
        /**
         * Load a single tab's batch (used by loadBothTabsInitial)
         * @param {string} mode - 'similarities' or 'differences'
         */
        console.log(`[NodePalette] CATAPULT for ${mode} tab (4 LLMs launching)...`);
        
        const url = '/thinking_mode/node_palette/start';
        const payload = {
            session_id: this.sessionId,
            diagram_type: this.diagramType,
            diagram_data: this.diagramData,
            educational_context: this.educationalContext,
            mode: mode  // Specify which mode to generate
        };
        
        try {
            // CATAPULT! Fire 4 LLMs concurrently for this tab
            // Don't show individual loading animation (parent shows overall)
            const nodeCount = await this.catapult(url, payload, mode, false);
            
            console.log(`[NodePalette] ${mode} tab loaded: ${nodeCount} nodes`);
            
        } catch (error) {
            console.error(`[NodePalette] Error loading ${mode} tab:`, error);
        }
    }
    
    async catapult(url, payload, targetMode = null, showLoading = true) {
        /**
         * CATAPULT - Fire all 4 LLMs concurrently!
         * 
         * This is the core function that launches 4 LLM requests simultaneously
         * via Server-Sent Events (SSE) and streams nodes back in real-time.
         * 
         * Think of it as a catapult launching 4 projectiles at once - each LLM
         * generates nodes in parallel, and we catch them as they stream in.
         * 
         * @param {string} url - API endpoint (/start or /next_batch)
         * @param {Object} payload - Request payload with session_id, diagram_data, etc.
         * @param {string|null} targetMode - For double bubble: 'similarities' or 'differences'
         * @param {boolean} showLoading - Whether to show loading animation (default: true)
         * @returns {Promise<number>} - Number of nodes generated
         */
        // Show loading animation while catapult is firing (if requested)
        if (showLoading) {
            this.showCatapultLoading();
        }
        
        // Capture current stage generation to validate nodes belong to this batch
        const batchStageGeneration = this.stageGeneration;
        console.log(`[NodePalette] Starting batch for stage generation: ${batchStageGeneration}`);
        
        // Create AbortController for this batch (allows cancellation)
        this.currentBatchAbortController = new AbortController();
        const signal = this.currentBatchAbortController.signal;
        
        let response;
        try {
            response = await auth.fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload),
                signal: signal  // Pass abort signal to fetch
            });
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[NodePalette] Batch request aborted (stage changed)');
                this.hideCatapultLoading();
                this.isLoadingBatch = false;
                return 0;  // Return 0 nodes generated
            }
            throw error;  // Re-throw other errors
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let nodeCount = 0;
        let llmsComplete = 0;
        const batchStartTime = Date.now();
        
        // STREAMING LOOP - Catch nodes as they fly in from all 4 LLMs
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.substring(6));
                        
                        if (data.event === 'batch_start') {
                            // CATAPULT LAUNCHED! All 4 LLMs are now firing
                            console.log(`[NodePalette] CATAPULT LAUNCHED: ${data.llm_count} LLMs firing concurrently`);
                            this.updateCatapultLoading(`Launching ${data.llm_count} LLMs...`, 0, data.llm_count);
                            
                        } else if (data.event === 'node_generated') {
                            const node = data.node;
                            
                            // Check if stage has changed (invalidate old batches)
                            if (this.stageGeneration !== batchStageGeneration) {
                                console.warn(`[NodePalette] ⚠️ Ignoring node from old stage generation (batch: ${batchStageGeneration}, current: ${this.stageGeneration}): ${node.id}`);
                                continue;
                            }
                            
                            nodeCount++;
                            
                            // Update loading animation with live count
                            this.updateCatapultLoading(`Generating ideas... ${nodeCount} nodes received`, llmsComplete, 4);
                            
                            // Add node to appropriate target (tab-specific or main array)
                            if (targetMode && this.tabNodes) {
                                // For double bubble: validate node matches target mode using explicit mode field
                                const nodeMode = node.mode || null;
                                
                                console.log(`[NodePalette] Received node - Target: ${targetMode}, Node mode: ${nodeMode}, Has left/right: ${!!(node.left && node.right)}, ID: ${node.id}`);
                                
                                // Strict validation: node must have the correct mode tag
                                if (nodeMode !== targetMode) {
                                    console.warn(`[NodePalette] ⚠️ Node mode mismatch - expected '${targetMode}', got '${nodeMode}': ${node.id}`);
                                    nodeCount--; // Don't count this node
                                    continue;
                                }
                                
                                // Add to specific tab's storage
                                this.tabNodes[targetMode].push(node);
                                
                                // If this is the CURRENT tab, also render it
                                if (targetMode === this.currentTab) {
                                    this.nodes.push(node);
                                    this.renderNodeCardOnly(node);
                                }
                                
                                // Update tab counters in real-time as nodes arrive
                                this.updateTabCounters();
                            } else {
                                // For other diagrams: add directly and render
                                this.appendNode(node);
                            }
                            
                        } else if (data.event === 'llm_complete') {
                            // One of the 4 LLMs has finished
                            llmsComplete++;
                            console.log(`[NodePalette] ${data.llm} complete: ${data.unique_nodes} unique, ${data.duplicates} duplicates (${data.duration}s)`);
                            
                            // Only update loading animation if we're showing it
                            if (showLoading) {
                                this.updateCatapultLoading(`${data.llm} complete (${llmsComplete}/4)`, llmsComplete, 4);
                            }
                            
                        } else if (data.event === 'batch_complete') {
                            // All 4 LLMs have completed - catapult mission success!
                            const elapsed = ((Date.now() - batchStartTime) / 1000).toFixed(2);
                            console.log(`[NodePalette] CATAPULT COMPLETE (${elapsed}s) | New: ${data.new_unique_nodes} | Total: ${data.total_nodes}`);
                            
                            // Only update/hide loading animation if we're showing it
                            if (showLoading) {
                                this.updateCatapultLoading(`Complete! ${data.new_unique_nodes} new ideas`, 4, 4);
                                // Hide catapult loading animation after brief delay
                                setTimeout(() => this.hideCatapultLoading(), 800);
                            }
                            
                        } else if (data.event === 'error') {
                            console.error(`[NodePalette] CATAPULT ERROR:`, data.message);
                            if (showLoading) {
                                this.hideCatapultLoading();
                            }
                        }
                    }
                }
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[NodePalette] Batch streaming aborted (stage changed)');
                if (showLoading) {
                    this.hideCatapultLoading();
                }
                return nodeCount;  // Return nodes received so far
            }
            throw error;  // Re-throw other errors
        }
        
        return nodeCount;
    }
    
    async loadNextBatch() {
        /**
         * CATAPULT - Fire 4 LLMs concurrently for next batch!
         * 
         * INFINITE SCROLL: This gets called repeatedly as user scrolls down.
         * - Batch 1: Initial load
         * - Batch 2, 3, 4, 5...: Triggered at 2/3 scroll position, NO LIMIT!
         * 
         * Each batch = 1 CATAPULT = 4 LLMs fire concurrently = ~60 new nodes
         */
        if (this.isLoadingBatch) {
            console.warn('[NodePalette] Batch load already in progress, skipping');
            return;
        }
        
        this.isLoadingBatch = true;
        this.currentBatch++;
        
        // Hide transition animation as new batch starts
        this.hideBatchTransition();
        
        console.log(`[NodePalette] CATAPULT batch #${this.currentBatch} (4 LLMs launching)...`);
        
        // Determine URL based on batch number
        const url = this.currentBatch === 1
            ? '/thinking_mode/node_palette/start'
            : `/thinking_mode/node_palette/next_batch`;
        
        // Build base payload
        let payload;
        if (this.currentBatch === 1) {
            payload = {
                session_id: this.sessionId,
                diagram_type: this.diagramType,
                diagram_data: this.diagramData,
                educational_context: this.educationalContext,
                mode: this.currentTab  // For double bubble/multi flow maps
            };
        } else {
            payload = {
                session_id: this.sessionId,
                diagram_type: this.diagramType,
                center_topic: this.centerTopic,
                educational_context: this.educationalContext,
                mode: this.currentTab  // For double bubble/multi flow maps
            };
        }
        
        // Add stage parameters for diagrams with multi-stage workflows
        if (this.usesStages()) {
            if (this.diagramType === 'tree_map') {
                payload.stage = this.currentStage || 'dimensions';
                payload.stage_data = this.stageData || {};
                console.log(`[NodePalette-TreeMap] Loading batch | Stage: ${payload.stage} | Data:`, payload.stage_data);
            } else if (this.diagramType === 'brace_map') {
                payload.stage = this.currentStage || 'dimensions';
                payload.stage_data = this.stageData || {};
                console.log(`[NodePalette-BraceMap] Loading batch | Stage: ${payload.stage} | Data:`, payload.stage_data);
            } else if (this.diagramType === 'mindmap') {
                payload.stage = this.currentStage || 'branches';
                payload.stage_data = this.stageData || {};
                console.log(`[NodePalette-Mindmap] Loading batch | Stage: ${payload.stage} | Data:`, payload.stage_data);
            } else if (this.diagramType === 'flow_map') {
                payload.stage = this.currentStage || 'dimensions';
                payload.stage_data = this.stageData || {};
                console.log(`[NodePalette-FlowMap] Loading batch | Stage: ${payload.stage} | Data:`, payload.stage_data);
            }
        }
        
        try {
            // CATAPULT! Fire 4 LLMs concurrently (works for infinite batches)
            // For double bubble: targetMode determines which tab's nodes to update
            const targetMode = this.usesTabs() ? this.currentTab : null;
            await this.catapult(url, payload, targetMode);
            
            // Show elegant loading animation - ready for next batch when user scrolls!
            this.showBatchTransition();
            
        } catch (error) {
            console.error(`[NodePalette] CATAPULT batch ${this.currentBatch} error:`, error);
        } finally {
            this.isLoadingBatch = false;  // Allow next CATAPULT when user scrolls more
        }
    }
    
    appendNode(node) {
        /**
         * Append a new node card to the masonry layout.
         * 
         * @param {Object} node - Node data from backend
         */
        const metadata = this.getMetadata();
        
        console.log(`[NodePalette-Append] Appending ${metadata.nodeName} to this.nodes array:`, {
            diagram_type: this.diagramType,
            target_array: metadata.arrayName,
            node_type: metadata.nodeType,
            objectType: typeof node,
            nodeKeys: Object.keys(node),
            id: node.id,
            text: node.text,
            llm: node.source_llm,
            currentArrayLength: this.nodes.length
        });
        
        this.nodes.push(node);
        
        console.log(`[NodePalette-Append] After push: this.nodes.length = ${this.nodes.length} ${metadata.nodeNamePlural}`);
        
        const container = document.getElementById('node-palette-grid');
        if (!container) {
            console.error('[NodePalette-Append] ERROR: node-palette-grid container not found!');
            return;
        }
        
        const card = this.createNodeCard(node);
        container.appendChild(card);
        
        console.log(`[NodePalette-Append] Card appended to DOM | Card ID: ${card.dataset.nodeId}`);
        
        // Fade in animation
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 10);
        
        // Update selection counter
        this.updateSelectionCounter();
    }
    
    renderNodeCardOnly(node) {
        /**
         * Render a node card to the DOM WITHOUT adding to this.nodes array.
         * Used when restoring existing nodes from a previous session.
         * 
         * @param {Object} node - Node data (already in this.nodes)
         */
        const container = document.getElementById('node-palette-grid');
        if (!container) {
            console.error('[NodePalette-RenderOnly] ERROR: node-palette-grid container not found!');
            return;
        }
        
        const card = this.createNodeCard(node);
        container.appendChild(card);
        
        // Fade in animation
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 10);
    }
    
    createNodeCard(node) {
        /**
         * Create HTML element for a node card.
         * 
         * @param {Object} node - Node data
         * @returns {HTMLElement} Node card element
         */
        const card = document.createElement('div');
        card.className = `node-card llm-${node.source_llm}`;
        card.dataset.nodeId = node.id;
        card.dataset.llm = node.source_llm;
        
        // Check if this is a difference pair (has left/right fields)
        const isDifferencePair = node.left && node.right;
        
        // Add difference-pair class for styling
        if (isDifferencePair) {
            card.classList.add('difference-pair');
        }
        
        // Check if this node is already selected (important for session restoration)
        const isSelected = this.selectedNodes.has(node.id);
        if (isSelected) {
            card.classList.add('selected');
            console.log(`[NodePalette-CreateCard] Node already selected, applying 'selected' class:`, node.id);
        }
        
        // Add sequence badge for flow map steps (if sequence number exists)
        const sequenceBadgeHTML = (this.diagramType === 'flow_map' && node.sequence) 
            ? `<div class="sequence-badge">${node.sequence}</div>` 
            : '';
        
        let contentHTML;
        if (isDifferencePair) {
            // Difference node: Show on two lines showing the comparison relationship
            const leftText = this.truncateText(node.left, 40);
            const rightText = this.truncateText(node.right, 40);
            const dimension = node.dimension ? this.truncateText(node.dimension, 30) : null;
            
            // Build dimension HTML if present
            const dimensionHTML = dimension 
                ? `<div class="node-dimension">${dimension}</div>` 
                : '';
            
            contentHTML = `
                ${sequenceBadgeHTML}
                <div class="node-card-content node-card-difference">
                    <div class="node-text-split">
                        <div class="node-text-line">${leftText}</div>
                        <div class="node-text-divider">vs</div>
                        <div class="node-text-line">${rightText}</div>
                    </div>
                    ${dimensionHTML}
                    <div class="node-source">${node.source_llm}</div>
                </div>
                <div class="node-checkmark">✓</div>
            `;
        } else {
            // Similarity node: Show as single text
            const displayText = this.truncateText(node.text, 60);
            
            contentHTML = `
                ${sequenceBadgeHTML}
                <div class="node-card-content">
                    <div class="node-text">${displayText}</div>
                    <div class="node-source">${node.source_llm}</div>
                </div>
                <div class="node-checkmark">✓</div>
            `;
        }
        
        card.innerHTML = contentHTML;
        
        // Click handler for selection
        card.addEventListener('click', () => {
            this.toggleNodeSelection(node.id);
        });
        
        return card;
    }
    
    /**
     * Create a pair card for differences tab (using circular nodes with connection)
     */
    createPairCard(pairNode) {
        const card = document.createElement('div');
        card.className = `node-pair-container llm-${pairNode.source_llm}`;
        card.dataset.nodeId = pairNode.id;
        card.dataset.llm = pairNode.source_llm;
        
        // Check if pair is selected
        const isSelected = this.selectedNodes.has(pairNode.id);
        if (isSelected) {
            card.classList.add('selected');
        }
        
        // Get topics
        const leftTopic = this.diagramData?.left || 'Left';
        const rightTopic = this.diagramData?.right || 'Right';
        
        // Truncate text for circular nodes (truncateText handles undefined/null)
        const leftText = this.truncateText(pairNode.left, 50);
        const rightText = this.truncateText(pairNode.right, 50);
        
        card.innerHTML = `
            <!-- Left circular node -->
            <div class="pair-node pair-node-left">
                <div class="pair-node-content">
                    <div class="pair-node-label">${leftTopic}</div>
                    <div class="pair-node-text">${leftText}</div>
                </div>
            </div>
            
            <!-- Animated connection line -->
            <div class="pair-connection">
                <div class="connection-line"></div>
                <div class="connection-icon">⚖️</div>
            </div>
            
            <!-- Right circular node -->
            <div class="pair-node pair-node-right">
                <div class="pair-node-content">
                    <div class="pair-node-label">${rightTopic}</div>
                    <div class="pair-node-text">${rightText}</div>
                </div>
            </div>
            
            <!-- Source badge & checkmark -->
            <div class="pair-source">${pairNode.source_llm}</div>
            <div class="pair-checkmark">✓</div>
        `;
        
        // Click handler - select/deselect entire pair
        card.addEventListener('click', () => {
            this.toggleNodeSelection(pairNode.id);
        });
        
        return card;
    }
    
    /**
     * Render a pair card to DOM (without adding to this.nodes)
     */
    renderPairCardOnly(pairNode) {
        const container = document.getElementById('node-palette-grid');
        if (!container) {
            console.error('[NodePalette-RenderPair] ERROR: node-palette-grid not found!');
            return;
        }
        
        const card = this.createPairCard(pairNode);
        container.appendChild(card);
        
        // Fade in animation
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 10);
    }
    
    truncateText(text, maxLength) {
        /**
         * Truncate text to max length with ellipsis.
         * 
         * @param {string} text - Text to truncate
         * @param {number} maxLength - Maximum length
         * @returns {string} Truncated text
         */
        // Handle undefined/null text
        if (!text) return '';
        
        const str = String(text); // Convert to string just in case
        if (str.length <= maxLength) return str;
        return str.substring(0, maxLength - 3) + '...';
    }
    
    toggleNodeSelection(nodeId) {
        /**
         * Toggle selection state of a node.
         * For double bubble map: updates both global and tab-specific selections.
         * LOCKED TABS: Read-only mode - prevent any selection changes
         * 
         * @param {string} nodeId - Node ID to toggle
         */
        // Check if current tab is locked (read-only mode)
        if (this.lockedTabs.has(this.currentTab)) {
            console.log(`[NodePalette-Selection] ⚠️ Tab "${this.currentTab}" is locked (read-only). Cannot modify selections.`);
            // Show visual feedback that tab is locked
            const tabBtn = document.getElementById(`tab-${this.currentTab}`);
            if (tabBtn) {
                tabBtn.style.animation = 'shake 0.3s';
                setTimeout(() => {
                    tabBtn.style.animation = '';
                }, 300);
            }
            return;
        }
        
        const node = this.nodes.find(n => n.id === nodeId);
        // Handle both regular cards and pair containers
        const card = document.querySelector(`.node-card[data-node-id="${nodeId}"]`) || 
                     document.querySelector(`.node-pair-container[data-node-id="${nodeId}"]`);
        
        if (!node || !card) return;
        
        const wasSelected = this.selectedNodes.has(nodeId);
        
        const metadata = this.getMetadata();
        
        if (wasSelected) {
            // Deselect: remove from both global and tab-specific Sets
            this.selectedNodes.delete(nodeId);
            card.classList.remove('selected');
            
            // For double bubble map: also remove from tab-specific Set
            if (this.usesTabs() && this.tabSelectedNodes && this.currentTab) {
                this.tabSelectedNodes[this.currentTab]?.delete(nodeId);
                console.log(`[NodePalette-Selection] Removed from ${this.currentTab} tab selections`);
            }
            
            // Mark node as deselected
            node.selected = false;
            
            console.log(`[NodePalette-Selection] ✗ Deselected ${metadata.nodeName}:`, {
                id: node.id,
                text: node.text,
                source_llm: node.source_llm,
                mode: node.mode,
                
                // STATUS CHANGE TRACKED
                selected: false,  // Changed from true → false
                added_to_diagram: false,
                
                totalSelected: this.selectedNodes.size,
                totalNodes: this.nodes.length
            });
        } else {
            // Tree Map & Brace Map dimensions tab: SINGLE SELECTION ONLY
            if ((this.diagramType === 'tree_map' || this.diagramType === 'brace_map') && this.currentTab === 'dimensions') {
                // Deselect all other nodes first (enforce single selection)
                this.selectedNodes.forEach(selectedId => {
                    if (selectedId !== nodeId) {
                        const otherCard = document.querySelector(`.node-card[data-node-id="${selectedId}"]`);
                        if (otherCard) {
                            otherCard.classList.remove('selected');
                        }
                        const otherNode = this.nodes.find(n => n.id === selectedId);
                        if (otherNode) {
                            otherNode.selected = false;
                        }
                    }
                });
                this.selectedNodes.clear();
                if (this.tabSelectedNodes && this.tabSelectedNodes[this.currentTab]) {
                    this.tabSelectedNodes[this.currentTab].clear();
                }
                const mapType = this.diagramType === 'tree_map' ? 'TreeMap' : 'BraceMap';
                console.log(`[NodePalette-${mapType}] Cleared previous dimension selection (single-select enforced)`);
            }
            
            // Select: add to both global and tab-specific Sets
            this.selectedNodes.add(nodeId);
            card.classList.add('selected');
            
            // For double bubble map: also add to tab-specific Set
            if (this.usesTabs() && this.tabSelectedNodes && this.currentTab) {
                if (!this.tabSelectedNodes[this.currentTab]) {
                    this.tabSelectedNodes[this.currentTab] = new Set();
                }
                this.tabSelectedNodes[this.currentTab].add(nodeId);
                console.log(`[NodePalette-Selection] Added to ${this.currentTab} tab selections`);
            }
            
            // Mark node as selected - TRACK STATUS CHANGE
            node.selected = true;
            
            console.log(`[NodePalette-Selection] ✓ Selected ${metadata.nodeName}:`, {
                // Node Identity
                id: node.id,
                text: node.text,
                source_llm: node.source_llm,
                batch: node.batch_number,
                mode: node.mode,
                
                // Diagram Context
                diagram_type: this.diagramType,
                node_type: metadata.nodeType,
                target_array: metadata.arrayName,
                
                // STATUS TRACKED - Changed from false → true
                selected: true,  // Just changed!
                added_to_diagram: false,  // Not added yet
                
                // Aggregate Info
                totalSelected: this.selectedNodes.size,
                totalNodes: this.nodes.length,
                selectionRate: `${((this.selectedNodes.size / this.nodes.length) * 100).toFixed(1)}%`,
                
                // Object Structure
                type: typeof node,
                keys: Object.keys(node)
            });
        }
        
        this.updateSelectionCounter();
        
        // Log to backend every 5 selections
        if (this.selectedNodes.size % 5 === 0) {
            this.logSelection(nodeId, !wasSelected, node.text);
        }
    }
    
    updateSelectionCounter() {
        /**
         * Update the selection counter display.
         * For double bubble map: shows total selected across both tabs.
         */
        const counter = document.getElementById('selection-counter');
        const finishBtn = document.getElementById('finish-selection-btn');
        
        // Calculate totals (different for tabs vs single)
        let totalSelected = 0;
        let totalNodes = 0;
        
        if (this.usesTabs()) {
            // Tab-based diagrams (double bubble, multi flow): count across both tabs
            const tabNames = Object.keys(this.tabNodes);
            totalSelected = tabNames.reduce((sum, tabName) => 
                sum + (this.tabSelectedNodes[tabName]?.size || 0), 0);
            totalNodes = tabNames.reduce((sum, tabName) => 
                sum + (this.tabNodes[tabName]?.length || 0), 0);
            
            if (counter) {
                // Show per-tab breakdown
                const tabBreakdown = tabNames.map(tabName => {
                    const selected = this.tabSelectedNodes[tabName]?.size || 0;
                    return `${tabName.charAt(0).toUpperCase() + tabName.slice(0, 3)}: ${selected}`;
                }).join(', ');
                counter.textContent = `Selected: ${totalSelected}/${totalNodes} (${tabBreakdown})`;
            }
        } else {
            // Single-tab diagram
            totalSelected = this.selectedNodes.size;
            totalNodes = this.nodes.length;
            
            if (counter) {
                counter.textContent = `Selected: ${totalSelected}/${totalNodes}`;
            }
        }
        
        // Update finish button
        if (finishBtn) {
            const wasDisabled = finishBtn.disabled;
            finishBtn.disabled = totalSelected === 0;
            finishBtn.textContent = totalSelected > 0 
                ? `Next (${totalSelected} selected)` 
                : 'Next';
            
            // Log button state change
            if (wasDisabled && !finishBtn.disabled) {
                console.log('[NodePalette] Button enabled: "Next (%d selected)"', totalSelected);
            } else if (!wasDisabled && finishBtn.disabled) {
                console.log('[NodePalette] Button disabled: "Next"');
            }
        } else {
            console.error('[NodePalette] Finish button not found when updating counter!');
        }
    }
    
    updateFinishButtonState() {
        /**
         * Alias for updateSelectionCounter() - updates the finish button state.
         * Called when restoring a session to sync button state with selections.
         */
        this.updateSelectionCounter();
    }
    
    async logSelection(nodeId, selected, nodeText) {
        /**
         * Send selection event to backend for logging.
         */
        try {
            await auth.fetch('/thinking_mode/node_palette/select_node', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    node_id: nodeId,
                    selected: selected,
                    node_text: nodeText
                })
            });
        } catch (e) {
            console.error('[NodePalette-Selection] Failed to log selection:', e);
        }
    }
    
    
    showBatchTransition() {
        /**
         * Show elegant loading animation between batches
         */
        const container = document.getElementById('node-palette-grid');
        if (!container) return;
        
        // Check if transition element already exists
        let transition = document.getElementById('batch-transition');
        if (!transition) {
            transition = document.createElement('div');
            transition.id = 'batch-transition';
            transition.className = 'batch-transition';
            transition.innerHTML = `
                <div class="transition-content">
                    <div class="transition-spinner">
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                    </div>
                    <div class="transition-text">Preparing next batch...</div>
                    <div class="transition-subtext">Scroll down for more ideas</div>
                </div>
            `;
            container.appendChild(transition);
        }
        
        // Fade in
        setTimeout(() => {
            transition.style.opacity = '1';
            transition.style.transform = 'translateY(0)';
        }, 10);
    }
    
    hideBatchTransition() {
        /**
         * Hide batch transition animation
         */
        const transition = document.getElementById('batch-transition');
        if (transition) {
            transition.style.opacity = '0';
            transition.style.transform = 'translateY(20px)';
            setTimeout(() => {
                transition.remove();
            }, 400);
        }
    }
    
    showTabLoading(message = 'Loading nodes...') {
        /**
         * Show loading overlay in the current tab's grid
         * (Better for tabs - more visible than header loading)
         */
        const grid = document.getElementById('node-palette-grid');
        if (!grid) return;
        
        // Check if loading overlay already exists
        let overlay = document.getElementById('tab-loading-overlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'tab-loading-overlay';
            overlay.className = 'tab-loading-overlay';
            overlay.innerHTML = `
                <div class="tab-loading-content">
                    <div class="tab-loading-spinner">
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                    </div>
                    <div class="tab-loading-text">${message}</div>
                </div>
            `;
            grid.appendChild(overlay);
        } else {
            // Update message if overlay exists
            const textEl = overlay.querySelector('.tab-loading-text');
            if (textEl) textEl.textContent = message;
        }
        
        // Fade in
        setTimeout(() => {
            overlay.style.opacity = '1';
        }, 10);
    }
    
    hideTabLoading() {
        /**
         * Hide tab loading overlay
         */
        const overlay = document.getElementById('tab-loading-overlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.remove();
            }, 300);
        }
    }
    
    showCatapultLoading() {
        /**
         * Show CATAPULT loading animation - live updates while LLMs fire!
         */
        const header = document.getElementById('node-palette-header');
        if (!header) return;
        
        // Check if catapult loader already exists
        let loader = document.getElementById('catapult-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'catapult-loader';
            loader.className = 'catapult-loader';
            loader.innerHTML = `
                <div class="catapult-spinner">
                    <div class="spinner-circle"></div>
                    <div class="spinner-circle"></div>
                    <div class="spinner-circle"></div>
                    <div class="spinner-circle"></div>
                </div>
                <div class="catapult-status">Launching CATAPULT...</div>
                <div class="catapult-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                </div>
            `;
            header.appendChild(loader);
        }
        
        // Fade in
        setTimeout(() => {
            loader.style.opacity = '1';
        }, 10);
    }
    
    updateCatapultLoading(status, completedLLMs, totalLLMs) {
        /**
         * Update CATAPULT loading animation with live progress
         */
        const loader = document.getElementById('catapult-loader');
        if (!loader) return;
        
        const statusEl = loader.querySelector('.catapult-status');
        const progressFill = loader.querySelector('.progress-fill');
        
        if (statusEl) {
            statusEl.textContent = status;
        }
        
        if (progressFill) {
            const percentage = (completedLLMs / totalLLMs) * 100;
            progressFill.style.width = `${percentage}%`;
        }
    }
    
    hideCatapultLoading() {
        /**
         * Hide CATAPULT loading animation
         */
        const loader = document.getElementById('catapult-loader');
        if (loader) {
            loader.style.opacity = '0';
            setTimeout(() => {
                loader.remove();
            }, 300);
        }
    }
    
    async finishSelection() {
        /**
         * Finish Node Palette, add selected nodes to diagram.
         * For double bubble map: gather selections from BOTH tabs.
         */
        const metadata = this.getMetadata();
        
        console.log('[NodePalette-Finish] ========================================');
        console.log('[NodePalette-Finish] USER CLICKED FINISH BUTTON');
        console.log('[NodePalette-Finish] ========================================');
        console.log(`[NodePalette-Finish] Diagram: ${this.diagramType} | Node type: ${metadata.nodeNamePlural}`);
        
        // For double bubble map: gather ALL selected nodes from BOTH tabs
        let allSelectedNodes = [];
        let totalSelectedCount = 0;
        let totalNodesCount = 0;
        
        if (this.usesTabs()) {
            console.log('[NodePalette-Finish] Tab-based diagram detected - gathering from BOTH tabs');
            
            // Merge selections from both tabs (works for double bubble & multi flow)
            const tabNames = Object.keys(this.tabSelectedNodes);
            const allSelectedSets = tabNames.map(tabName => this.tabSelectedNodes[tabName] || new Set());
            const mergedSelectedIds = new Set(allSelectedSets.flatMap(set => [...set]));
            
            totalSelectedCount = mergedSelectedIds.size;
            
            // Log selections per tab
            tabNames.forEach(tabName => {
                const count = this.tabSelectedNodes[tabName]?.size || 0;
                console.log(`[NodePalette-Finish] ${tabName} tab: ${count} selected`);
            });
            console.log(`[NodePalette-Finish] Total selected across both tabs: ${totalSelectedCount}`);
            
            // Gather nodes from BOTH tabs
            const allNodes = tabNames.flatMap(tabName => this.tabNodes[tabName] || []);
            totalNodesCount = allNodes.length;
            
            const nodeCounts = tabNames.map(tabName => 
                `${tabName}=${this.tabNodes[tabName]?.length || 0}`
            ).join(', ');
            console.log(`[NodePalette-Finish] Total nodes generated: ${nodeCounts}, total=${totalNodesCount}`);
            
            // Filter for selected & new nodes
            allSelectedNodes = allNodes.filter(n => 
                mergedSelectedIds.has(n.id) && !n.added_to_diagram
            );
            
            const alreadyAddedCount = allNodes.filter(n => 
                mergedSelectedIds.has(n.id) && n.added_to_diagram
            ).length;
            
            console.log(`[NodePalette-Finish] Filtered ${allSelectedNodes.length} NEW nodes (${alreadyAddedCount} already added)`);
            
        } else {
            // Single-tab diagrams: use existing logic
            totalSelectedCount = this.selectedNodes.size;
            totalNodesCount = this.nodes.length;
            
            console.log(`[NodePalette-Finish] Single-tab diagram: ${totalSelectedCount}/${totalNodesCount} selected`);
            console.log('[NodePalette-Finish] selectedNodes Set (IDs):', Array.from(this.selectedNodes));
            
            allSelectedNodes = this.nodes.filter(n => 
                this.selectedNodes.has(n.id) && !n.added_to_diagram
            );
            
            const alreadyAddedCount = this.nodes.filter(n => 
                this.selectedNodes.has(n.id) && n.added_to_diagram
            ).length;
            
            console.log(`[NodePalette-Finish] Filtered ${allSelectedNodes.length} NEW ${metadata.nodeNamePlural} (${alreadyAddedCount} already added)`);
        }
        
        // Check if any nodes selected
        if (totalSelectedCount === 0) {
            console.warn(`[NodePalette-Finish] ⚠ No ${metadata.nodeNamePlural} selected, showing alert`);
            alert(`Please select at least one ${metadata.nodeName}`);
            return;
        }
        
        // Check if there are any NEW nodes to add
        if (allSelectedNodes.length === 0) {
            console.warn(`[NodePalette-Finish] ⚠ All selected ${metadata.nodeNamePlural} were already added. Nothing to do.`);
            const msg = metadata.language === 'zh' ? 
                '所有选中的节点都已添加到图中。' : 
                'All selected nodes have already been added to the diagram.';
            alert(msg);
            return;
        }
        
        console.log(`[NodePalette-Finish] Selected ${metadata.nodeName} details (NEW only):`);
        allSelectedNodes.forEach((node, idx) => {
            const modeInfo = node.mode ? ` | Mode: ${node.mode}` : '';
            console.log(`  [${idx + 1}/${allSelectedNodes.length}] ID: ${node.id}${modeInfo} | LLM: ${node.source_llm} | Text: "${node.text || node.left + ' vs ' + node.right}"`);
        });
        
        // Log finish event to backend
        console.log('[NodePalette-Finish] Sending finish event to backend...');
        try {
            // Gather all selected IDs (merge from tabs if needed)
            let allSelectedIds;
            if (this.usesTabs()) {
                const tabNames = Object.keys(this.tabSelectedNodes);
                allSelectedIds = tabNames.flatMap(tabName => 
                    [...(this.tabSelectedNodes[tabName] || new Set())]
                );
            } else {
                allSelectedIds = Array.from(this.selectedNodes);
            }
            
            const response = await auth.fetch('/thinking_mode/node_palette/finish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    selected_node_ids: allSelectedIds,
                    total_nodes_generated: totalNodesCount,
                    batches_loaded: this.currentBatch,
                    diagram_type: this.diagramType  // Add diagram type for cleanup
                })
            });
            console.log('[NodePalette-Finish] Backend response:', response.status, response.statusText);
        } catch (e) {
            console.error('[NodePalette-Finish] Failed to log finish event:', e);
        }
        
        // Hide Node Palette BEFORE adding nodes (so user sees the result)
        console.log('[NodePalette-Finish] Hiding Node Palette panel...');
        this.hideBatchTransition(); // Clean up any active transition
        this.hidePalettePanel();
        
        // Wait for panel to hide
        await new Promise(resolve => setTimeout(resolve, 350));
        
        // Add selected nodes to diagram (method name kept for backward compatibility)
        console.log(`[NodePalette-Finish] Starting ${metadata.nodeName} assembly to ${this.diagramType}...`);
        await this.assembleNodesToCircleMap(allSelectedNodes);
        
        console.log('[NodePalette-Finish] ========================================');
        console.log('[NodePalette-Finish] ✓ FINISH COMPLETE');
        console.log('[NodePalette-Finish] ========================================');
    }
    
    async assembleNodesToCircleMap(selectedNodes) {
        /**
         * Add selected nodes to the diagram.
         * Uses InteractiveEditor API for robust integration.
         * Works for Circle Map, Bubble Map, and other diagram types.
         * 
         * Special handling for Double Bubble Map with mode-aware assembly.
         * 
         * @param {Array} selectedNodes - Array of selected node objects
         */
        
        // Special handling for diagrams with mode-aware nodes
        console.log(`[NodePalette-Assemble] Router check: diagramType="${this.diagramType}"`);
        if (this.diagramType === 'double_bubble_map') {
            console.log('[NodePalette-Assemble] ✓ Routing to assembleNodesToDoubleBubbleMap()');
            return await this.assembleNodesToDoubleBubbleMap(selectedNodes);
        }
        if (this.diagramType === 'multi_flow_map') {
            console.log('[NodePalette-Assemble] ✓ Routing to assembleNodesToMultiFlowMap()');
            return await this.assembleNodesToMultiFlowMap(selectedNodes);
        }
        if (this.diagramType === 'bridge_map') {
            console.log('[NodePalette-Assemble] ✓ Routing to assembleNodesToBridgeMap()');
            return await this.assembleNodesToBridgeMap(selectedNodes);
        }
        if (this.diagramType === 'tree_map') {
            console.log('[NodePalette-Assemble] ✓ Routing to assembleNodesToTreeMap()');
            return await this.assembleNodesToTreeMap(selectedNodes);
        }
        if (this.diagramType === 'mindmap') {
            console.log('[NodePalette-Assemble] ✓ Routing to assembleNodesToMindMap()');
            return await this.assembleNodesToMindMap(selectedNodes);
        }
        
        // Generic handling for all other diagram types
        console.log('[NodePalette-Assemble] Using generic assembly logic');
        const metadata = this.getMetadata();
        
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] ASSEMBLING ${metadata.nodeNamePlural.toUpperCase()} TO ${this.diagramType.toUpperCase()}`);
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] Diagram: ${this.diagramType}`);
        console.log(`[NodePalette-Assemble] Target array: spec.${metadata.arrayName}`);
        console.log(`[NodePalette-Assemble] Node type: ${metadata.nodeType}`);
        console.log(`[NodePalette-Assemble] Input: Received ${selectedNodes.length} selected ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Assemble] ${metadata.nodeName.charAt(0).toUpperCase() + metadata.nodeName.slice(1)} objects structure:`);
        selectedNodes.forEach((node, idx) => {
            console.log(`  [${idx + 1}] Type: ${typeof node} | Keys: ${Object.keys(node).join(', ')}`);
            console.log(`       ID: ${node.id} | Text: "${node.text}" | LLM: ${node.source_llm}`);
        });
        
        // Step 1: Verify editor exists
        const editor = window.currentEditor;
        console.log('[NodePalette-Assemble] Editor: %s', editor ? '✓ Found' : '✗ Not found');
        
        if (!editor) {
            console.error('[NodePalette-Assemble] ERROR: No active editor found');
            alert('Error: No active editor found. Please try refreshing the page.');
            return;
        }
        
        console.log('[NodePalette-Assemble] Editor type: %s', editor.diagramType);
        console.log('[NodePalette-Assemble] Editor currentSpec: %s', !!editor.currentSpec);
        
        // Step 2: Verify spec exists
        const currentSpec = editor.currentSpec;
        if (!currentSpec) {
            console.error('[NodePalette-Assemble] ERROR: No current spec found');
            alert('Error: No diagram specification found. Please try refreshing the page.');
            return;
        }
        
        const arrayName = metadata.arrayName;
        
        console.log('[NodePalette-Assemble] Spec keys: %s', Object.keys(currentSpec).join(', '));
        console.log(`[NodePalette-Assemble] Current spec.${arrayName}: %s`, Array.isArray(currentSpec[arrayName]) ? `Array[${currentSpec[arrayName].length}]` : typeof currentSpec[arrayName]);
        
        // Step 3: Initialize array if needed
        if (!currentSpec[arrayName]) {
            console.log(`[NodePalette-Assemble] Initializing new spec.${arrayName} array`);
            currentSpec[arrayName] = [];
        }
        
        const beforeCount = currentSpec[arrayName].length;
        console.log(`[NodePalette-Assemble] BEFORE: spec.${arrayName} has ${beforeCount} items`);
        if (beforeCount > 0) {
            console.log(`[NodePalette-Assemble] Existing ${metadata.nodeNamePlural}:`);
            currentSpec[arrayName].forEach((item, idx) => {
                console.log(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
            });
        }
        
        // ========================================
        // STEP 4: SMART REPLACE LOGIC
        // ========================================
        // Analyze existing nodes and choose strategy:
        // - REPLACE: All placeholders → clear all, add selected
        // - SMART_REPLACE: Mix of placeholders + user nodes → keep user nodes, add selected
        // - APPEND: All user nodes → append selected (current behavior)
        
        console.log('[NodePalette-Assemble] ========================================');
        console.log('[NodePalette-Assemble] DETECTION PHASE: Analyzing existing nodes');
        console.log('[NodePalette-Assemble] ========================================');
        
        // Analyze existing nodes
        const existingNodes = currentSpec[arrayName] || [];
        const placeholders = [];
        const userNodes = [];
        
        existingNodes.forEach((nodeText, idx) => {
            const isPlaceholder = this.isPlaceholder(nodeText);
            if (isPlaceholder) {
                placeholders.push({ index: idx, text: nodeText });
            } else {
                userNodes.push({ index: idx, text: nodeText });
            }
            console.log(`  [${idx}] "${nodeText}" -> ${isPlaceholder ? 'PLACEHOLDER' : 'USER NODE'}`);
        });
        
        console.log(`[NodePalette-Assemble] Analysis complete:`);
        console.log(`[NodePalette-Assemble]   Total existing: ${existingNodes.length}`);
        console.log(`[NodePalette-Assemble]   Placeholders: ${placeholders.length}`);
        console.log(`[NodePalette-Assemble]   User nodes: ${userNodes.length}`);
        console.log(`[NodePalette-Assemble]   Selected to add: ${selectedNodes.length}`);
        
        // ========================================
        // UNIFIED EXECUTION - Elegant Approach
        // ========================================
        // This single approach handles all cases:
        // - Empty array: userNodes=[], result=[selected]
        // - All placeholders: userNodes=[] (filtered out), result=[selected]
        // - Mix: userNodes=[kept], result=[kept, selected]
        // - All user nodes: userNodes=[all], result=[all, selected]
        
        console.log('[NodePalette-Assemble] ========================================');
        console.log('[NodePalette-Assemble] EXECUTION: Building new array');
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] Keeping ${userNodes.length} user nodes`);
        console.log(`[NodePalette-Assemble] Adding ${selectedNodes.length} selected ${metadata.nodeNamePlural}`);
        
        // Build new array: keep user nodes + add selected nodes
        const newArray = [];
        const addedNodeIds = [];
        
        // Keep user nodes (placeholders automatically excluded)
        userNodes.forEach(userNode => {
            newArray.push(userNode.text);
            console.log(`  KEEPING user node: "${userNode.text}"`);
        });
        
        // Add selected nodes
        selectedNodes.forEach((node, idx) => {
            newArray.push(node.text);
            node.added_to_diagram = true;
            addedNodeIds.push(node.id);
            console.log(`  [${idx + 1}/${selectedNodes.length}] ADDED: "${node.text}" | LLM: ${node.source_llm} | ID: ${node.id}`);
        });
        
        // Update spec
        currentSpec[arrayName] = newArray;
        
        console.log(`[NodePalette-Assemble] ✓ Complete: ${userNodes.length} kept + ${selectedNodes.length} added = ${newArray.length} total`);
        
        console.log(`[NodePalette-Assemble] Successfully processed ${addedNodeIds.length} ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Assemble] Added node IDs:`, addedNodeIds);
        
        const afterCount = currentSpec[arrayName].length;
        const diff = afterCount - beforeCount;
        console.log('[NodePalette-Assemble] ========================================');
        console.log('[NodePalette-Assemble] BEFORE/AFTER SUMMARY');
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] BEFORE: ${beforeCount} ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Assemble]   - Placeholders: ${placeholders.length} (auto-excluded)`);
        console.log(`[NodePalette-Assemble]   - User nodes: ${userNodes.length} (kept)`);
        console.log(`[NodePalette-Assemble] AFTER: ${afterCount} ${metadata.nodeNamePlural} (${diff >= 0 ? '+' : ''}${diff})`);
        console.log(`[NodePalette-Assemble] Final spec.${arrayName} array:`);
        currentSpec[arrayName].forEach((item, idx) => {
            console.log(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
        });
        
        // Step 5: Re-render the diagram
        console.log('[NodePalette-Assemble] Rendering diagram...');
        try {
            // Try different render methods based on editor type
            if (typeof editor.render === 'function') {
                console.log('[NodePalette-Assemble] Calling editor.render()...');
                const renderResult = await editor.render();
                console.log('[NodePalette-Assemble] ✓ editor.render() completed:', renderResult);
            } else if (typeof editor.renderDiagram === 'function') {
                console.log('[NodePalette-Assemble] Calling editor.renderDiagram()...');
                await editor.renderDiagram(currentSpec);
                console.log('[NodePalette-Assemble] ✓ editor.renderDiagram() completed');
            } else if (typeof editor.update === 'function') {
                console.log('[NodePalette-Assemble] Calling editor.update()...');
                await editor.update();
                console.log('[NodePalette-Assemble] ✓ editor.update() completed');
            } else {
                console.error('[NodePalette-Assemble] ERROR: No render method found on editor');
                console.error('[NodePalette-Assemble] Available methods:', Object.keys(editor).filter(k => typeof editor[k] === 'function'));
                alert('Error: Cannot render diagram. Please try refreshing the page.');
                return;
            }
            
            // Step 6: Verify the rendered nodes
            console.log('[NodePalette-Assemble] Verifying rendered nodes in DOM...');
            const nodeElements = document.querySelectorAll(`[data-node-type="${metadata.nodeType}"]`);
            console.log(`[NodePalette-Assemble] Found ${nodeElements.length} ${metadata.nodeNamePlural} in DOM with [data-node-type="${metadata.nodeType}"]`);
            nodeElements.forEach((elem, idx) => {
                const nodeId = elem.getAttribute('data-node-id');
                const arrayIndex = elem.getAttribute('data-array-index');
                const textElement = elem.querySelector('text');
                const textContent = textElement ? textElement.textContent : 'NO TEXT ELEMENT';
                console.log(`  [${idx}] ID: ${nodeId} | Index: ${arrayIndex} | Type: ${metadata.nodeType} | Text: "${textContent}"`);
            });
            
            // Step 7: Save to history
            console.log('[NodePalette-Assemble] Saving to history...');
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
                console.log('[NodePalette-Assemble] ✓ History saved via saveHistoryState');
            } else if (typeof editor.saveHistory === 'function') {
                editor.saveHistory('node_palette_add');
                console.log('[NodePalette-Assemble] ✓ History saved via saveHistory');
            } else {
                console.warn('[NodePalette-Assemble] ⚠ No history save method found (skipping)');
            }
            
            console.log('[NodePalette-Assemble] ========================================');
            console.log(`[NodePalette-Assemble] ✓ SUCCESS: ${selectedNodes.length} ${metadata.nodeNamePlural} added to ${this.diagramType}`);
            console.log('[NodePalette-Assemble] ========================================');
            
            // FINAL STATUS SUMMARY - Complete tracking report
            console.log(`[NodePalette-Assemble] FINAL STATUS SUMMARY:`);
            console.log(`[NodePalette-Assemble]   Total nodes generated: ${this.nodes.length}`);
            console.log(`[NodePalette-Assemble]   Total nodes selected: ${this.selectedNodes.size}`);
            console.log(`[NodePalette-Assemble]   Total nodes added to ${this.diagramType}: ${selectedNodes.length}`);
            console.log(`[NodePalette-Assemble]   Selection rate: ${((this.selectedNodes.size / this.nodes.length) * 100).toFixed(1)}%`);
            console.log(`[NodePalette-Assemble] All added nodes now have: selected=true, added_to_diagram=true`);
            
        } catch (error) {
            console.error('[NodePalette-Assemble] ========================================');
            console.error('[NodePalette-Assemble] ✗ ERROR: Failed to render Circle Map');
            console.error('[NodePalette-Assemble] Error type:', error.constructor.name);
            console.error('[NodePalette-Assemble] Error message:', error.message);
            console.error('[NodePalette-Assemble] Error stack:', error.stack);
            console.error('[NodePalette-Assemble] Current spec at error:', JSON.stringify(currentSpec, null, 2));
            console.error('[NodePalette-Assemble] ========================================');
            alert(`Error rendering diagram: ${error.message}\n\nPlease check console for details.`);
        }
    }
    
    async assembleNodesToDoubleBubbleMap(selectedNodes) {
        /**
         * Specialized assembly for Double Bubble Map.
         * Handles two node types with different data structures:
         * - Similarities: simple text → spec.similarities[]
         * - Differences: paired text → spec.left_differences[] + spec.right_differences[]
         * 
         * @param {Array} selectedNodes - Array of selected node objects
         */
        
        console.log('[DoubleBubble-Assemble] ========================================');
        console.log('[DoubleBubble-Assemble] ASSEMBLING NODES TO DOUBLE BUBBLE MAP');
        console.log('[DoubleBubble-Assemble] ========================================');
        console.log(`[DoubleBubble-Assemble] Total selected nodes: ${selectedNodes.length}`);
        
        // Verify editor
        const editor = window.currentEditor;
        if (!editor) {
            console.error('[DoubleBubble-Assemble] ERROR: No active editor found');
            alert('Error: No active editor found. Please try refreshing the page.');
            return;
        }
        
        const currentSpec = editor.currentSpec;
        if (!currentSpec) {
            console.error('[DoubleBubble-Assemble] ERROR: No current spec found');
            alert('Error: No diagram specification found. Please try refreshing the page.');
            return;
        }
        
        // DEBUG: Log all selected nodes with their mode
        console.log('[DoubleBubble-Assemble] Selected nodes details:');
        selectedNodes.forEach((node, idx) => {
            console.log(`  [${idx + 1}/${selectedNodes.length}] mode="${node.mode}" | left="${node.left||'N/A'}" | right="${node.right||'N/A'}" | text="${node.text}" | ID: ${node.id}`);
        });
        
        // Group nodes by mode
        const similaritiesNodes = selectedNodes.filter(n => n.mode === 'similarities');
        const differencesNodes = selectedNodes.filter(n => n.mode === 'differences');
        
        console.log('[DoubleBubble-Assemble] Node distribution after filtering:');
        console.log(`  Similarities: ${similaritiesNodes.length} nodes`);
        console.log(`  Differences: ${differencesNodes.length} nodes`);
        
        // DEBUG: Log detailed breakdown
        if (similaritiesNodes.length > 0) {
            console.log('[DoubleBubble-Assemble] Similarities node IDs:', similaritiesNodes.map(n => n.id));
        }
        if (differencesNodes.length > 0) {
            console.log('[DoubleBubble-Assemble] Differences node IDs:', differencesNodes.map(n => n.id));
        }
        
        // Initialize arrays if needed
        if (!Array.isArray(currentSpec.similarities)) {
            currentSpec.similarities = [];
        }
        if (!Array.isArray(currentSpec.left_differences)) {
            currentSpec.left_differences = [];
        }
        if (!Array.isArray(currentSpec.right_differences)) {
            currentSpec.right_differences = [];
        }
        
        const beforeSimilarities = currentSpec.similarities.length;
        const beforeLeftDiff = currentSpec.left_differences.length;
        const beforeRightDiff = currentSpec.right_differences.length;
        
        // ========================================
        // SMART PLACEHOLDER REPLACEMENT
        // ========================================
        console.log('[DoubleBubble-Assemble] ========================================');
        console.log('[DoubleBubble-Assemble] ANALYZING EXISTING NODES FOR PLACEHOLDERS');
        console.log('[DoubleBubble-Assemble] ========================================');
        
        // Analyze similarities array
        const simPlaceholders = [];
        const simUserNodes = [];
        currentSpec.similarities.forEach((text, idx) => {
            const isPlaceholder = this.isPlaceholder(text);
            if (isPlaceholder) {
                simPlaceholders.push({ index: idx, text: text });
            } else {
                simUserNodes.push({ index: idx, text: text });
            }
        });
        
        // Analyze differences arrays (they're paired, so analyze together)
        const diffPlaceholders = [];
        const diffUserNodes = [];
        for (let i = 0; i < Math.max(currentSpec.left_differences.length, currentSpec.right_differences.length); i++) {
            const leftText = currentSpec.left_differences[i] || '';
            const rightText = currentSpec.right_differences[i] || '';
            const isPlaceholder = this.isPlaceholder(leftText) || this.isPlaceholder(rightText);
            
            if (isPlaceholder) {
                diffPlaceholders.push({ index: i, left: leftText, right: rightText });
            } else {
                diffUserNodes.push({ index: i, left: leftText, right: rightText });
            }
        }
        
        console.log('[DoubleBubble-Assemble] Similarities:');
        console.log(`  Total: ${currentSpec.similarities.length}`);
        console.log(`  Placeholders: ${simPlaceholders.length}`);
        console.log(`  User nodes: ${simUserNodes.length}`);
        
        console.log('[DoubleBubble-Assemble] Differences:');
        console.log(`  Total pairs: ${Math.max(currentSpec.left_differences.length, currentSpec.right_differences.length)}`);
        console.log(`  Placeholder pairs: ${diffPlaceholders.length}`);
        console.log(`  User pairs: ${diffUserNodes.length}`);
        
        // Track added nodes
        const addedNodeIds = [];
        
        // Process similarities - SMART REPLACE
        if (similaritiesNodes.length > 0) {
            console.log('[DoubleBubble-Assemble] ========================================');
            console.log('[DoubleBubble-Assemble] PROCESSING SIMILARITIES (SMART REPLACE)');
            console.log('[DoubleBubble-Assemble] ========================================');
            
            // Build new array: keep user nodes + add selected nodes
            const newSimilarities = [];
            
            // Keep user nodes (filter out placeholders)
            simUserNodes.forEach(userNode => {
                newSimilarities.push(userNode.text);
                console.log(`  KEEPING user node: "${userNode.text}"`);
            });
            
            // Add selected nodes
            similaritiesNodes.forEach((node, idx) => {
                newSimilarities.push(node.text);
                node.added_to_diagram = true;
                addedNodeIds.push(node.id);
                console.log(`  [${idx + 1}/${similaritiesNodes.length}] ADDED: "${node.text}" | LLM: ${node.source_llm} | ID: ${node.id}`);
            });
            
            // Replace array
            currentSpec.similarities = newSimilarities;
            console.log(`[DoubleBubble-Assemble] ✓ Similarities: ${simUserNodes.length} kept + ${similaritiesNodes.length} added = ${newSimilarities.length} total`);
        }
        
        // Process differences - SMART REPLACE (paired arrays)
        if (differencesNodes.length > 0) {
            console.log('[DoubleBubble-Assemble] ========================================');
            console.log('[DoubleBubble-Assemble] PROCESSING DIFFERENCES (SMART REPLACE)');
            console.log('[DoubleBubble-Assemble] ========================================');
            
            // Build new arrays: keep user pairs + add selected pairs
            const newLeftDiff = [];
            const newRightDiff = [];
            
            // Keep user pairs (filter out placeholder pairs)
            diffUserNodes.forEach(userPair => {
                newLeftDiff.push(userPair.left);
                newRightDiff.push(userPair.right);
                console.log(`  KEEPING user pair: "${userPair.left}" | "${userPair.right}"`);
            });
            
            // Add selected pairs
            differencesNodes.forEach((node, idx) => {
                // Verify node has required structure
                if (!node.left || !node.right) {
                    console.warn(`[DoubleBubble-Assemble] ⚠️ Skipping malformed difference node (missing left/right): ${node.id}`);
                    console.warn(`  Node keys: ${Object.keys(node).join(', ')}`);
                    console.warn(`  Text: "${node.text}"`);
                    return;
                }
                
                newLeftDiff.push(node.left);
                newRightDiff.push(node.right);
                node.added_to_diagram = true;
                addedNodeIds.push(node.id);
                
                const dimensionInfo = node.dimension ? ` | Dimension: "${node.dimension}"` : '';
                console.log(`  [${idx + 1}/${differencesNodes.length}] ADDED: "${node.left}" | "${node.right}"${dimensionInfo} | LLM: ${node.source_llm} | ID: ${node.id}`);
            });
            
            // Replace arrays
            currentSpec.left_differences = newLeftDiff;
            currentSpec.right_differences = newRightDiff;
            console.log(`[DoubleBubble-Assemble] ✓ Differences: ${diffUserNodes.length} kept + ${differencesNodes.length} added = ${newLeftDiff.length} total pairs`);
        }
        
        // Summary
        const afterSimilarities = currentSpec.similarities.length;
        const afterLeftDiff = currentSpec.left_differences.length;
        const afterRightDiff = currentSpec.right_differences.length;
        
        console.log('[DoubleBubble-Assemble] ========================================');
        console.log('[DoubleBubble-Assemble] BEFORE/AFTER SUMMARY');
        console.log('[DoubleBubble-Assemble] ========================================');
        console.log(`[DoubleBubble-Assemble] Similarities: ${beforeSimilarities} → ${afterSimilarities} (+${afterSimilarities - beforeSimilarities})`);
        console.log(`[DoubleBubble-Assemble] Left Differences: ${beforeLeftDiff} → ${afterLeftDiff} (+${afterLeftDiff - beforeLeftDiff})`);
        console.log(`[DoubleBubble-Assemble] Right Differences: ${beforeRightDiff} → ${afterRightDiff} (+${afterRightDiff - beforeRightDiff})`);
        
        // DEBUG: Show what's actually in the arrays now
        console.log('[DoubleBubble-Assemble] Current spec.similarities:', currentSpec.similarities);
        console.log('[DoubleBubble-Assemble] Current spec.left_differences:', currentSpec.left_differences);
        console.log('[DoubleBubble-Assemble] Current spec.right_differences:', currentSpec.right_differences);
        
        // Verify paired arrays are synchronized
        if (currentSpec.left_differences.length !== currentSpec.right_differences.length) {
            console.error('[DoubleBubble-Assemble] ⚠️ WARNING: left_differences and right_differences arrays are out of sync!');
            console.error(`  Left: ${currentSpec.left_differences.length}, Right: ${currentSpec.right_differences.length}`);
        }
        
        // Re-render the diagram
        console.log('[DoubleBubble-Assemble] Rendering diagram...');
        try {
            if (typeof editor.renderDiagram === 'function') {
                await editor.renderDiagram(currentSpec);
                console.log('[DoubleBubble-Assemble] ✓ Diagram rendered successfully');
            } else if (typeof editor.render === 'function') {
                await editor.render();
                console.log('[DoubleBubble-Assemble] ✓ Diagram rendered successfully');
            } else {
                console.error('[DoubleBubble-Assemble] ERROR: No render method found');
                alert('Error: Cannot render diagram. Please try refreshing the page.');
                return;
            }
            
            // Save to history
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
                console.log('[DoubleBubble-Assemble] ✓ History saved');
            } else if (typeof editor.saveHistory === 'function') {
                editor.saveHistory('node_palette_add');
                console.log('[DoubleBubble-Assemble] ✓ History saved');
            }
            
            console.log('[DoubleBubble-Assemble] ========================================');
            console.log('[DoubleBubble-Assemble] ✓ SUCCESS: Double Bubble Map updated');
            console.log('[DoubleBubble-Assemble] ========================================');
            console.log(`[DoubleBubble-Assemble] Added ${addedNodeIds.length} nodes total`);
            console.log(`[DoubleBubble-Assemble] Node IDs:`, addedNodeIds);
            
        } catch (error) {
            console.error('[DoubleBubble-Assemble] ========================================');
            console.error('[DoubleBubble-Assemble] ✗ ERROR: Failed to render diagram');
            console.error('[DoubleBubble-Assemble] Error:', error.message);
            console.error('[DoubleBubble-Assemble] Stack:', error.stack);
            console.error('[DoubleBubble-Assemble] ========================================');
            alert(`Error rendering diagram: ${error.message}\n\nPlease check console for details.`);
        }
    }
    
    async assembleNodesToMultiFlowMap(selectedNodes) {
        /**
         * Specialized assembly for Multi Flow Map.
         * Handles two node types:
         * - Causes: text → spec.causes[]
         * - Effects: text → spec.effects[]
         */
        
        console.log('[MultiFlow-Assemble] ========================================');
        console.log('[MultiFlow-Assemble] ASSEMBLING NODES TO MULTI FLOW MAP');
        console.log('[MultiFlow-Assemble] ========================================');
        console.log(`[MultiFlow-Assemble] Total selected nodes: ${selectedNodes.length}`);
        
        const editor = window.currentEditor;
        if (!editor || !editor.currentSpec) {
            console.error('[MultiFlow-Assemble] ERROR: No active editor found');
            alert('Error: No active editor found.');
            return;
        }
        
        const currentSpec = editor.currentSpec;
        
        // Group nodes by mode
        const causesNodes = selectedNodes.filter(n => n.mode === 'causes');
        const effectsNodes = selectedNodes.filter(n => n.mode === 'effects');
        
        console.log('[MultiFlow-Assemble] Node distribution:');
        console.log(`  Causes: ${causesNodes.length} nodes`);
        console.log(`  Effects: ${effectsNodes.length} nodes`);
        
        // Initialize arrays
        if (!Array.isArray(currentSpec.causes)) currentSpec.causes = [];
        if (!Array.isArray(currentSpec.effects)) currentSpec.effects = [];
        
        // Process causes
        if (causesNodes.length > 0) {
            const newCauses = currentSpec.causes.filter(text => !this.isPlaceholder(text));
            causesNodes.forEach(node => {
                newCauses.push(node.text);
                node.added_to_diagram = true;
            });
            currentSpec.causes = newCauses;
            console.log(`[MultiFlow-Assemble] ✓ Added ${causesNodes.length} causes`);
        }
        
        // Process effects
        if (effectsNodes.length > 0) {
            const newEffects = currentSpec.effects.filter(text => !this.isPlaceholder(text));
            effectsNodes.forEach(node => {
                newEffects.push(node.text);
                node.added_to_diagram = true;
            });
            currentSpec.effects = newEffects;
            console.log(`[MultiFlow-Assemble] ✓ Added ${effectsNodes.length} effects`);
        }
        
        // Re-render
        try {
            if (typeof editor.renderDiagram === 'function') {
                await editor.renderDiagram(currentSpec);
            } else if (typeof editor.render === 'function') {
                await editor.render();
            }
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
            }
            console.log('[MultiFlow-Assemble] ✓ ASSEMBLY COMPLETE');
        } catch (error) {
            console.error('[MultiFlow-Assemble] ERROR:', error);
            alert(`Error rendering diagram: ${error.message}`);
        }
    }
    
    async assembleNodesToBridgeMap(selectedNodes) {
        /**
         * Specialized assembly for Bridge Map.
         * Handles analogy pairs with left/right structure.
         * Each node has: {left, right, dimension (optional)}
         */
        
        console.log('[BridgeMap-Assemble] ========================================');
        console.log('[BridgeMap-Assemble] ASSEMBLING NODES TO BRIDGE MAP');
        console.log('[BridgeMap-Assemble] ========================================');
        console.log(`[BridgeMap-Assemble] Total selected nodes: ${selectedNodes.length}`);
        
        const editor = window.currentEditor;
        if (!editor || !editor.currentSpec) {
            console.error('[BridgeMap-Assemble] ERROR: No active editor found');
            alert('Error: No active editor found.');
            return;
        }
        
        const currentSpec = editor.currentSpec;
        
        // Initialize analogies array
        if (!Array.isArray(currentSpec.analogies)) {
            currentSpec.analogies = [];
        }
        
        // Log node structures
        console.log('[BridgeMap-Assemble] Selected node details:');
        selectedNodes.forEach((node, idx) => {
            console.log(`  [${idx + 1}] left="${node.left}" | right="${node.right}" | dimension="${node.dimension || 'N/A'}"`);
        });
        
        // Filter out placeholders from existing analogies
        const existingAnalogies = currentSpec.analogies.filter(analogy => {
            const leftText = analogy.left || '';
            const rightText = analogy.right || '';
            return !this.isPlaceholder(leftText) && !this.isPlaceholder(rightText);
        });
        
        console.log(`[BridgeMap-Assemble] Keeping ${existingAnalogies.length} existing non-placeholder analogies`);
        
        // Convert selected nodes to analogy objects
        const newAnalogies = selectedNodes.map((node, idx) => {
            const analogy = {
                left: node.left,
                right: node.right,
                id: idx
            };
            
            // Add dimension if present (optional field)
            if (node.dimension) {
                analogy.dimension = node.dimension;
            }
            
            node.added_to_diagram = true;
            return analogy;
        });
        
        // Combine existing + new analogies
        currentSpec.analogies = [...existingAnalogies, ...newAnalogies];
        
        // Re-assign IDs sequentially
        currentSpec.analogies.forEach((analogy, idx) => {
            analogy.id = idx;
        });
        
        console.log(`[BridgeMap-Assemble] ✓ Added ${newAnalogies.length} analogies`);
        console.log(`[BridgeMap-Assemble] Total analogies now: ${currentSpec.analogies.length}`);
        
        // Re-render
        try {
            if (typeof editor.renderDiagram === 'function') {
                await editor.renderDiagram(currentSpec);
                console.log('[BridgeMap-Assemble] ✓ Diagram re-rendered');
            } else if (typeof editor.render === 'function') {
                await editor.render();
                console.log('[BridgeMap-Assemble] ✓ Diagram rendered (legacy)');
            }
            
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
                console.log('[BridgeMap-Assemble] ✓ History saved');
            }
            
            console.log('[BridgeMap-Assemble] ========================================');
            console.log('[BridgeMap-Assemble] ✓ ASSEMBLY COMPLETE');
            console.log('[BridgeMap-Assemble] ========================================');
        } catch (error) {
            console.error('[BridgeMap-Assemble] ERROR:', error);
            alert(`Error rendering diagram: ${error.message}`);
        }
    }
    
    async assembleNodesToTreeMap(selectedNodes) {
        /**
         * Specialized assembly for Tree Map.
         * Multi-stage workflow: dimension → categories → children
         * 
         * Builds hierarchical structure:
         * {
         *   topic: "四驱系统",
         *   dimension: "车型",
         *   children: [
         *     { text: "SUV", children: [{text: "item1", children: []}, ...] },
         *     { text: "Sedan", children: [{text: "item2", children: []}, ...] }
         *   ]
         * }
         */
        
        console.log('[TreeMap-Assemble] ========================================');
        console.log('[TreeMap-Assemble] ASSEMBLING NODES TO TREE MAP');
        console.log('[TreeMap-Assemble] ========================================');
        console.log(`[TreeMap-Assemble] Total selected nodes: ${selectedNodes.length}`);
        console.log(`[TreeMap-Assemble] Stage data:`, this.stageData);
        
        const editor = window.currentEditor;
        if (!editor || !editor.currentSpec) {
            console.error('[TreeMap-Assemble] ERROR: No active editor found');
            alert('Error: No active editor found.');
            return;
        }
        
        const currentSpec = editor.currentSpec;
        
        // Extract dimension from stage data
        const dimension = this.stageData.dimension || '';
        const selectedCategories = this.stageData.categories || [];
        
        console.log(`[TreeMap-Assemble] Dimension: "${dimension}"`);
        console.log(`[TreeMap-Assemble] Categories: ${selectedCategories.length} selected`);
        console.log(`[TreeMap-Assemble] Categories:`, selectedCategories);
        
        // Group children nodes by category (using node.mode)
        const nodesByCategory = {};
        
        selectedNodes.forEach(node => {
            const category = node.mode;  // e.g., 'SUV', 'Sedan', 'Truck'
            
            if (!category) {
                console.warn(`[TreeMap-Assemble] Node has no mode field:`, node);
                return;
            }
            
            // Only process nodes that belong to our selected categories
            if (!selectedCategories.includes(category)) {
                console.warn(`[TreeMap-Assemble] Node category "${category}" not in selected categories, skipping`);
                return;
            }
            
            if (!nodesByCategory[category]) {
                nodesByCategory[category] = [];
            }
            
            nodesByCategory[category].push(node);
        });
        
        console.log('[TreeMap-Assemble] Nodes grouped by category:');
        Object.keys(nodesByCategory).forEach(cat => {
            console.log(`  ${cat}: ${nodesByCategory[cat].length} items`);
        });
        
        // Build hierarchical structure
        const newChildren = [];
        
        selectedCategories.forEach(categoryName => {
            const categoryNodes = nodesByCategory[categoryName] || [];
            
            // Build category object with children
            const categoryObj = {
                text: categoryName,
                children: categoryNodes.map(node => ({
                    text: node.text,
                    children: []  // Leaf nodes (no further nesting)
                }))
            };
            
            newChildren.push(categoryObj);
            
            // Mark nodes as added
            categoryNodes.forEach(node => {
                node.added_to_diagram = true;
            });
            
            console.log(`[TreeMap-Assemble] ✓ Category "${categoryName}": ${categoryNodes.length} items`);
        });
        
        // Filter out placeholder categories from existing children
        const existingChildren = (currentSpec.children || []).filter(category => {
            return category.text && !this.isPlaceholder(category.text);
        });
        
        console.log(`[TreeMap-Assemble] Keeping ${existingChildren.length} existing non-placeholder categories`);
        
        // Merge existing + new children
        currentSpec.children = [...existingChildren, ...newChildren];
        
        // Set dimension if provided
        if (dimension) {
            currentSpec.dimension = dimension;
            console.log(`[TreeMap-Assemble] ✓ Set dimension: "${dimension}"`);
        }
        
        console.log(`[TreeMap-Assemble] ✓ Added ${newChildren.length} categories with items`);
        console.log(`[TreeMap-Assemble] Total categories now: ${currentSpec.children.length}`);
        
        // Log final structure
        console.log('[TreeMap-Assemble] Final structure:');
        console.log(`  Topic: "${currentSpec.topic}"`);
        console.log(`  Dimension: "${currentSpec.dimension}"`);
        console.log(`  Categories: ${currentSpec.children.length}`);
        currentSpec.children.forEach((cat, idx) => {
            const itemCount = cat.children ? cat.children.length : 0;
            console.log(`    [${idx + 1}] ${cat.text}: ${itemCount} items`);
        });
        
        // Re-render
        try {
            if (typeof editor.renderDiagram === 'function') {
                await editor.renderDiagram(currentSpec);
                console.log('[TreeMap-Assemble] ✓ Diagram re-rendered');
            } else if (typeof editor.render === 'function') {
                await editor.render();
                console.log('[TreeMap-Assemble] ✓ Diagram rendered (legacy)');
            }
            
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
                console.log('[TreeMap-Assemble] ✓ History saved');
            }
            
            console.log('[TreeMap-Assemble] ========================================');
            console.log('[TreeMap-Assemble] ✓ ASSEMBLY COMPLETE');
            console.log('[TreeMap-Assemble] ========================================');
        } catch (error) {
            console.error('[TreeMap-Assemble] ERROR:', error);
            alert(`Error rendering diagram: ${error.message}`);
        }
    }
    
    async assembleNodesToMindMap(selectedNodes) {
        /**
         * Specialized assembly for Mind Map.
         * Creates proper branch objects with id, label, text, and children fields.
         * 
         * Each branch object structure:
         * {
         *   id: "branch_N",
         *   label: "Branch Text",
         *   text: "Branch Text",  // backward compatibility
         *   children: []  // sub-items array
         * }
         */
        
        console.log('[MindMap-Assemble] ========================================');
        console.log('[MindMap-Assemble] ASSEMBLING BRANCHES TO MINDMAP');
        console.log('[MindMap-Assemble] ========================================');
        console.log(`[MindMap-Assemble] Input: ${selectedNodes.length} selected branches`);
        
        const editor = window.currentEditor;
        if (!editor || !editor.currentSpec) {
            console.error('[MindMap-Assemble] ERROR: No active editor or spec');
            alert('Error: No active editor found');
            return;
        }
        
        const currentSpec = editor.currentSpec;
        
        // Initialize children array if needed
        if (!Array.isArray(currentSpec.children)) {
            currentSpec.children = [];
        }
        
        const beforeCount = currentSpec.children.length;
        console.log(`[MindMap-Assemble] BEFORE: ${beforeCount} branches`);
        
        // Analyze existing branches - keep user-created branches, skip placeholders
        const placeholderPatterns = [
            /^Branch\s*\d+$/i,
            /^分支\s*\d+$/,
            /^新分支\s*\d*$/,
            /^New Branch\s*\d*$/i
        ];
        
        const realBranches = currentSpec.children.filter(branch => {
            const text = (branch.label || branch.text || '').trim();
            if (text.length === 0) return false;
            if (placeholderPatterns.some(pattern => pattern.test(text))) {
                console.log(`[MindMap-Assemble] Skipping placeholder: "${text}"`);
                return false;
            }
            return true;
        });
        
        console.log(`[MindMap-Assemble] Keeping ${realBranches.length} real branches`);
        console.log(`[MindMap-Assemble] Adding ${selectedNodes.length} new branches`);
        
        // Build new array: keep real branches + add selected branches
        const newBranches = [...realBranches];
        const startIndex = newBranches.length;
        
        selectedNodes.forEach((node, idx) => {
            const branchIndex = startIndex + idx;
            const newBranch = {
                id: `branch_${branchIndex}`,
                label: node.text,
                text: node.text,  // backward compatibility
                children: []  // empty sub-items array
            };
            newBranches.push(newBranch);
            node.added_to_diagram = true;
            console.log(`  [${idx + 1}/${selectedNodes.length}] ADDED: "${node.text}" | ID: ${newBranch.id}`);
        });
        
        // Update spec
        currentSpec.children = newBranches;
        
        console.log(`[MindMap-Assemble] AFTER: ${newBranches.length} branches (+${selectedNodes.length})`);
        console.log('[MindMap-Assemble] ========================================');
        console.log('[MindMap-Assemble] Calling backend to recalculate layout...');
        console.log('[MindMap-Assemble] ========================================');
        
        // Mind maps need backend layout recalculation after adding nodes
        try {
            await editor.recalculateMindMapLayout();
            console.log('[MindMap-Assemble] ✓ Layout recalculated and diagram rendered');
            
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
                console.log('[MindMap-Assemble] ✓ History saved');
            }
            
            console.log('[MindMap-Assemble] ========================================');
            console.log(`[MindMap-Assemble] ✓ SUCCESS: ${selectedNodes.length} branches added to mindmap`);
            console.log('[MindMap-Assemble] ========================================');
        } catch (error) {
            console.error('[MindMap-Assemble] ERROR:', error);
            alert(`Error rendering mindmap: ${error.message}`);
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NodePaletteManager;
}

// Global instance
window.nodePaletteManager = new NodePaletteManager();

// Note: Button listener is now attached when panel opens (see showPalettePanel)
// This ensures the listener is active even if panel opens after DOMContentLoaded

