/**
 * LearningModeManager
 * 
 * Manages the interactive Learning Mode experience:
 * - Knocks out 20% of random nodes
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class LearningModeManager {
    constructor(toolbarManager, interactiveEditor) {
        this.toolbarManager = toolbarManager;
        this.editor = interactiveEditor;
        this.logger = window.frontendLogger || console;
        this.lang = window.languageManager;
        
        // State management
        this.isActive = false;
        this.sessionId = null;
        this.knockedOutNodes = [];       // Array of node objects that were knocked out
        this.questions = [];              // Intelligent questions from backend
        this.currentNodeIndex = 0;       // Current node being tested
        this.correctAnswers = 0;
        this.totalAttempts = 0;
        this.hintLevel = 0;              // Current hint level (0-3)
        this.escalationLevel = 0;        // Phase 4: Current escalation level (0-3) for failed verifications
        this.maxEscalations = 3;         // Phase 4: Maximum escalation attempts before skip option
        this.currentNodeEscalations = 0; // Phase 4: Escalations for current node
        this.misconceptionPatterns = []; // Phase 4: Track misconceptions across session
        
        // Original node data (for restoration)
        this.originalNodeData = new Map(); // nodeId -> { text, visibility, element }
        
        // UI elements
        this.learningOverlay = null;
        this.questionPanel = null;
        this.inputField = null;
        this.submitBtn = null;
        this.hintBtn = null;
        this.exitBtn = null;
        
        this.logger.log('LearningModeManager', 'Initialized');
    }
    
    /**
     * Start Learning Mode
     * @param {Object} validationResult - Result from DiagramValidator
     */
    async startLearningMode(validationResult) {
        if (this.isActive) {
            this.logger.warn('LearningModeManager', 'Learning Mode already active');
            return;
        }
        
        this.logger.log('LearningModeManager', '🧠 Starting Learning Mode...');
        
        try {
            // Phase 1: Node Selection & Knockout
            const nodes = this.selectRandomNodes(validationResult.totalNodes);
            if (nodes.length === 0) {
                throw new Error('No nodes to knock out');
            }
            
            this.knockedOutNodes = nodes;
            this.logger.log('LearningModeManager', `Selected ${nodes.length} nodes to knock out`);
            
            // Phase 2: Generate Intelligent Questions from Backend
            const currentLanguage = this.lang?.currentLanguage || 'en';
            const knocked_out_node_ids = nodes.map(n => n.id);
            
            const sessionData = await this.initializeBackendSession(
                knocked_out_node_ids,
                currentLanguage
            );
            
            if (!sessionData.success) {
                throw new Error('Failed to initialize learning session: ' + (sessionData.error || 'Unknown error'));
            }
            
            this.sessionId = sessionData.session_id;
            this.questions = sessionData.questions;
            
            this.logger.log('LearningModeManager', `✅ Backend session created: ${this.sessionId} | ${this.questions.length} intelligent questions`);
            
            // Save original node data
            this.saveOriginalNodeData(nodes);
            
            // Knock out nodes (hide their text)
            this.knockOutNodes(nodes);
            
            // Create Learning Mode UI
            this.createLearningUI();
            
            // Disable editing tools
            this.disableEditingTools();
            
            // Set active state
            this.isActive = true;
            
            // Show first question
            this.showNextQuestion();
            
            this.logger.log('LearningModeManager', '✅ Learning Mode started successfully');
            
        } catch (error) {
            this.logger.error('LearningModeManager', 'Failed to start Learning Mode:', error);
            this.exitLearningMode();
            throw error;
        }
    }
    
    /**
     * Initialize backend learning session with intelligent question generation
     * @param {Array} knocked_out_node_ids - Array of node IDs to knock out
     * @param {string} language - 'en' or 'zh'
     * @returns {Promise<Object>} Session data from backend
     */
    async initializeBackendSession(knocked_out_node_ids, language) {
        try {
            const response = await auth.fetch('/api/learning/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    diagram_type: this.editor.diagramType,
                    spec: this.editor.currentSpec,
                    knocked_out_nodes: knocked_out_node_ids,
                    language: language
                })
            });
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            this.logger.error('LearningModeManager', 'Error initializing backend session:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    /**
     * Select 20% of random nodes to knock out
     * @param {number} totalNodes - Total number of nodes in diagram
     * @returns {Array} Array of node objects
     */
    selectRandomNodes(totalNodes) {
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            return [];
        }
        
        // Get all text elements with data-node-id
        const allNodes = [];
        svg.selectAll('text[data-node-id]').each(function() {
            const element = d3.select(this);
            const nodeId = element.attr('data-node-id');
            const nodeType = element.attr('data-node-type');
            // Use extractTextFromSVG to handle both single-line and multi-line (tspan) text
            const text = (typeof window.extractTextFromSVG === 'function') 
                ? window.extractTextFromSVG(element) 
                : element.text();
            
            allNodes.push({
                id: nodeId,
                type: nodeType,
                text: text,
                element: this
            });
        });
        
        // Calculate 20% (minimum 1, maximum all nodes)
        const knockoutCount = Math.max(1, Math.min(allNodes.length, Math.ceil(allNodes.length * 0.2)));
        
        // Shuffle and select
        const shuffled = this.shuffleArray([...allNodes]);
        const selected = shuffled.slice(0, knockoutCount);
        
        this.logger.log('LearningModeManager', `Selected ${selected.length}/${allNodes.length} nodes (20%)`);
        
        return selected;
    }
    
    /**
     * Shuffle array using Fisher-Yates algorithm
     * @param {Array} array - Array to shuffle
     * @returns {Array} Shuffled array
     */
    shuffleArray(array) {
        const shuffled = [...array];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        return shuffled;
    }
    
    /**
     * Save original node data for restoration
     * @param {Array} nodes - Array of node objects
     */
    saveOriginalNodeData(nodes) {
        nodes.forEach(node => {
            this.originalNodeData.set(node.id, {
                text: node.text,
                element: node.element,
                visibility: d3.select(node.element).style('opacity') || '1'
            });
        });
        
        this.logger.log('LearningModeManager', `Saved ${nodes.length} original node states`);
    }
    
    /**
     * Knock out nodes (hide their text)
     * @param {Array} nodes - Array of node objects
     */
    knockOutNodes(nodes) {
        nodes.forEach(node => {
            const element = d3.select(node.element);
            
            // Hide text by setting opacity to 0
            element.style('opacity', '0');
            
            // Add a visual indicator (dashed border on parent rect/circle)
            const parentG = d3.select(node.element.parentNode);
            parentG.selectAll('rect, circle, ellipse').style('stroke-dasharray', '5,5');
            
            this.logger.log('LearningModeManager', `Knocked out node: ${node.id} (${node.text})`);
        });
    }
    
    /**
     * Create Learning Mode UI overlay
     */
    createLearningUI() {
        // Create overlay container
        this.learningOverlay = d3.select('body')
            .append('div')
            .attr('id', 'learning-mode-overlay')
            .style('position', 'fixed')
            .style('top', '60px')
            .style('right', '20px')
            .style('width', '400px')
            .style('max-height', 'calc(100vh - 100px)')
            .style('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)')
            .style('border-radius', '12px')
            .style('box-shadow', '0 8px 32px rgba(0, 0, 0, 0.3)')
            .style('padding', '20px')
            .style('z-index', '9999')
            .style('overflow-y', 'auto')
            .style('color', '#fff')
            .style('font-family', 'system-ui, -apple-system, sans-serif');
        
        // Title
        this.learningOverlay.append('h2')
            .style('margin', '0 0 16px 0')
            .style('font-size', '24px')
            .style('font-weight', '700')
            .html('🧠 ' + (this.lang?.translate('learningModeTitle') || 'Learning Mode'));
        
        // Progress indicator
        this.learningOverlay.append('div')
            .attr('id', 'learning-progress')
            .style('margin-bottom', '16px')
            .style('font-size', '14px')
            .style('opacity', '0.9')
            .html(this.lang?.translate('learningModeProgress', 1, this.knockedOutNodes.length) || `Question <strong>1</strong> of <strong>${this.knockedOutNodes.length}</strong>`);
        
        // Question panel
        this.questionPanel = this.learningOverlay.append('div')
            .attr('id', 'learning-question')
            .style('background', 'rgba(255, 255, 255, 0.15)')
            .style('border-radius', '8px')
            .style('padding', '16px')
            .style('margin-bottom', '16px')
            .style('min-height', '100px');
        
        // Input field label
        this.learningOverlay.append('label')
            .attr('for', 'learning-input')
            .attr('style', 'display: none;')
            .text(this.lang?.translate('learningModeInputLabel') || 'Learning mode input');
        
        // Input field
        this.inputField = this.learningOverlay.append('input')
            .attr('type', 'text')
            .attr('id', 'learning-input')
            .attr('name', 'learning-input')
            .attr('autocomplete', 'off')
            .attr('placeholder', this.lang?.translate('learningModeInputPlaceholder') || 'Type your answer here...')
            .style('width', '100%')
            .style('padding', '12px')
            .style('border', 'none')
            .style('border-radius', '6px')
            .style('font-size', '16px')
            .style('margin-bottom', '12px')
            .style('box-sizing', 'border-box');
        
        // Button container
        const btnContainer = this.learningOverlay.append('div')
            .style('display', 'flex')
            .style('gap', '8px')
            .style('margin-bottom', '12px');
        
        // Submit button
        this.submitBtn = btnContainer.append('button')
            .attr('id', 'learning-submit')
            .style('flex', '1')
            .style('padding', '12px')
            .style('background', '#10b981')
            .style('color', '#fff')
            .style('border', 'none')
            .style('border-radius', '6px')
            .style('font-size', '16px')
            .style('font-weight', '600')
            .style('cursor', 'pointer')
            .html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'))
            .on('click', () => this.handleSubmit());
        
        // Hint button
        this.hintBtn = btnContainer.append('button')
            .attr('id', 'learning-hint')
            .style('flex', '1')
            .style('padding', '12px')
            .style('background', 'rgba(255, 255, 255, 0.2)')
            .style('color', '#fff')
            .style('border', 'none')
            .style('border-radius', '6px')
            .style('font-size', '16px')
            .style('font-weight', '600')
            .style('cursor', 'pointer')
            .html('💡 ' + (this.lang?.translate('learningModeHint') || 'Hint'))
            .on('click', () => this.handleHint());
        
        // Exit button
        this.exitBtn = this.learningOverlay.append('button')
            .attr('id', 'learning-exit')
            .style('width', '100%')
            .style('padding', '12px')
            .style('background', 'rgba(220, 38, 38, 0.8)')
            .style('color', '#fff')
            .style('border', 'none')
            .style('border-radius', '6px')
            .style('font-size', '14px')
            .style('font-weight', '600')
            .style('cursor', 'pointer')
            .html('✕ ' + (this.lang?.translate('learningModeExit') || 'Exit Learning Mode'))
            .on('click', () => this.exitLearningMode());
        
        this.logger.log('LearningModeManager', 'Created Learning Mode UI');
    }
    
    /**
     * Show next question
     */
    showNextQuestion() {
        if (this.currentNodeIndex >= this.knockedOutNodes.length) {
            this.showCompletionScreen();
            return;
        }
        
        const node = this.knockedOutNodes[this.currentNodeIndex];
        const questionData = this.questions[this.currentNodeIndex];
        
        // Reset hint level for new question
        this.hintLevel = 0;
        
        // Update progress
        d3.select('#learning-progress')
            .html(this.lang?.translate('learningModeProgress', this.currentNodeIndex + 1, this.knockedOutNodes.length) || `Question <strong>${this.currentNodeIndex + 1}</strong> of <strong>${this.knockedOutNodes.length}</strong>`);
        
        // Show intelligent question from backend
        const intelligentQuestion = questionData?.question || this._getFallbackQuestion(node);
        const difficultyBadge = questionData?.difficulty ? `<span style="background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 8px;">${questionData.difficulty}</span>` : '';
        
        this.questionPanel.html(`
            <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">
                ${this.lang?.translate('learningModeFillIn') || 'Fill in the missing node:'}${difficultyBadge}
            </div>
            <div style="font-size: 18px; font-weight: 600; line-height: 1.5;">
                ${intelligentQuestion}
            </div>
            <div style="font-size: 12px; opacity: 0.7; margin-top: 12px;">
                💡 ${this.lang?.translate('learningModeContextHint') || 'Hint: Look at the diagram structure and context'}
            </div>
        `);
        
        // Clear input
        this.inputField.property('value', '');
        this.inputField.node().focus();
        
        // Enable Enter key submission
        this.inputField.on('keypress', (event) => {
            if (event.key === 'Enter') {
                this.handleSubmit();
            }
        });
        
        this.logger.log('LearningModeManager', `Showing question ${this.currentNodeIndex + 1}/${this.knockedOutNodes.length} | Difficulty: ${questionData?.difficulty || 'unknown'}`);
    }
    
    /**
     * Get fallback question if backend fails
     * @param {Object} node - Node object
     * @returns {string} Fallback question
     */
    _getFallbackQuestion(node) {
        const nodeTypeDisplay = node.type || (this.lang?.currentLanguage === 'zh' ? '节点' : 'node');
        const questionPrefix = this.lang?.translate('learningModeQuestionPrefix') || 'What is the text for';
        const questionSuffix = this.lang?.translate('learningModeQuestionSuffix') || '?';
        
        return `${questionPrefix} <strong>${nodeTypeDisplay}</strong> <code style="background: rgba(255,255,255,0.2); padding: 2px 6px; border-radius: 4px;">${node.id}</code>${questionSuffix}`;
    }
    
    /**
     * Handle answer submission
     */
    async handleSubmit() {
        const userAnswer = this.inputField.property('value').trim();
        
        if (!userAnswer) {
            this.showFeedback(this.lang?.translate('learningModeEnterAnswer') || 'Please enter an answer', 'warning');
            return;
        }
        
        // Disable submit button to prevent double submission
        this.submitBtn.property('disabled', true);
        this.submitBtn.html('⏳ ' + (this.lang?.currentLanguage === 'zh' ? '验证中...' : 'Checking...'));
        
        this.totalAttempts++;
        
        const node = this.knockedOutNodes[this.currentNodeIndex];
        const questionData = this.questions[this.currentNodeIndex];
        
        try {
            // Call backend for semantic validation
            const validation = await this.validateAnswerWithBackend(
                userAnswer,
                questionData
            );
            
            if (validation.correct) {
                this.correctAnswers++;
                this.showFeedback('✅ ' + (validation.message || this.lang?.translate('learningModeCorrect') || 'Correct!'), 'success');
                
                // Restore node visibility
                this.restoreNode(node);
                
                // Move to next question after delay
                setTimeout(() => {
                    this.currentNodeIndex++;
                    this.showNextQuestion();
                    // Re-enable submit button
                    this.submitBtn.property('disabled', false);
                    this.submitBtn.html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'));
                }, 1500);
                
            } else {
                // Check if agent workflow generated learning materials
                if (validation.agent_workflow && validation.agent_workflow.agent_response) {
                    this.logger.log('LearningModeManager', '✅ Agent workflow detected - showing learning materials');
                    
                    // Show learning material modal
                    this.showLearningMaterialModal(validation, node);
                    
                    // Re-enable submit button
                    this.submitBtn.property('disabled', false);
                    this.submitBtn.html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'));
                    
                } else {
                    // Log why modal didn't show
                    if (validation.agent_workflow && validation.agent_workflow.error) {
                        this.logger.error('LearningModeManager', `❌ V3 Agent failed: ${validation.agent_workflow.error}`);
                    } else if (validation.agent_workflow) {
                        this.logger.warn('LearningModeManager', `⚠️ Agent workflow exists but no agent_response. Keys: ${Object.keys(validation.agent_workflow).join(', ')}`);
                    } else {
                        this.logger.warn('LearningModeManager', '⚠️ No agent_workflow in validation result. Backend may have failed.');
                    }
                    
                    // Fallback: Show error with misconception analysis
                    const incorrectMsg = validation.message || this.lang?.translate('learningModeIncorrect', node.text) || `Not quite. The correct answer is: <strong>${node.text}</strong>`;
                    this.showFeedback('❌ ' + incorrectMsg, 'error');
                    
                    // Log misconception if available
                    if (validation.misconception_analysis) {
                        this.logger.log('LearningModeManager', `Misconception detected: ${validation.misconception_analysis.type} | ${validation.misconception_analysis.diagnosis}`);
                    }
                    
                    // Show answer and move on after delay
                    setTimeout(() => {
                        this.restoreNode(node);
                        this.currentNodeIndex++;
                        this.showNextQuestion();
                        // Re-enable submit button
                        this.submitBtn.property('disabled', false);
                        this.submitBtn.html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'));
                    }, 3500);
                }
            }
            
            this.logger.log('LearningModeManager', `Answer: ${validation.correct ? '✓' : '✗'} | Confidence: ${validation.confidence || 'N/A'} | ${userAnswer} vs ${node.text}`);
            
        } catch (error) {
            this.logger.error('LearningModeManager', 'Error validating answer:', error);
            
            // Fallback to simple string comparison
            const isCorrect = this.compareAnswers(userAnswer, node.text);
            
            if (isCorrect) {
                this.correctAnswers++;
                this.showFeedback('✅ ' + (this.lang?.translate('learningModeCorrect') || 'Correct!'), 'success');
                this.restoreNode(node);
                setTimeout(() => {
                    this.currentNodeIndex++;
                    this.showNextQuestion();
                    this.submitBtn.property('disabled', false);
                    this.submitBtn.html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'));
                }, 1500);
            } else {
                const incorrectMsg = this.lang?.translate('learningModeIncorrect', node.text) || `Not quite. The correct answer is: <strong>${node.text}</strong>`;
                this.showFeedback('❌ ' + incorrectMsg, 'error');
                setTimeout(() => {
                    this.restoreNode(node);
                    this.currentNodeIndex++;
                    this.showNextQuestion();
                    this.submitBtn.property('disabled', false);
                    this.submitBtn.html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'));
                }, 3000);
            }
        }
    }
    
    /**
     * Validate answer with backend semantic checker
     * @param {string} userAnswer - User's answer
     * @param {Object} questionData - Question data from backend
     * @returns {Promise<Object>} Validation result
     */
    async validateAnswerWithBackend(userAnswer, questionData) {
        try {
            const response = await auth.fetch('/api/learning/validate_answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    node_id: questionData.node_id,
                    user_answer: userAnswer,
                    question: questionData.question,
                    context: questionData.context || {},
                    language: this.lang?.currentLanguage || 'en'
                })
            });
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            this.logger.error('LearningModeManager', 'Error calling validation API:', error);
            throw error;
        }
    }
    
    /**
     * Compare user answer with correct answer (case-insensitive, trimmed)
     * @param {string} userAnswer - User's answer
     * @param {string} correctAnswer - Correct answer
     * @returns {boolean} True if answers match
     */
    compareAnswers(userAnswer, correctAnswer) {
        const normalize = (str) => str.toLowerCase().trim().replace(/\s+/g, ' ');
        return normalize(userAnswer) === normalize(correctAnswer);
    }
    
    /**
     * Handle hint request - Gets progressive hints from backend
     */
    async handleHint() {
        // Increment hint level (max 3)
        this.hintLevel = Math.min(this.hintLevel + 1, 3);
        
        const node = this.knockedOutNodes[this.currentNodeIndex];
        const questionData = this.questions[this.currentNodeIndex];
        
        // Disable hint button temporarily
        this.hintBtn.property('disabled', true);
        this.hintBtn.html('⏳ ' + (this.lang?.currentLanguage === 'zh' ? '生成中...' : 'Generating...'));
        
        try {
            // Get intelligent hint from backend
            const hintData = await this.getHintFromBackend(questionData, this.hintLevel);
            
            const hintText = hintData.hint || this._getFallbackHint(node.text, this.hintLevel);
            const hintLevelText = this.lang?.currentLanguage === 'zh' ? `提示 ${this.hintLevel}/3` : `Hint ${this.hintLevel}/3`;
            
            this.showFeedback(`💡 [${hintLevelText}] ${hintText}`, 'info');
            
            this.logger.log('LearningModeManager', `Hint ${this.hintLevel}/3 provided for: ${node.id}`);
            
        } catch (error) {
            this.logger.error('LearningModeManager', 'Error getting hint:', error);
            
            // Fallback to simple hint
            const fallbackHint = this._getFallbackHint(node.text, this.hintLevel);
            this.showFeedback(`💡 ${fallbackHint}`, 'info');
        }
        
        // Re-enable hint button (unless max level reached)
        setTimeout(() => {
            if (this.hintLevel < 3) {
                this.hintBtn.property('disabled', false);
                this.hintBtn.html('💡 ' + (this.lang?.translate('learningModeHint') || 'Hint'));
            } else {
                // Max hints reached
                this.hintBtn.property('disabled', true);
                this.hintBtn.html('💡 ' + (this.lang?.currentLanguage === 'zh' ? '已达上限' : 'Max hints'));
            }
        }, 500);
    }
    
    /**
     * Get intelligent hint from backend
     * @param {Object} questionData - Question data
     * @param {number} hintLevel - Hint level (1-3)
     * @returns {Promise<Object>} Hint data
     */
    async getHintFromBackend(questionData, hintLevel) {
        try {
            const response = await auth.fetch('/api/learning/get_hint', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    node_id: questionData.node_id,
                    question: questionData.question,
                    context: questionData.context || {},
                    hint_level: hintLevel,
                    language: this.lang?.currentLanguage || 'en'
                })
            });
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            this.logger.error('LearningModeManager', 'Error calling hint API:', error);
            throw error;
        }
    }
    
    /**
     * Get fallback hint if backend fails
     * @param {string} correctAnswer - Correct answer
     * @param {number} hintLevel - Hint level (1-3)
     * @returns {string} Fallback hint
     */
    _getFallbackHint(correctAnswer, hintLevel) {
        if (hintLevel >= 3) {
            // Level 3: Give first character and length
            return this.lang?.translate('learningModeBasicHint', correctAnswer.charAt(0), correctAnswer.length) || 
                   `The answer starts with '<strong>${correctAnswer.charAt(0)}</strong>' and has <strong>${correctAnswer.length}</strong> characters.`;
        } else if (hintLevel === 2) {
            // Level 2: Give first character
            if (this.lang?.currentLanguage === 'zh') {
                return `答案以"<strong>${correctAnswer.charAt(0)}</strong>"开头。`;
            } else {
                return `The answer starts with '<strong>${correctAnswer.charAt(0)}</strong>'.`;
            }
        } else {
            // Level 1: Give category hint
            if (this.lang?.currentLanguage === 'zh') {
                return '想想图示的主题和这个节点的位置。';
            } else {
                return 'Think about the diagram\'s theme and this node\'s position.';
            }
        }
    }
    
    /**
     * Show feedback message in question panel
     * @param {string} message - Feedback message (can include HTML)
     * @param {string} type - 'success', 'error', 'warning', 'info'
     */
    showFeedback(message, type = 'info') {
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        
        const feedbackDiv = this.learningOverlay.insert('div', '#learning-exit')
            .style('background', colors[type] || colors.info)
            .style('padding', '12px')
            .style('border-radius', '6px')
            .style('margin-bottom', '12px')
            .style('font-size', '14px')
            .style('animation', 'fadeIn 0.3s ease-in')
            .html(message);
        
        // Remove after 3 seconds (except for errors, which stay longer)
        const duration = type === 'error' ? 5000 : 3000;
        setTimeout(() => {
            feedbackDiv.transition()
                .duration(300)
                .style('opacity', '0')
                .remove();
        }, duration);
    }
    
    /**
     * Restore a knocked out node
     * @param {Object} node - Node object
     */
    restoreNode(node) {
        const element = d3.select(node.element);
        
        // Restore text opacity
        element.style('opacity', '1');
        
        // Remove dashed border
        const parentG = d3.select(node.element.parentNode);
        parentG.selectAll('rect, circle, ellipse').style('stroke-dasharray', null);
        
        this.logger.log('LearningModeManager', `Restored node: ${node.id}`);
    }
    
    /**
     * Show completion screen
     */
    showCompletionScreen() {
        const accuracy = this.totalAttempts > 0 ? (this.correctAnswers / this.totalAttempts * 100).toFixed(1) : 0;
        
        this.questionPanel.html(`
            <div style="text-align: center;">
                <div style="font-size: 48px; margin-bottom: 16px;">
                    ${accuracy >= 80 ? '🎉' : accuracy >= 60 ? '👍' : '💪'}
                </div>
                <div style="font-size: 24px; font-weight: 700; margin-bottom: 8px;">
                    ${this.lang?.translate('learningModeComplete') || 'Learning Complete!'}
                </div>
                <div style="font-size: 16px; opacity: 0.9; margin-bottom: 16px;">
                    ${this.lang?.translate('learningModeScore', this.correctAnswers, this.knockedOutNodes.length) || `You got <strong>${this.correctAnswers}</strong> out of <strong>${this.knockedOutNodes.length}</strong> correct`}
                </div>
                <div style="font-size: 14px; opacity: 0.8;">
                    ${this.lang?.translate('learningModeAccuracy', accuracy) || `Accuracy: <strong>${accuracy}%</strong>`}
                </div>
            </div>
        `);
        
        // Hide input and buttons
        this.inputField.style('display', 'none');
        this.submitBtn.style('display', 'none');
        this.hintBtn.style('display', 'none');
        
        // Change exit button to "Finish"
        this.exitBtn.html('✓ ' + (this.lang?.translate('learningModeFinish') || 'Finish')).style('background', '#10b981');
        
        this.logger.log('LearningModeManager', `Learning completed: ${this.correctAnswers}/${this.knockedOutNodes.length} (${accuracy}%)`);
    }
    
    /**
     * Show learning material modal with agent's teaching materials
     * @param {Object} validation - Validation result with agent workflow
     * @param {Object} node - Current node
     */
    showLearningMaterialModal(validation, node) {
        // Highlight the node being tested on the canvas
        this.highlightNodeOnCanvas(node);
        
        // Create full-screen modal overlay
        const modal = d3.select('body')
            .append('div')
            .attr('id', 'learning-material-modal')
            .style('position', 'fixed')
            .style('top', '0')
            .style('left', '0')
            .style('width', '100%')
            .style('height', '100%')
            .style('background', 'rgba(0, 0, 0, 0.8)')
            .style('z-index', '10000')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .style('animation', 'fadeIn 0.3s ease-in');
        
        // Modal content container
        const modalContent = modal.append('div')
            .style('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)')
            .style('border-radius', '20px')
            .style('padding', '40px')
            .style('max-width', '700px')
            .style('max-height', '80vh')
            .style('overflow-y', 'auto')
            .style('box-shadow', '0 20px 60px rgba(0, 0, 0, 0.5)')
            .style('color', '#fff')
            .style('font-family', 'system-ui, -apple-system, sans-serif')
            .style('animation', 'slideUp 0.4s ease-out');
        
        // Title
        modalContent.append('h2')
            .style('margin', '0 0 24px 0')
            .style('font-size', '28px')
            .style('font-weight', '700')
            .style('text-align', 'center')
            .html('🎓 ' + (this.lang?.translate('learningMaterialTitle') || "Let's Learn This Concept!"));
        
        // Show which node is being tested (with visual context)
        const questionData = this.questions[this.currentNodeIndex];
        const nodeContext = this._getNodeContextDescription(node, questionData);
        modalContent.append('div')
            .style('background', 'rgba(255, 255, 255, 0.25)')
            .style('border-left', '4px solid #fbbf24')
            .style('border-radius', '8px')
            .style('padding', '16px')
            .style('margin-bottom', '20px')
            .style('font-size', '15px')
            .style('line-height', '1.5')
            .html(`<strong>🎯 Testing Node:</strong> ${nodeContext}`);
        
        // Parse agent response to extract learning materials
        const agentResponse = validation.agent_workflow.agent_response || '';
        
        // Show agent's full response for now (Phase 3)
        // In Phase 4, we'll parse structured JSON for specific sections
        modalContent.append('div')
            .style('background', 'rgba(255, 255, 255, 0.15)')
            .style('border-radius', '12px')
            .style('padding', '20px')
            .style('margin-bottom', '20px')
            .style('line-height', '1.6')
            .style('font-size', '16px')
            .html(agentResponse.replace(/\n/g, '<br>'));
        
        // Show correct answer
        modalContent.append('div')
            .style('background', 'rgba(16, 185, 129, 0.2)')
            .style('border-left', '4px solid #10b981')
            .style('border-radius', '8px')
            .style('padding', '16px')
            .style('margin-bottom', '24px')
            .html(`<strong>✓ Correct Answer:</strong> ${node.text}`);
        
        // Button container
        const buttonContainer = modalContent.append('div')
            .style('display', 'flex')
            .style('gap', '12px')
            .style('justify-content', 'center');
        
        // "I Understand" button
        buttonContainer.append('button')
            .style('flex', '1')
            .style('padding', '14px 24px')
            .style('background', '#10b981')
            .style('color', '#fff')
            .style('border', 'none')
            .style('border-radius', '10px')
            .style('font-size', '16px')
            .style('font-weight', '600')
            .style('cursor', 'pointer')
            .style('transition', 'all 0.2s')
            .html('✓ ' + (this.lang?.translate('learningMaterialUnderstand') || 'I Understand'))
            .on('mouseover', function() {
                d3.select(this).style('background', '#059669').style('transform', 'translateY(-2px)');
            })
            .on('mouseout', function() {
                d3.select(this).style('background', '#10b981').style('transform', 'translateY(0)');
            })
            .on('click', async () => {
                // Phase 4: Instead of moving to next question, show verification
                this.logger.log('LearningModeManager', 'Phase 4: User clicked "I Understand" - generating verification question');
                
                // Show loading state
                buttonContainer.selectAll('button').property('disabled', true);
                
                try {
                    // Generate and show verification question
                    await this.showVerificationQuestion(modal, modalContent, node, validation);
                } catch (error) {
                    this.logger.error('LearningModeManager', 'Failed to generate verification:', error);
                    // Fallback: close modal and move to next
                    this.removeNodeHighlight(node);
                    modal.remove();
                    this.restoreNode(node);
                    this.currentNodeIndex++;
                    this.showNextQuestion();
                }
            });
        
        // "Close" button
        buttonContainer.append('button')
            .style('flex', '1')
            .style('padding', '14px 24px')
            .style('background', 'rgba(255, 255, 255, 0.2)')
            .style('color', '#fff')
            .style('border', 'none')
            .style('border-radius', '10px')
            .style('font-size', '16px')
            .style('font-weight', '600')
            .style('cursor', 'pointer')
            .style('transition', 'all 0.2s')
            .html('✕ ' + (this.lang?.translate('learningMaterialClose') || 'Close'))
            .on('mouseover', function() {
                d3.select(this).style('background', 'rgba(255, 255, 255, 0.3)').style('transform', 'translateY(-2px)');
            })
            .on('mouseout', function() {
                d3.select(this).style('background', 'rgba(255, 255, 255, 0.2)').style('transform', 'translateY(0)');
            })
            .on('click', () => {
                // Remove highlight and close modal
                this.removeNodeHighlight(node);
                modal.remove();
                this.restoreNode(node);
                this.currentNodeIndex++;
                this.showNextQuestion();
            });
        
        this.logger.log('LearningModeManager', 'Learning material modal displayed');
    }
    
    /**
     * Get a user-friendly description of which node is being tested
     * @param {Object} node - The node being tested
     * @param {Object} questionData - Question data from backend
     * @returns {string} - Description like "Attribute 3 of 'acceleration'" or "Branch 2: 'iPhone features'"
     */
    _getNodeContextDescription(node, questionData) {
        const nodeType = node.type || 'node';
        const nodeId = node.id || 'unknown';
        const diagramType = this.toolbarManager?.diagramType || 'unknown';
        
        // Get the diagram's main topic for context
        let mainTopic = 'the diagram';
        const topicElement = d3.select('#d3-container text[data-node-type="topic"]');
        if (!topicElement.empty()) {
            // Use extractTextFromSVG to handle both single-line and multi-line (tspan) text
            mainTopic = (typeof window.extractTextFromSVG === 'function') 
                ? window.extractTextFromSVG(topicElement).trim() 
                : topicElement.text().trim() || 'the diagram';
        }
        
        // Build context based on node type and diagram type
        let context = '';
        
        switch (diagramType) {
            case 'bubble_map':
                if (nodeType === 'attribute') {
                    const attributeNum = nodeId.replace('attribute_', '');
                    context = `<span style="color: #fbbf24;">Attribute ${attributeNum}</span> of "<strong>${mainTopic}</strong>"`;
                } else if (nodeType === 'topic' || nodeId === 'topic_center') {
                    context = `<span style="color: #fbbf24;">Central Topic</span>`;
                }
                break;
            
            case 'mind_map':
                if (nodeType === 'branch') {
                    const branchNum = nodeId.replace('branch_', '');
                    context = `<span style="color: #fbbf24;">Branch ${branchNum}</span> of "<strong>${mainTopic}</strong>"`;
                } else if (nodeType === 'child') {
                    context = `<span style="color: #fbbf24;">Child Node</span> (${nodeId})`;
                } else if (nodeType === 'topic') {
                    context = `<span style="color: #fbbf24;">Main Topic</span>`;
                }
                break;
            
            case 'tree_map':
                if (nodeType === 'category') {
                    const catNum = nodeId.replace('category_', '');
                    context = `<span style="color: #fbbf24;">Category ${catNum}</span> of "<strong>${mainTopic}</strong>"`;
                } else if (nodeType === 'leaf') {
                    context = `<span style="color: #fbbf24;">Leaf Node</span> (${nodeId})`;
                }
                break;
            
            case 'bridge_map':
                if (nodeType === 'analogy_left' || nodeType === 'analogy_right') {
                    const side = nodeType.includes('left') ? 'Left' : 'Right';
                    const pairNum = nodeId.match(/\d+/)?.[0] || '?';
                    context = `<span style="color: #fbbf24;">${side} side of Pair ${pairNum}</span>`;
                }
                break;
            
            case 'brace_map':
                if (nodeType === 'part') {
                    const partNum = nodeId.replace('part_', '');
                    context = `<span style="color: #fbbf24;">Part ${partNum}</span> of "<strong>${mainTopic}</strong>"`;
                } else if (nodeType === 'subpart') {
                    context = `<span style="color: #fbbf24;">Subpart</span> (${nodeId})`;
                }
                break;
            
            default:
                context = `<span style="color: #fbbf24;">${nodeType}</span> (${nodeId})`;
        }
        
        return context || `<span style="color: #fbbf24;">Node ${nodeId}</span>`;
    }
    
    /**
     * Highlight a node on the canvas with a glowing effect
     * @param {Object} node - Node to highlight
     */
    highlightNodeOnCanvas(node) {
        // Find the parent group containing the node
        const parentG = d3.select(node.element.parentNode);
        
        // Add a glowing pulse effect to the shape (rect/circle/ellipse)
        parentG.selectAll('rect, circle, ellipse')
            .style('stroke', '#fbbf24')
            .style('stroke-width', '4px')
            .style('filter', 'drop-shadow(0 0 12px #fbbf24)')
            .style('animation', 'pulse 1.5s ease-in-out infinite');
        
        // Temporarily restore text opacity to show what we're highlighting
        d3.select(node.element).style('opacity', '1');
        
        this.logger.log('LearningModeManager', `Highlighted node: ${node.id}`);
    }
    
    /**
     * Remove highlight from a node
     * @param {Object} node - Node to unhighlight
     */
    removeNodeHighlight(node) {
        const parentG = d3.select(node.element.parentNode);
        
        // Remove glowing effect
        parentG.selectAll('rect, circle, ellipse')
            .style('stroke', null)
            .style('stroke-width', null)
            .style('filter', null)
            .style('animation', null);
        
        // Hide text again
        d3.select(node.element).style('opacity', '0');
        
        this.logger.log('LearningModeManager', `Removed highlight from node: ${node.id}`);
    }
    
    /**
     * Phase 4: Show verification question after learning materials
     * @param {Object} modal - D3 selection of modal overlay
     * @param {Object} modalContent - D3 selection of modal content
     * @param {Object} node - Current node being tested
     * @param {Object} validation - Original validation result with learning materials
     */
    async showVerificationQuestion(modal, modalContent, node, validation) {
        // Clear modal content
        modalContent.html('');
        
        // Show title
        modalContent.append('h2')
            .style('margin', '0 0 24px 0')
            .style('font-size', '28px')
            .style('font-weight', '700')
            .style('text-align', 'center')
            .html('🎯 ' + (this.lang?.translate('verificationTitle') || 'Let\'s Verify Your Understanding'));
        
        // Show escalation level indicator if > 0
        if (this.currentNodeEscalations > 0) {
            modalContent.append('div')
                .style('background', 'rgba(251, 191, 36, 0.2)')
                .style('border-left', '4px solid #fbbf24')
                .style('border-radius', '8px')
                .style('padding', '12px')
                .style('margin-bottom', '16px')
                .style('font-size', '14px')
                .html(`📊 Attempt ${this.currentNodeEscalations + 1} of ${this.maxEscalations}`);
        }
        
        // Generate verification question from different angle
        const verificationQuestion = this._generateVerificationQuestion(node, this.currentNodeEscalations);
        
        // Show verification question
        modalContent.append('div')
            .style('background', 'rgba(255, 255, 255, 0.15)')
            .style('border-radius', '12px')
            .style('padding', '20px')
            .style('margin-bottom', '20px')
            .style('line-height', '1.6')
            .style('font-size', '16px')
            .html(verificationQuestion);
        
        // Input field for verification answer
        const inputContainer = modalContent.append('div')
            .style('margin-bottom', '20px');
        
        const verificationInputId = `learning-verification-input-${Date.now()}`;
        inputContainer.append('label')
            .attr('for', verificationInputId)
            .attr('style', 'display: none;')
            .text(this.lang?.translate('learningModeVerificationLabel') || 'Verification answer input');
        
        const verificationInput = inputContainer.append('input')
            .attr('id', verificationInputId)
            .attr('name', 'learning-verification-input')
            .attr('type', 'text')
            .attr('autocomplete', 'off')
            .attr('placeholder', this.lang?.translate('learningModeInputPlaceholder') || 'Type your answer...')
            .style('width', '100%')
            .style('padding', '14px')
            .style('border', '2px solid rgba(255, 255, 255, 0.3)')
            .style('border-radius', '10px')
            .style('background', 'rgba(255, 255, 255, 0.1)')
            .style('color', '#fff')
            .style('font-size', '16px')
            .style('font-family', 'inherit')
            .style('outline', 'none')
            .on('focus', function() {
                d3.select(this).style('border-color', '#fbbf24');
            })
            .on('blur', function() {
                d3.select(this).style('border-color', 'rgba(255, 255, 255, 0.3)');
            });
        
        // Feedback area
        const feedbackArea = modalContent.append('div')
            .attr('id', 'verification-feedback')
            .style('min-height', '40px')
            .style('margin-bottom', '20px');
        
        // Button container
        const buttonContainer = modalContent.append('div')
            .style('display', 'flex')
            .style('gap', '12px')
            .style('justify-content', 'center');
        
        // Submit button
        const submitBtn = buttonContainer.append('button')
            .style('flex', '1')
            .style('padding', '14px 24px')
            .style('background', '#3b82f6')
            .style('color', '#fff')
            .style('border', 'none')
            .style('border-radius', '10px')
            .style('font-size', '16px')
            .style('font-weight', '600')
            .style('cursor', 'pointer')
            .style('transition', 'all 0.2s')
            .html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'))
            .on('mouseover', function() {
                d3.select(this).style('background', '#2563eb').style('transform', 'translateY(-2px)');
            })
            .on('mouseout', function() {
                d3.select(this).style('background', '#3b82f6').style('transform', 'translateY(0)');
            })
            .on('click', async () => {
                const userAnswer = verificationInput.property('value').trim();
                if (!userAnswer) {
                    feedbackArea.html('<div style="color: #fbbf24;">⚠️ ' + (this.lang?.translate('learningModeEnterAnswer') || 'Please enter an answer') + '</div>');
                    return;
                }
                
                // Disable button during validation
                submitBtn.property('disabled', true);
                submitBtn.html('⏳ ' + (this.lang?.currentLanguage === 'zh' ? '验证中...' : 'Checking...'));
                
                await this.handleVerificationAnswer(userAnswer, node, modal, modalContent, validation, feedbackArea, verificationQuestion);
                
                // Re-enable button
                submitBtn.property('disabled', false);
                submitBtn.html('✓ ' + (this.lang?.translate('learningModeSubmit') || 'Submit'));
            });
        
        // Skip button (only show after max escalations)
        if (this.currentNodeEscalations >= this.maxEscalations) {
            buttonContainer.append('button')
                .style('flex', '1')
                .style('padding', '14px 24px')
                .style('background', 'rgba(239, 68, 68, 0.8)')
                .style('color', '#fff')
                .style('border', 'none')
                .style('border-radius', '10px')
                .style('font-size', '16px')
                .style('font-weight', '600')
                .style('cursor', 'pointer')
                .style('transition', 'all 0.2s')
                .html('⏭️ ' + (this.lang?.translate('skipQuestion') || 'Skip'))
                .on('mouseover', function() {
                    d3.select(this).style('background', 'rgba(220, 38, 38, 0.9)').style('transform', 'translateY(-2px)');
                })
                .on('mouseout', function() {
                    d3.select(this).style('background', 'rgba(239, 68, 68, 0.8)').style('transform', 'translateY(0)');
                })
                .on('click', () => {
                    this.logger.log('LearningModeManager', `Phase 4: User skipped node after ${this.currentNodeEscalations} escalations`);
                    this.removeNodeHighlight(node);
                    modal.remove();
                    this.restoreNode(node);
                    this.currentNodeEscalations = 0; // Reset for next node
                    this.currentNodeIndex++;
                    this.showNextQuestion();
                });
        }
        
        // Focus input
        verificationInput.node().focus();
        
        this.logger.log('LearningModeManager', `Phase 4: Showing verification question (escalation ${this.currentNodeEscalations})`);
    }
    
    /**
     * Phase 4: Generate verification question from different cognitive angle
     * @param {Object} node - Current node
     * @param {number} escalationLevel - Current escalation level (0-3)
     * @returns {string} - Verification question HTML
     */
    _generateVerificationQuestion(node, escalationLevel) {
        const angles = [
            // Level 0: Structural relationship
            this.lang?.currentLanguage === 'zh' 
                ? `<strong>从结构角度</strong>：这个节点与其他节点有什么关系？` 
                : `<strong>From a structural perspective</strong>: How does this node relate to others?`,
            // Level 1: Functional role
            this.lang?.currentLanguage === 'zh'
                ? `<strong>从功能角度</strong>：这个节点在整个概念中扮演什么角色？`
                : `<strong>From a functional perspective</strong>: What role does this node play in the overall concept?`,
            // Level 2: Application
            this.lang?.currentLanguage === 'zh'
                ? `<strong>从应用角度</strong>：你能举一个这个概念的实际例子吗？`
                : `<strong>From an application perspective</strong>: Can you give a real-world example of this concept?`,
            // Level 3: Definition (simplified)
            this.lang?.currentLanguage === 'zh'
                ? `<strong>用最简单的话</strong>：这个节点的意思是什么？`
                : `<strong>In simplest terms</strong>: What does this node mean?`
        ];
        
        const currentAngle = angles[Math.min(escalationLevel, angles.length - 1)];
        
        return `
            <p style="margin-bottom: 12px;">${currentAngle}</p>
            <p style="opacity: 0.9;">💡 ${this.lang?.currentLanguage === 'zh' ? '请用自己的话回答，不需要完全一样' : 'Answer in your own words - it doesn\'t have to be exact'}</p>
        `;
    }
    
    /**
     * Phase 4: Handle verification answer (correct/incorrect)
     */
    async handleVerificationAnswer(userAnswer, node, modal, modalContent, validation, feedbackArea, verificationQuestion) {
        try {
            // Call backend to verify understanding
            const verificationResult = await this.verifyUnderstandingWithBackend(
                userAnswer,
                node.text,
                verificationQuestion
            );
            
            if (verificationResult.understanding_verified) {
                // ✅ Verification passed!
                feedbackArea.html(`
                    <div style="background: rgba(16, 185, 129, 0.2); border-left: 4px solid #10b981; padding: 12px; border-radius: 8px;">
                        <strong>✓ ${this.lang?.currentLanguage === 'zh' ? '理解确认！' : 'Understanding Verified!'}</strong><br>
                        <span style="opacity: 0.9;">${verificationResult.message || (this.lang?.currentLanguage === 'zh' ? '你真正理解了这个概念！' : 'You truly understand this concept!')}</span>
                    </div>
                `);
                
                this.logger.log('LearningModeManager', `Phase 4: Verification PASSED after ${this.currentNodeEscalations} escalations`);
                
                // Wait a moment for user to read feedback, then move to next
                setTimeout(() => {
                    this.removeNodeHighlight(node);
                    modal.remove();
                    this.restoreNode(node);
                    this.currentNodeEscalations = 0; // Reset for next node
                    this.currentNodeIndex++;
                    this.showNextQuestion();
                }, 2000);
                
            } else {
                // ❌ Verification failed - escalate
                this.currentNodeEscalations++;
                this.misconceptionPatterns.push({
                    nodeId: node.id,
                    userAnswer: userAnswer,
                    correctAnswer: node.text,
                    escalationLevel: this.currentNodeEscalations,
                    timestamp: Date.now()
                });
                
                feedbackArea.html(`
                    <div style="background: rgba(239, 68, 68, 0.2); border-left: 4px solid #ef4444; padding: 12px; border-radius: 8px;">
                        <strong>✗ ${this.lang?.currentLanguage === 'zh' ? '还需要再学习一下' : 'Let\'s Learn More'}</strong><br>
                        <span style="opacity: 0.9;">${verificationResult.message || (this.lang?.currentLanguage === 'zh' ? '我们换个角度再讲一次' : 'Let\'s try a different teaching approach')}</span>
                    </div>
                `);
                
                this.logger.log('LearningModeManager', `Phase 4: Verification FAILED - escalating to level ${this.currentNodeEscalations}`);
                
                if (this.currentNodeEscalations >= this.maxEscalations) {
                    // Max escalations reached - show skip option
                    feedbackArea.append('div')
                        .style('margin-top', '12px')
                        .style('padding', '12px')
                        .style('background', 'rgba(251, 191, 36, 0.2)')
                        .style('border-radius', '8px')
                        .html(`💡 <strong>${this.lang?.currentLanguage === 'zh' ? '已达到最大尝试次数' : 'Maximum attempts reached'}</strong><br>${this.lang?.currentLanguage === 'zh' ? '你可以选择跳过这个问题，或者再试一次' : 'You can skip this question or try once more'}`);
                    
                    // Reload the modal to show skip button
                    setTimeout(() => {
                        this.showVerificationQuestion(modal, modalContent, node, validation);
                    }, 3000);
                } else {
                    // Escalate: Show new teaching materials after delay
                    setTimeout(() => {
                        // TODO: Call V3 agent for escalated teaching materials with different strategy
                        // For now, just re-show verification with higher level
                        this.showVerificationQuestion(modal, modalContent, node, validation);
                    }, 3000);
                }
            }
            
        } catch (error) {
            this.logger.error('LearningModeManager', 'Error verifying understanding:', error);
            feedbackArea.html(`
                <div style="background: rgba(239, 68, 68, 0.2); padding: 12px; border-radius: 8px;">
                    ⚠️ ${this.lang?.currentLanguage === 'zh' ? '验证出错，请重试' : 'Verification error, please try again'}
                </div>
            `);
        }
    }
    
    /**
     * Phase 4: Call backend to verify understanding
     */
    async verifyUnderstandingWithBackend(userAnswer, correctAnswer, verificationQuestion) {
        const response = await auth.fetch('/api/learning/verify_understanding', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: this.sessionId,
                node_id: this.knockedOutNodes[this.currentNodeIndex]?.id,
                user_answer: userAnswer,
                correct_answer: correctAnswer,
                verification_question: verificationQuestion,
                language: this.lang?.currentLanguage || 'en'
            })
        });
        
        if (!response.ok) {
            throw new Error(`Verification API returned ${response.status}`);
        }
        
        return await response.json();
    }
    
    /**
     * Disable editing tools during Learning Mode
     */
    disableEditingTools() {
        const buttons = [
            'add-node-btn',
            'delete-node-btn',
            'auto-complete-btn',
            'duplicate-node-btn',
            'empty-node-btn',
            'reset-btn'
        ];
        
        buttons.forEach(btnId => {
            const btn = document.getElementById(btnId);
            if (btn) {
                btn.disabled = true;
                btn.style.opacity = '0.5';
            }
        });
        
        this.logger.log('LearningModeManager', 'Disabled editing tools');
    }
    
    /**
     * Re-enable editing tools after Learning Mode
     */
    enableEditingTools() {
        const buttons = [
            'add-node-btn',
            'delete-node-btn',
            'auto-complete-btn',
            'duplicate-node-btn',
            'empty-node-btn',
            'reset-btn'
        ];
        
        buttons.forEach(btnId => {
            const btn = document.getElementById(btnId);
            if (btn) {
                btn.disabled = false;
                btn.style.opacity = '1';
            }
        });
        
        this.logger.log('LearningModeManager', 'Re-enabled editing tools');
    }
    
    /**
     * Exit Learning Mode and restore original state
     */
    exitLearningMode() {
        if (!this.isActive) {
            return;
        }
        
        this.logger.log('LearningModeManager', '🛑 Exiting Learning Mode...');
        
        // Restore all knocked out nodes
        this.knockedOutNodes.forEach(node => {
            this.restoreNode(node);
        });
        
        // Remove UI
        if (this.learningOverlay) {
            this.learningOverlay.remove();
            this.learningOverlay = null;
        }
        
        // Re-enable editing tools
        this.enableEditingTools();
        
        // Reset state
        this.isActive = false;
        this.sessionId = null;
        this.knockedOutNodes = [];
        this.currentNodeIndex = 0;
        this.correctAnswers = 0;
        this.totalAttempts = 0;
        this.originalNodeData.clear();
        
        this.logger.log('LearningModeManager', '✅ Learning Mode exited');
    }
}

// Make available globally
window.LearningModeManager = LearningModeManager;

