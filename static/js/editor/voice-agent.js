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
        
        this.logger = window.logger || console;
    }
    
    async init() {
        try {
            // Initialize audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 24000
            });
            
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
            
        } catch (error) {
            this.logger.error('VoiceAgent', 'Stop failed:', error);
        }
    }
    
    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const diagramSessionId = window.sessionManager?.currentSessionId || 'default';
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/voice/${diagramSessionId}`;
            
            // Add token to URL
            const token = localStorage.getItem('access_token') || '';
            this.ws = new WebSocket(`${wsUrl}?token=${token}`);
            
            this.ws.onopen = () => {
                this.logger.info('VoiceAgent', 'WebSocket connected');
                
                // Send start message with context
                const context = this.collectCompleteContext();
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
                this.logger.info('VoiceAgent', 'Transcription:', data.text);
                if (window.blackCat) {
                    window.blackCat.setState('thinking');
                }
                break;
            
            case 'text_chunk':
                this.logger.debug('VoiceAgent', 'Text chunk:', data.text);
                break;
            
            case 'audio_chunk':
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
                break;
            
            case 'action':
                this.executeAction(data.action, data.params);
                break;
            
            case 'error':
                this.logger.error('VoiceAgent', 'Server error:', data.error);
                if (window.blackCat) {
                    window.blackCat.setState('error');
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
            case 'open_node_palette':
                if (window.panelManager) {
                    window.panelManager.openPanel('thinkguide');
                }
                if (window.nodePaletteManager) {
                    window.nodePaletteManager.open();
                }
                if (window.blackCat) {
                    window.blackCat.setState('celebrating');
                    setTimeout(() => {
                        if (this.isActive) window.blackCat.setState('listening');
                    }, 1000);
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
    
    collectCompleteContext() {
        const context = {
            diagram_type: window.sessionManager?.currentDiagramType || 'unknown',
            active_panel: this.getActivePanelContext(),
            selected_nodes: [],
            conversation_history: [],
            node_palette_open: false
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
        
        return context;
    }
    
    getActivePanelContext() {
        if (window.panelManager) {
            const activePanel = window.panelManager.getActivePanel();
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

