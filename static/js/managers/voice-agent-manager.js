/**
 * Voice Agent Manager (Event Bus Version)
 * ========================================
 * 
 * Handles real-time voice conversation with backend via WebSocket.
 * Integrates with Event Bus for decoupled communication.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class VoiceAgentManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        
        // WebSocket
        this.ws = null;
        this.sessionId = null;
        
        // Audio
        this.audioContext = null;
        this.audioWorklet = null;
        this.micStream = null;
        this.audioQueue = [];
        this.isPlaying = false;
        this.currentAudioSource = null;
        
        // State
        this.isActive = false;
        
        // UI Components
        this.comicBubble = null;
        this.blackCat = null;
        
        // Initialize
        this.init();
        this.subscribeToEvents();
        
        this.logger.info('VoiceAgentManager', 'Initialized with Event Bus');
    }
    
    /**
     * Initialize audio context and UI components
     */
    async init() {
        try {
            // Initialize audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 24000
            });
            
            // Initialize comic bubble
            if (window.ComicBubble) {
                this.comicBubble = new ComicBubble();
                this.comicBubble.init();
            } else {
                this.logger.warn('VoiceAgentManager', 'ComicBubble not available');
            }
            
            // Get black cat reference
            this.blackCat = window.blackCat;
            
            this.logger.info('VoiceAgentManager', 'Initialized');
        } catch (error) {
            this.logger.error('VoiceAgentManager', 'Init failed:', error);
        }
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for voice agent start/stop requests
        this.eventBus.on('voice:start_requested', () => this.startConversation());
        this.eventBus.on('voice:stop_requested', () => this.stopConversation());
        
        // Listen for panel state changes (to provide context)
        this.eventBus.on('state:changed', (data) => {
            if (data.path === 'panels' && this.isActive) {
                this.updateContext();
            }
        });
        
        this.logger.debug('VoiceAgentManager', 'Subscribed to events');
    }
    
    /**
     * Start voice conversation
     */
    async startConversation() {
        if (this.isActive) {
            this.logger.warn('VoiceAgentManager', 'Already active');
            return;
        }
        
        try {
            // Update state
            this.stateManager.updateVoice({ active: true });
            
            // Get microphone access
            this.micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,
                    channelCount: 1
                }
            });
            
            // Connect WebSocket
            await this.connectWebSocket();
            
            // Start capturing audio
            await this.startAudioCapture();
            
            this.isActive = true;
            
            this.logger.info('VoiceAgentManager', 'Conversation started');
            
            // Emit event
            this.eventBus.emit('voice:started', { sessionId: this.sessionId });
            
            // Update black cat state
            if (this.blackCat) {
                this.blackCat.setState('listening');
            }
            
        } catch (error) {
            this.logger.error('VoiceAgentManager', 'Start failed:', error);
            
            // Update state
            this.stateManager.updateVoice({ 
                active: false,
                error: error.message
            });
            
            // Emit error event
            this.eventBus.emit('voice:error', { error: error.message });
            
            if (this.blackCat) {
                this.blackCat.setState('error');
            }
        }
    }
    
    /**
     * Stop voice conversation
     */
    async stopConversation() {
        if (!this.isActive) return;
        
        try {
            // Stop audio capture
            if (this.micStream) {
                this.micStream.getTracks().forEach(track => track.stop());
                this.micStream = null;
            }
            
            // Disconnect audio worklet/processor
            if (this.audioWorklet) {
                try {
                    this.audioWorklet.disconnect();
                } catch (e) {
                    // Ignore if already disconnected
                }
                this.audioWorklet = null;
            }
            
            // Stop currently playing audio immediately
            if (this.currentAudioSource) {
                try {
                    this.currentAudioSource.stop();
                    this.currentAudioSource.disconnect();
                } catch (e) {
                    // Ignore if already stopped
                }
                this.currentAudioSource = null;
            }
            
            // Clear audio playback queue and stop playback
            this.audioQueue = [];
            this.isPlaying = false;
            
            // Close WebSocket
            if (this.ws) {
                this.ws.send(JSON.stringify({ type: 'stop' }));
                this.ws.close();
                this.ws = null;
            }
            
            this.isActive = false;
            this.sessionId = null;
            
            // Update state
            this.stateManager.updateVoice({ 
                active: false,
                sessionId: null
            });
            
            this.logger.info('VoiceAgentManager', 'Conversation stopped');
            
            // Emit event
            this.eventBus.emit('voice:stopped', {});
            
            // Update black cat state
            if (this.blackCat) {
                this.blackCat.setState('idle');
            }
            
            // Hide and clear bubble
            if (this.comicBubble) {
                this.comicBubble.hide();
                this.comicBubble.clear();
            }
            
        } catch (error) {
            this.logger.error('VoiceAgentManager', 'Stop failed:', error);
        }
    }
    
    /**
     * Connect to WebSocket
     */
    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const diagramSessionId = window.sessionManager?.currentSessionId || 'default';
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/voice/${diagramSessionId}`;
            
            // Try to get token from localStorage
            const token = localStorage.getItem('access_token');
            const wsUrlWithAuth = token ? `${wsUrl}?token=${token}` : wsUrl;
            
            this.ws = new WebSocket(wsUrlWithAuth);
            
            this.ws.onopen = () => {
                this.logger.info('VoiceAgentManager', 'WebSocket connected');
                
                // Send start message with context
                const context = this.collectContext();
                this.ws.send(JSON.stringify({
                    type: 'start',
                    diagram_type: context.diagram_type,
                    active_panel: context.active_panel,
                    context: context
                }));
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleServerMessage(data);
                    
                    if (data.type === 'connected') {
                        this.sessionId = data.session_id;
                        this.stateManager.updateVoice({ sessionId: this.sessionId });
                        resolve();
                    }
                } catch (error) {
                    this.logger.error('VoiceAgentManager', 'Message parse error:', error);
                }
            };
            
            this.ws.onerror = (error) => {
                this.logger.error('VoiceAgentManager', 'WebSocket error:', error);
                this.eventBus.emit('voice:ws_error', { error });
                reject(error);
            };
            
            this.ws.onclose = () => {
                this.logger.info('VoiceAgentManager', 'WebSocket closed');
                this.isActive = false;
                this.stateManager.updateVoice({ active: false });
                this.eventBus.emit('voice:ws_closed', {});
            };
        });
    }
    
    /**
     * Start audio capture
     */
    async startAudioCapture() {
        if (!this.audioContext) {
            throw new Error('AudioContext not initialized');
        }
        
        // Resume AudioContext if suspended (browser policy)
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
            this.logger.info('VoiceAgentManager', 'AudioContext resumed');
        }
        
        const source = this.audioContext.createMediaStreamSource(this.micStream);
        
        // Use ScriptProcessorNode for audio capture (compatibility)
        const processor = this.audioContext.createScriptProcessor(4096, 1, 1);
        
        processor.onaudioprocess = (e) => {
            if (!this.isActive) return;
            
            const inputData = e.inputBuffer.getChannelData(0);
            
            // Convert float32 to int16
            const pcm16 = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Convert to base64
            const audioBase64 = this.arrayBufferToBase64(pcm16.buffer);
            
            // Send to server
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'audio',
                    data: audioBase64
                }));
                
                // Log audio data being sent (debug)
                this.logger.debug('VoiceAgentManager', `Sending audio: ${pcm16.length} samples`);
            }
        };
        
        source.connect(processor);
        processor.connect(this.audioContext.destination);
        
        this.audioWorklet = processor;
        
        this.logger.info('VoiceAgentManager', 'Audio capture started');
    }
    
    /**
     * Handle server WebSocket message
     */
    handleServerMessage(data) {
        switch (data.type) {
            case 'connected':
                this.logger.info('VoiceAgentManager', 'Session connected:', data.session_id);
                this.eventBus.emit('voice:connected', { sessionId: data.session_id });
                break;
            
            case 'transcription':
                this.logger.info('VoiceAgentManager', 'Transcription:', data.text);
                this.eventBus.emit('voice:transcription', { text: data.text });
                
                if (this.blackCat) {
                    this.blackCat.setState('thinking');
                }
                
                if (this.comicBubble) {
                    this.comicBubble.clear();
                    this.comicBubble.showThinking();
                }
                break;
            
            case 'text_chunk':
                this.logger.debug('VoiceAgentManager', 'Text chunk:', data.text);
                this.eventBus.emit('voice:text_chunk', { text: data.text });
                
                if (this.comicBubble) {
                    this.comicBubble.appendText(data.text);
                }
                break;
            
            case 'audio_chunk':
                this.logger.debug('VoiceAgentManager', `Audio chunk: ${data.audio.length} bytes`);
                this.playAudioChunk(data.audio);
                
                if (this.blackCat) {
                    this.blackCat.setState('speaking');
                }
                break;
            
            case 'speech_started':
                this.logger.info('VoiceAgentManager', 'Speech started');
                this.eventBus.emit('voice:speech_started', {});
                
                if (this.blackCat) {
                    this.blackCat.setState('listening');
                }
                
                // Interrupt playback
                this.audioQueue = [];
                
                if (this.comicBubble) {
                    this.comicBubble.hide();
                }
                break;
            
            case 'speech_stopped':
                this.logger.info('VoiceAgentManager', 'Speech stopped');
                this.eventBus.emit('voice:speech_stopped', {});
                break;
            
            case 'response_done':
                this.logger.info('VoiceAgentManager', 'Response done');
                this.eventBus.emit('voice:response_done', {});
                
                if (this.blackCat) {
                    setTimeout(() => {
                        if (this.isActive) {
                            this.blackCat.setState('listening');
                        }
                    }, 500);
                }
                
                if (this.comicBubble) {
                    this.comicBubble.autoHide(4000);
                }
                break;
            
            case 'action':
                this.executeAction(data.action, data.params);
                break;
            
            case 'diagram_update':
                this.logger.info('VoiceAgentManager', 'Diagram update:', data.action, data.updates);
                this.applyDiagramUpdate(data.action, data.updates);
                break;
            
            case 'error':
                this.logger.error('VoiceAgentManager', 'Server error:', data.error);
                this.eventBus.emit('voice:server_error', { error: data.error });
                
                if (this.blackCat) {
                    this.blackCat.setState('error');
                }
                
                if (this.comicBubble) {
                    this.comicBubble.clear();
                    this.comicBubble.setText('Oops! Something went wrong 😿');
                    this.comicBubble.show();
                    this.comicBubble.autoHide(3000);
                }
                break;
        }
    }
    
    /**
     * Execute action from voice command
     */
    executeAction(action, params) {
        this.logger.info('VoiceAgentManager', 'Executing action:', action, params);
        
        switch (action) {
            // ========== Panel Control (via Event Bus) ==========
            case 'open_thinkguide':
                this.eventBus.emit('panel:open_requested', { panel: 'thinkguide' });
                this.celebrate();
                break;
            
            case 'close_thinkguide':
                this.eventBus.emit('panel:close_requested', { panel: 'thinkguide' });
                this.celebrate(800);
                break;
            
            case 'open_node_palette':
                this.eventBus.emit('panel:open_requested', { panel: 'nodePalette' });
                this.celebrate();
                break;
            
            case 'close_node_palette':
                this.eventBus.emit('panel:close_requested', { panel: 'nodePalette' });
                this.celebrate(800);
                break;
            
            case 'open_mindmate':
                this.eventBus.emit('panel:open_requested', { panel: 'mindmate' });
                this.celebrate();
                break;
            
            case 'close_mindmate':
                this.eventBus.emit('panel:close_requested', { panel: 'mindmate' });
                this.celebrate(800);
                break;
            
            case 'close_all_panels':
                this.eventBus.emit('panel:close_all_requested', {});
                this.celebrate(800);
                break;
            
            // ========== Interaction Control ==========
            case 'auto_complete':
                const autoCompleteBtn = document.getElementById('auto-complete-btn');
                if (autoCompleteBtn) {
                    autoCompleteBtn.click();
                    this.logger.info('VoiceAgentManager', 'Auto-complete triggered');
                }
                this.celebrate(1200);
                break;
            
            case 'ask_thinkguide':
                if (params.message) {
                    // Emit event to send message to ThinkGuide
                    this.eventBus.emit('thinkguide:send_message', { message: params.message });
                    this.celebrate();
                }
                break;
            
            case 'ask_mindmate':
                if (params.message) {
                    // Emit event to send message to MindMate
                    this.eventBus.emit('mindmate:send_message', { message: params.message });
                    this.celebrate();
                }
                break;
            
            case 'explain_node':
                if (params.node_id && params.node_label) {
                    // Open ThinkGuide
                    this.eventBus.emit('panel:open_requested', { panel: 'thinkguide' });
                    
                    // Highlight node
                    this.eventBus.emit('selection:highlight_requested', { nodeId: params.node_id });
                    
                    // Send prompt to ThinkGuide
                    const prompt = params.prompt || `Explain the concept of "${params.node_label}" in simple terms for K12 students.`;
                    setTimeout(() => {
                        this.eventBus.emit('thinkguide:send_message', { message: prompt });
                    }, 500);
                    
                    this.celebrate();
                }
                break;
            
            case 'select_node':
                if (params.node_id) {
                    this.eventBus.emit('selection:select_requested', { nodeId: params.node_id });
                    this.celebrate(800);
                }
                break;
        }
        
        // Emit generic action event
        this.eventBus.emit('voice:action_executed', { action, params });
    }
    
    /**
     * Apply diagram update from voice command
     */
    applyDiagramUpdate(action, updates) {
        this.logger.info('VoiceAgentManager', 'Applying diagram update:', action, updates);
        
        // Emit event for diagram update
        this.eventBus.emit('diagram:update_requested', { action, updates });
        
        switch (action) {
            case 'update_center':
                const newText = updates.new_text;
                if (newText && window.currentEditor && window.currentEditor.currentSpec) {
                    window.currentEditor.currentSpec.topic = newText;
                    window.currentEditor.renderDiagram();
                    this.celebrate();
                }
                break;
            
            case 'update_node':
                const nodeId = updates.node_id;
                const nodeText = updates.new_text;
                if (nodeId && nodeText && window.currentEditor) {
                    window.currentEditor.updateDiagramNode(nodeId, nodeText);
                }
                break;
            
            case 'delete_node':
                const deleteNodeId = updates.node_id;
                if (deleteNodeId && window.thinkingModeManager) {
                    window.thinkingModeManager.removeDiagramNode(deleteNodeId);
                }
                break;
        }
    }
    
    /**
     * Collect context from State Manager
     */
    collectContext() {
        const state = this.stateManager.getState();
        
        const diagram_type = window.sessionManager?.currentDiagramType 
                          || window.currentEditor?.diagramType 
                          || 'circle_map';
        
        const context = {
            diagram_type: diagram_type,
            active_panel: this.getActivePanel(),
            selected_nodes: [],
            conversation_history: [],
            node_palette_open: false,
            diagram_data: {},
            panels: state.panels || {}
        };
        
        // Get selected nodes
        if (window.selectionManager) {
            context.selected_nodes = window.selectionManager.getSelectedNodes() || [];
        }
        
        // Get node palette state
        const nodePaletteState = state.panels?.nodePalette;
        if (nodePaletteState) {
            context.node_palette_open = nodePaletteState.isOpen || false;
        }
        
        // Get conversation history from ThinkGuide state
        const thinkguideState = state.panels?.thinkguide;
        if (thinkguideState) {
            context.conversation_history = thinkguideState.conversationHistory || [];
        }
        
        // Get current diagram data
        if (window.currentEditor && window.currentEditor.currentSpec) {
            const spec = window.currentEditor.currentSpec;
            context.diagram_data = {
                center: {
                    text: spec.topic || ''
                },
                children: spec.children || spec.context || spec.adjectives || spec.items || []
            };
        }
        
        return context;
    }
    
    /**
     * Get active panel
     */
    getActivePanel() {
        const state = this.stateManager.getState();
        const panels = state.panels || {};
        
        // Find first open panel
        for (const [name, panelState] of Object.entries(panels)) {
            if (panelState.isOpen) {
                return name;
            }
        }
        
        return 'none';
    }
    
    /**
     * Update context when state changes
     */
    updateContext() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const context = this.collectContext();
            this.ws.send(JSON.stringify({
                type: 'context_update',
                context: context
            }));
        }
    }
    
    /**
     * Audio playback
     */
    async playAudioChunk(audioBase64) {
        try {
            const audioData = this.base64ToArrayBuffer(audioBase64);
            const pcm16 = new Int16Array(audioData);
            const float32 = new Float32Array(pcm16.length);
            
            for (let i = 0; i < pcm16.length; i++) {
                float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7FFF);
            }
            
            const audioBuffer = this.audioContext.createBuffer(1, float32.length, 24000);
            audioBuffer.getChannelData(0).set(float32);
            
            this.audioQueue.push(audioBuffer);
            
            if (!this.isPlaying) {
                this.playNextAudio();
            }
        } catch (error) {
            this.logger.error('VoiceAgentManager', 'Audio playback error:', error);
        }
    }
    
    playNextAudio() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            this.currentAudioSource = null;
            return;
        }
        
        this.isPlaying = true;
        const audioBuffer = this.audioQueue.shift();
        
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);
        
        // Store reference to current source
        this.currentAudioSource = source;
        
        source.onended = () => {
            this.currentAudioSource = null;
            this.playNextAudio();
        };
        
        source.start();
    }
    
    /**
     * Helper: Celebrate action (black cat animation)
     */
    celebrate(delay = 1000) {
        if (this.blackCat) {
            this.blackCat.setState('celebrating');
            setTimeout(() => {
                if (this.isActive) {
                    this.blackCat.setState('listening');
                }
            }, delay);
        }
    }
    
    /**
     * Utility methods
     */
    arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }
    
    base64ToArrayBuffer(base64) {
        const binaryString = window.atob(base64);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    }
    
    /**
     * Cleanup
     */
    destroy() {
        this.logger.debug('VoiceAgentManager', 'Destroying');
        
        // Stop any active conversation
        if (this.isActive) {
            this.stopConversation();
        }
        
        // Stop any playing audio
        if (this.currentAudioSource) {
            try {
                this.currentAudioSource.stop();
                this.currentAudioSource.disconnect();
            } catch (e) {
                // Ignore if already stopped
            }
            this.currentAudioSource = null;
        }
        
        // Close WebSocket
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        // Release audio resources
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        if (this.audioWorklet) {
            this.audioWorklet = null;
        }
        
        if (this.micStream) {
            this.micStream.getTracks().forEach(track => track.stop());
            this.micStream = null;
        }
        
        // Remove Event Bus listeners
        this.eventBus.off('voice:start_requested');
        this.eventBus.off('voice:stop_requested');
        this.eventBus.off('state:changed');
        
        // Clear session
        this.sessionId = null;
        this.isActive = false;
        this.isPlaying = false;
        this.audioQueue = [];
        
        // Cleanup UI references
        if (this.comicBubble) {
            this.comicBubble.hide();
        }
        
        // Nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.comicBubble = null;
        this.blackCat = null;
        this.logger = null;
    }
}

// NOTE: No longer auto-initialized globally.
// Now created per-session in DiagramSelector and managed by SessionLifecycleManager.

