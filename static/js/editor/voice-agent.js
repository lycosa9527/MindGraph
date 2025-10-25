/**
 * Voice Agent - WebSocket Voice Conversation Controller
 * Handles real-time voice communication with backend
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class VoiceAgent {
    constructor() {
        this.ws = null;
        this.isActive = false;
        this.sessionId = null;
        this.audioContext = null;
        this.audioWorklet = null;
        this.micStream = null;
        this.audioQueue = [];
        this.isPlaying = false;
        this.comicBubble = null;
        
        this.logger = window.logger || console;
    }
    
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
                this.logger.warn('VoiceAgent', 'ComicBubble not available');
            }
            
            this.logger.info('VoiceAgent', 'Initialized');
        } catch (error) {
            this.logger.error('VoiceAgent', 'Init failed:', error);
        }
    }
    
    async startConversation() {
        if (this.isActive) {
            this.logger.warn('VoiceAgent', 'Already active');
            return;
        }
        
        try {
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
            this.logger.info('VoiceAgent', 'Conversation started');
            
            // Update black cat state
            if (window.blackCat) {
                window.blackCat.setState('listening');
            }
            
        } catch (error) {
            this.logger.error('VoiceAgent', 'Start failed:', error);
            if (window.blackCat) {
                window.blackCat.setState('error');
            }
        }
    }
    
    async stopConversation() {
        if (!this.isActive) return;
        
        try {
            // Stop audio capture
            if (this.micStream) {
                this.micStream.getTracks().forEach(track => track.stop());
                this.micStream = null;
            }
            
            // Close WebSocket
            if (this.ws) {
                this.ws.send(JSON.stringify({ type: 'stop' }));
                this.ws.close();
                this.ws = null;
            }
            
            this.isActive = false;
            this.sessionId = null;
            
            this.logger.info('VoiceAgent', 'Conversation stopped');
            
            // Update black cat state
            if (window.blackCat) {
                window.blackCat.setState('idle');
            }
            
            // Hide and clear bubble
            if (this.comicBubble) {
                this.comicBubble.hide();
                this.comicBubble.clear();
            }
            
        } catch (error) {
            this.logger.error('VoiceAgent', 'Stop failed:', error);
        }
    }
    
    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const diagramSessionId = window.sessionManager?.currentSessionId || 'default';
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/voice/${diagramSessionId}`;
            
            // Try to get token from localStorage (won't work for HttpOnly cookies)
            // Backend will read from cookie if query param is missing
            const token = localStorage.getItem('access_token');
            
            // Only add token param if we have one (don't send empty string)
            const wsUrlWithAuth = token ? `${wsUrl}?token=${token}` : wsUrl;
            this.ws = new WebSocket(wsUrlWithAuth);
            
            this.ws.onopen = () => {
                this.logger.info('VoiceAgent', 'WebSocket connected');
                
                // Send start message with context
                const context = this.collectCompleteContext();
                this.logger.info('VoiceAgent', 'Starting conversation with diagram type:', context.diagram_type);
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
                        resolve();
                    }
                } catch (error) {
                    this.logger.error('VoiceAgent', 'Message parse error:', error);
                }
            };
            
            this.ws.onerror = (error) => {
                this.logger.error('VoiceAgent', 'WebSocket error:', error);
                reject(error);
            };
            
            this.ws.onclose = () => {
                this.logger.info('VoiceAgent', 'WebSocket closed');
                this.isActive = false;
            };
        });
    }
    
    async startAudioCapture() {
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
            
            // Log audio capture (every 10th chunk to avoid spam)
            if (Math.random() < 0.1) {
                this.logger.debug('VoiceAgent', `Sending audio chunk: ${audioBase64.length} bytes (PCM16)`);
            }
            
            // Send to server
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'audio',
                    data: audioBase64
                }));
            }
        };
        
        source.connect(processor);
        processor.connect(this.audioContext.destination);
        
        this.audioWorklet = processor;
    }
    
    handleServerMessage(data) {
        switch (data.type) {
            case 'connected':
                this.logger.info('VoiceAgent', 'Session connected:', data.session_id);
                break;
            
            case 'transcription':
                this.logger.info('VoiceAgent', 'Transcription from Omni:', data.text);
                if (window.blackCat) {
                    window.blackCat.setState('thinking');
                }
                // Show thinking bubble
                if (this.comicBubble) {
                    this.comicBubble.clear();
                    this.comicBubble.showThinking();
                }
                break;
            
            case 'text_chunk':
                this.logger.debug('VoiceAgent', 'Text chunk from Omni:', data.text);
                // Stream text to comic bubble
                if (this.comicBubble) {
                    this.comicBubble.appendText(data.text);
                }
                break;
            
            case 'audio_chunk':
                this.logger.debug('VoiceAgent', `Audio chunk from Omni: ${data.audio.length} bytes (PCM24 base64)`);
                this.playAudioChunk(data.audio);
                if (window.blackCat) {
                    window.blackCat.setState('speaking');
                }
                break;
            
            case 'speech_started':
                this.logger.info('VoiceAgent', 'Speech started');
                if (window.blackCat) {
                    window.blackCat.setState('listening');
                }
                // Interrupt playback
                this.audioQueue = [];
                // Hide bubble when user starts speaking
                if (this.comicBubble) {
                    this.comicBubble.hide();
                }
                break;
            
            case 'speech_stopped':
                this.logger.info('VoiceAgent', 'Speech stopped');
                break;
            
            case 'response_done':
                this.logger.info('VoiceAgent', 'Response done');
                if (window.blackCat) {
                    setTimeout(() => {
                        if (this.isActive) {
                            window.blackCat.setState('listening');
                        }
                    }, 500);
                }
                // Auto-hide bubble after response
                if (this.comicBubble) {
                    this.comicBubble.autoHide(4000); // Hide after 4 seconds
                }
                break;
            
            case 'action':
                this.executeAction(data.action, data.params);
                break;
            
            case 'diagram_update':
                this.logger.info('VoiceAgent', 'Diagram update:', data.action, data.updates);
                this.applyDiagramUpdate(data.action, data.updates);
                break;
            
            case 'error':
                this.logger.error('VoiceAgent', 'Server error:', data.error);
                if (window.blackCat) {
                    window.blackCat.setState('error');
                }
                // Show error in bubble
                if (this.comicBubble) {
                    this.comicBubble.clear();
                    this.comicBubble.setText('Oops! Something went wrong 😿');
                    this.comicBubble.show();
                    this.comicBubble.autoHide(3000);
                }
                break;
        }
    }
    
    async playAudioChunk(audioBase64) {
        try {
            // Decode base64 to ArrayBuffer
            const audioData = this.base64ToArrayBuffer(audioBase64);
            
            // Convert PCM16 to Float32
            const pcm16 = new Int16Array(audioData);
            const float32 = new Float32Array(pcm16.length);
            for (let i = 0; i < pcm16.length; i++) {
                float32[i] = pcm16[i] / (pcm16[i] < 0 ? 0x8000 : 0x7FFF);
            }
            
            // Create audio buffer
            const audioBuffer = this.audioContext.createBuffer(1, float32.length, 24000);
            audioBuffer.getChannelData(0).set(float32);
            
            // Queue for playback
            this.audioQueue.push(audioBuffer);
            
            if (!this.isPlaying) {
                this.playNextAudio();
            }
        } catch (error) {
            this.logger.error('VoiceAgent', 'Audio playback error:', error);
        }
    }
    
    playNextAudio() {
        if (this.audioQueue.length === 0) {
            this.isPlaying = false;
            return;
        }
        
        this.isPlaying = true;
        const audioBuffer = this.audioQueue.shift();
        
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);
        
        source.onended = () => {
            this.playNextAudio();
        };
        
        source.start();
    }
    
    executeAction(action, params) {
        this.logger.info('VoiceAgent', 'Executing action:', action, params);
        
        switch (action) {
            // ========== Panel Control ==========
            case 'open_thinkguide':
                if (window.panelManager) {
                    window.panelManager.openPanel('thinkguide');
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 1000);
                }
                break;
            
            case 'close_thinkguide':
                if (window.panelManager) {
                    window.panelManager.closePanel('thinkguide');
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 800);
                }
                break;
            
            case 'open_node_palette':
                if (window.thinkingModeManager) {
                    window.thinkingModeManager.openNodePalette();
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 1000);
                }
                break;
            
            case 'close_node_palette':
                // Node Palette closes by clicking "Finish" or going back to diagram
                const finishBtn = document.getElementById('node-palette-finish-btn');
                if (finishBtn) {
                    finishBtn.click();
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 800);
                }
                break;
            
            case 'open_mindmate':
                if (window.panelManager) {
                    window.panelManager.openPanel('mindmate');
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 1000);
                }
                break;
            
            case 'close_mindmate':
                if (window.panelManager) {
                    window.panelManager.closePanel('mindmate');
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 800);
                }
                break;
            
            case 'close_all_panels':
                if (window.panelManager) {
                    window.panelManager.closeAll();
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 800);
                }
                break;
            
            // ========== Interaction Control ==========
            case 'auto_complete':
                // Trigger the auto-complete button
                const autoCompleteBtn = document.getElementById('auto-complete-btn');
                if (autoCompleteBtn) {
                    autoCompleteBtn.click();
                    this.logger.info('VoiceAgent', 'Auto-complete button triggered');
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 1200);
                }
                break;
            
            case 'ask_thinkguide':
                if (params.message) {
                    // Open ThinkGuide if not already open
                    if (window.panelManager && !window.panelManager.isPanelOpen('thinkguide')) {
                        window.panelManager.openPanel('thinkguide');
                    }
                    // Send message to ThinkGuide
                    if (window.thinkingModeManager) {
                        setTimeout(() => {
                            window.thinkingModeManager.sendMessage(params.message);
                        }, 500); // Small delay to ensure panel is open
                    }
                    if (window.blackCat) {
                        window.blackCat.setState('celebrating');
                        setTimeout(() => {
                            if (this.isActive) window.blackCat.setState('listening');
                        }, 1000);
                    }
                }
                break;
            
            case 'ask_mindmate':
                if (params.message) {
                    // Open MindMate if not already open
                    if (window.panelManager && !window.panelManager.isPanelOpen('mindmate')) {
                        window.panelManager.openPanel('mindmate');
                    }
                    // Send message to MindMate
                    if (window.aiAssistantManager) {
                        setTimeout(() => {
                            // Set the input value and trigger send
                            if (window.aiAssistantManager.chatInput) {
                                window.aiAssistantManager.chatInput.value = params.message;
                                window.aiAssistantManager.sendMessage();
                            }
                        }, 500); // Small delay to ensure panel is open
                    }
                    if (window.blackCat) {
                        window.blackCat.setState('celebrating');
                        setTimeout(() => {
                            if (this.isActive) window.blackCat.setState('listening');
                        }, 1000);
                    }
                }
                break;
            
            case 'explain_node':
                if (params.node_id && params.node_label) {
                    // Open ThinkGuide panel
                    if (window.panelManager) {
                        window.panelManager.openPanel('thinkguide');
                    }
                    // Highlight node
                    if (window.selectionManager) {
                        window.selectionManager.highlightNode(params.node_id);
                    }
                    // Send prompt to ThinkGuide
                    if (window.thinkingModeManager) {
                        const prompt = params.prompt || `Explain the concept of "${params.node_label}" in simple terms for K12 students.`;
                        window.thinkingModeManager.sendMessage(prompt);
                    }
                    // Celebrate
                    if (window.blackCat) {
                        window.blackCat.setState('celebrating');
                        setTimeout(() => {
                            if (this.isActive) window.blackCat.setState('listening');
                        }, 1000);
                    }
                }
                break;
            
            case 'select_node':
                if (params.node_id && window.selectionManager) {
                    window.selectionManager.selectNode(params.node_id);
                    if (window.blackCat) {
                        window.blackCat.setState('celebrating');
                        setTimeout(() => {
                            if (this.isActive) window.blackCat.setState('listening');
                        }, 800);
                    }
                }
                break;
        }
    }
    
    applyDiagramUpdate(action, updates) {
        this.logger.info('VoiceAgent', 'Applying diagram update:', action, updates);
        
        switch (action) {
            case 'update_center':
                // Update center topic/text
                const newText = updates.new_text;
                if (newText && window.currentEditor) {
                    // Update the spec
                    if (window.currentEditor.currentSpec) {
                        window.currentEditor.currentSpec.topic = newText;
                        this.logger.info('VoiceAgent', 'Updated center topic to:', newText);
                        
                        // Re-render diagram
                        window.currentEditor.renderDiagram();
                        this.logger.info('VoiceAgent', 'Diagram re-rendered');
                        
                        // Celebrate success
                        if (window.blackCat) {
                            window.blackCat.setState('celebrating');
                            setTimeout(() => {
                                if (this.isActive) window.blackCat.setState('listening');
                            }, 1000);
                        }
                    }
                }
                break;
            
            case 'update_node':
                // Update a specific node
                const nodeId = updates.node_id;
                const nodeText = updates.new_text;
                if (nodeId && nodeText && window.currentEditor) {
                    window.currentEditor.updateDiagramNode(nodeId, nodeText);
                    this.logger.info('VoiceAgent', 'Updated node:', nodeId, nodeText);
                }
                break;
            
            case 'delete_node':
                // Delete a node
                const deleteNodeId = updates.node_id;
                if (deleteNodeId && window.thinkingModeManager) {
                    window.thinkingModeManager.removeDiagramNode(deleteNodeId);
                    this.logger.info('VoiceAgent', 'Deleted node:', deleteNodeId);
                }
                break;
            
            default:
                this.logger.warn('VoiceAgent', 'Unknown diagram update action:', action);
        }
    }
    
    collectCompleteContext() {
        // Try multiple sources for diagram type (priority order)
        const diagram_type = window.sessionManager?.currentDiagramType 
                          || window.currentEditor?.diagramType 
                          || 'circle_map';  // Default to circle_map instead of 'unknown'
        
        const context = {
            diagram_type: diagram_type,
            active_panel: this.getActivePanelContext(),
            selected_nodes: [],
            conversation_history: [],
            node_palette_open: false,
            diagram_data: {}
        };
        
        // Get selected nodes
        if (window.selectionManager) {
            context.selected_nodes = window.selectionManager.getSelectedNodes() || [];
        }
        
        // Get node palette state
        if (window.nodePaletteManager) {
            context.node_palette_open = window.nodePaletteManager.isOpen || false;
        }
        
        // Get conversation history
        if (window.thinkingModeManager) {
            context.conversation_history = window.thinkingModeManager.conversationHistory || [];
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
    
    getActivePanelContext() {
        if (window.panelManager) {
            const activePanel = window.panelManager.getCurrentPanel();
            return activePanel || 'thinkguide';
        }
        return 'thinkguide';
    }
    
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
    
    destroy() {
        this.stopConversation();
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}

window.VoiceAgent = VoiceAgent;

