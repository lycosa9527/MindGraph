/**
 * Voice Agent Manager (Event Bus Version)
 * ========================================
 * 
 * Handles real-time voice conversation with backend via WebSocket.
 * Integrates with Event Bus for decoupled communication.
 * Supports both voice and text input via chat window.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class VoiceAgentManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        
        // Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'VoiceAgentManager';
        
        // WebSocket
        this.ws = null;
        this.sessionId = null;
        this.diagramSessionId = null; // Store for cleanup (available even after currentEditor is destroyed)
        
        // Cleanup state
        this._cleaningUp = false; // Guard flag to prevent new connections during cleanup
        
        // Audio
        this.audioContext = null;
        this.audioWorklet = null;        // Fallback ScriptProcessorNode
        this.audioWorkletNode = null;    // Modern AudioWorkletNode
        this.audioSource = null;         // MediaStreamSource
        this.micStream = null;
        this.audioQueue = [];
        this.isPlaying = false;
        this.currentAudioSource = null;
        
        // State
        this.isActive = false;
        this.isVoiceActive = false; // Voice input enabled
        
        // UI Components
        this.comicBubble = null;
        this.blackCat = null;
        
        // Store callback references for proper cleanup
        this.callbacks = {
            voiceStart: () => this.startConversation(),
            voiceStop: () => this.stopConversation(),
            stateChanged: (data) => {
                // Update context when panels OR diagram changes
                if (this.isActive && (data.path === 'panels' || data.path === 'diagram')) {
                    this.updateContext();
                }
            },
            diagramRendered: () => {
                // Update context after diagram re-renders (nodes may have changed)
                if (this.isActive) {
                    this.updateContext();
                }
            },
            sessionEnding: (data) => {
                // CRITICAL: Cleanup backend voice session when session ends
                // This ensures WebSocket connections are closed and backend state is cleared
                this.cleanupBackendSession(data.sessionId);
            }
        };
        
        // Track initialization state
        this._initialized = false;
        
        // Track destruction state to prevent double destruction
        this._destroyed = false;
        
        this.logger.info('VoiceAgentManager', 'Created (call init() to initialize)');
    }
    
    /**
     * Initialize audio context and UI components
     */
    async init() {
        // Prevent double initialization
        if (this._initialized) {
            this.logger.warn('VoiceAgentManager', 'Already initialized, skipping');
            return;
        }
        this._initialized = true;
        
        try {
            // Initialize audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 24000
            });
            
            // Initialize comic bubble / chat window
            if (window.ComicBubble) {
                this.comicBubble = new ComicBubble();
                this.comicBubble.init();
                
                // Wire up callbacks
                this.comicBubble.onSendMessage = (text) => this.sendTextMessage(text);
                this.comicBubble.onVoiceToggle = (active) => this.toggleVoiceInput(active);
                
                this.logger.info('VoiceAgentManager', 'ComicBubble initialized with callbacks');
            } else {
                this.logger.warn('VoiceAgentManager', 'ComicBubble not available');
            }
            
            // Get black cat reference
            this.blackCat = window.blackCat;
            
            // Set up black cat click to toggle chat window
            if (this.blackCat) {
                this.blackCat.onClick = () => {
                    if (this.comicBubble) {
                        // Always toggle the chat window
                        this.comicBubble.toggleWindow();
                        
                        // If opening window and not connected, start connection
                        if (this.comicBubble.isWindowVisible && !this.isActive) {
                            this.startConversation();
                        }
                    }
                };
                this.logger.info('VoiceAgentManager', 'BlackCat click handler set');
            } else {
                this.logger.warn('VoiceAgentManager', 'BlackCat not available');
            }
            
            // Subscribe to events
            this.subscribeToEvents();
            
            this.logger.info('VoiceAgentManager', 'Fully initialized');
        } catch (error) {
            this.logger.error('VoiceAgentManager', 'Init failed:', error);
            this._initialized = false; // Allow retry on error
        }
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for voice agent start/stop requests - use stored callbacks with owner tracking
        this.eventBus.onWithOwner('voice:start_requested', this.callbacks.voiceStart, this.ownerId);
        this.eventBus.onWithOwner('voice:stop_requested', this.callbacks.voiceStop, this.ownerId);
        
        // Listen for state changes (panels, diagram) to update context
        this.eventBus.onWithOwner('state:changed', this.callbacks.stateChanged, this.ownerId);
        
        // Listen for diagram re-renders to update context with latest nodes
        this.eventBus.onWithOwner('diagram:rendered', this.callbacks.diagramRendered, this.ownerId);
        
        // CRITICAL: Listen for session ending event to cleanup backend state
        // This ensures backend WebSocket connections are closed when leaving canvas
        this.eventBus.onWithOwner('lifecycle:session_ending', this.callbacks.sessionEnding, this.ownerId);
        
        this.logger.debug('VoiceAgentManager', 'Event listeners registered with owner tracking');
    }
    
    /**
     * Start conversation (WebSocket connection)
     */
    async startConversation() {
        // CRITICAL: Check if manager is destroyed - cannot start if destroyed
        if (this._destroyed) {
            this.logger.warn('VoiceAgentManager', 'Cannot start conversation: manager is destroyed');
            throw new Error('Voice agent manager has been destroyed');
        }
        
        // CRITICAL: Reset cleanup flag when starting a new conversation
        // This allows new connections after cleanup is complete
        if (this._cleaningUp) {
            this.logger.debug('VoiceAgentManager', 'Resetting cleanup flag for new conversation');
            this._cleaningUp = false;
        }
        
        // CRITICAL: Clear conversation history when starting a new conversation
        // This ensures old messages don't persist when switching diagrams
        if (this.comicBubble) {
            this.comicBubble.clearMessages();
            this.logger.debug('VoiceAgentManager', 'Cleared conversation history for new session');
        }
        if (this.isActive) {
            this.logger.debug('VoiceAgentManager', 'Already active');
            return;
        }
        
        try {
            // Update state
            this.stateManager.updateVoice({ active: true });
            
            // Connect WebSocket
            await this.connectWebSocket();
            
            this.isActive = true;
            
            this.logger.info('VoiceAgentManager', 'Conversation started');
            
            // Emit event through EventBus
            this.eventBus.emit('voice:started', { sessionId: this.sessionId });
            
            // Update StateManager
            if (this.stateManager) {
                this.stateManager.updateVoice({ 
                    active: true,
                    sessionId: this.sessionId,
                    startedAt: Date.now()
                });
            }
            
            // Update UI
            if (this.comicBubble) {
                this.comicBubble.setStatus('active');
            }
            
            if (this.blackCat) {
                this.blackCat.setState('idle');
            }
            
        } catch (error) {
            // Extract meaningful error message
            const errorMessage = error instanceof Error 
                ? error.message 
                : (typeof error === 'string' 
                    ? error 
                    : (error?.message || error?.toString() || 'Unknown error'));
            
            this.logger.error('VoiceAgentManager', 'Start failed:', error instanceof Error ? error : new Error(errorMessage));
            
            // Update state
            this.stateManager.updateVoice({ 
                active: false,
                error: errorMessage
            });
            
            // Emit error event
            this.eventBus.emit('voice:error', { error: errorMessage });
            
            if (this.comicBubble) {
                this.comicBubble.setStatus('error');
            }
            
            if (this.blackCat) {
                this.blackCat.setState('error');
            }
        }
    }
    
    /**
     * Toggle voice input (microphone)
     */
    async toggleVoiceInput(active) {
        this.logger.info('VoiceAgentManager', 'Toggle voice input:', active);
        
        if (active) {
            try {
                await this.startVoiceInput();
            } catch (error) {
                this.logger.error('VoiceAgentManager', 'Failed to start voice:', error);
                if (this.comicBubble) {
                    this.comicBubble.setVoiceActive(false);
                    this.comicBubble.addMessage('Failed to access microphone. Please check permissions.', 'agent');
                }
            }
        } else {
            this.stopVoiceInput();
        }
    }
    
    /**
     * Start voice input (microphone capture)
     */
    async startVoiceInput() {
        if (this.isVoiceActive) return;
        
        try {
            // Check if MediaDevices API is available
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                const isSecureContext = window.isSecureContext || location.protocol === 'https:';
                const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
                let errorMessage = 'Microphone access is not available. ';
                
                if (!isSecureContext && !isLocalhost) {
                    // IP address over HTTP - needs HTTPS
                    errorMessage += 'Voice input requires HTTPS when accessing via IP address. ';
                    errorMessage += 'Solutions: 1) Use HTTPS (recommended), 2) Use localhost for testing, or 3) Use a reverse proxy with SSL.';
                } else if (!isSecureContext && isLocalhost) {
                    // localhost over HTTP - should work but might not in some browsers
                    errorMessage += 'Voice input may not work over HTTP. Please use HTTPS or ensure your browser allows getUserMedia on localhost.';
                } else if (!navigator.mediaDevices) {
                    errorMessage += 'Your browser does not support the MediaDevices API.';
                } else {
                    errorMessage += 'getUserMedia is not available in your browser.';
                }
                
                this.logger.error('VoiceAgentManager', errorMessage);
                if (this.comicBubble) {
                    this.comicBubble.setVoiceActive(false);
                    this.comicBubble.addMessage(errorMessage, 'agent');
                }
                throw new Error(errorMessage);
            }
            
            // Ensure conversation is active
            if (!this.isActive) {
                await this.startConversation();
            }
            
            // Get microphone access
            this.micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 16000,
                    channelCount: 1
                }
            });
            
            // Start capturing audio
            await this.startAudioCapture();
            
            this.isVoiceActive = true;
            
            this.logger.info('VoiceAgentManager', 'Voice input started');
            
            // Update UI
            if (this.comicBubble) {
                this.comicBubble.setVoiceActive(true);
            }
            
            if (this.blackCat) {
                this.blackCat.setState('listening');
            }
            
        } catch (error) {
            this.logger.error('VoiceAgentManager', 'Voice input failed:', error);
            
            if (this.comicBubble) {
                this.comicBubble.setVoiceActive(false);
                // Only show error message if it's not already shown above
                if (!error.message || !error.message.includes('Microphone access is not available')) {
                    const errorMessage = error.name === 'NotAllowedError' 
                        ? 'Microphone permission denied. Please allow microphone access in your browser settings.'
                        : error.name === 'NotFoundError'
                        ? 'No microphone found. Please connect a microphone and try again.'
                        : 'Failed to access microphone: ' + (error.message || error.toString());
                    this.comicBubble.addMessage(errorMessage, 'agent');
                }
            }
        }
    }
    
    /**
     * Stop voice input
     */
    stopVoiceInput() {
        if (!this.isVoiceActive) return;
        
        // Stop audio capture
        if (this.micStream) {
            this.micStream.getTracks().forEach(track => track.stop());
            this.micStream = null;
        }
        
        // Stop AudioWorkletNode
        if (this.audioWorkletNode) {
            try {
                // Tell worklet to stop processing
                this.audioWorkletNode.port.postMessage({ command: 'stop' });
                this.audioWorkletNode.disconnect();
            } catch (e) {
                // Ignore if already disconnected
            }
            this.audioWorkletNode = null;
        }
        
        // Disconnect audio source
        if (this.audioSource) {
            try {
                this.audioSource.disconnect();
            } catch (e) {
                // Ignore if already disconnected
            }
            this.audioSource = null;
        }
        
        // Disconnect fallback processor
        if (this.audioWorklet) {
            try {
                this.audioWorklet.disconnect();
            } catch (e) {
                // Ignore if already disconnected
            }
            this.audioWorklet = null;
        }
        
        this.isVoiceActive = false;
        
        this.logger.info('VoiceAgentManager', 'Voice input stopped');
        
        // Update UI
        if (this.comicBubble) {
            this.comicBubble.setVoiceActive(false);
        }
        
        if (this.blackCat && this.isActive) {
            this.blackCat.setState('idle');
        }
    }
    
    /**
     * Stop voice conversation
     */
    async stopConversation() {
        if (!this.isActive) return;
        
        // CRITICAL: Guard against null logger (can happen during cleanup)
        const logger = this.logger || console;
        
        try {
            // Stop voice input first
            this.stopVoiceInput();
            
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
                try {
                    if (this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send(JSON.stringify({ type: 'stop' }));
                    }
                    this.ws.close();
                } catch (e) {
                    // Ignore if already closed
                }
                this.ws = null;
            }
            
            // CRITICAL: Clear conversation history when stopping
            // This ensures clean state when restarting or switching diagrams
            if (this.comicBubble) {
                this.comicBubble.clearMessages();
                logger.debug('VoiceAgentManager', 'Cleared conversation history on stop');
            }
            
            this.isActive = false;
            this.sessionId = null;
            
            // Update state (only if stateManager still exists)
            if (this.stateManager) {
                try {
                    this.stateManager.updateVoice({ 
                        active: false,
                        sessionId: null
                    });
                } catch (e) {
                    // Ignore if stateManager is being destroyed
                }
            }
            
            logger.info('VoiceAgentManager', 'Conversation stopped');
            
            // Emit event (only if eventBus still exists)
            if (this.eventBus) {
                try {
                    this.eventBus.emit('voice:stopped', {});
                } catch (e) {
                    // Ignore if eventBus is being destroyed
                }
            }
            
            // Update black cat state
            if (this.blackCat) {
                try {
                    this.blackCat.setState('idle');
                } catch (e) {
                    // Ignore if blackCat is being destroyed
                }
            }
            
        } catch (error) {
            logger.error('VoiceAgentManager', 'Stop failed:', error);
        }
    }
    
    /**
     * Send text message through WebSocket
     */
    async sendTextMessage(text) {
        if (!text || !text.trim()) return;
        
        this.logger.info('VoiceAgentManager', 'Sending text message:', text.substring(0, 50));
        
        // Ensure conversation is active
        if (!this.isActive) {
            this.logger.info('VoiceAgentManager', 'Starting conversation before sending...');
            try {
                await this.startConversation();
                // Wait for connection to stabilize
                await new Promise(resolve => setTimeout(resolve, 300));
            } catch (error) {
                this.logger.error('VoiceAgentManager', 'Failed to start conversation:', error);
                if (this.comicBubble) {
                    this.comicBubble.addMessage('Failed to connect. Please try again.', 'agent');
                }
                return;
            }
        }
        
        this._sendText(text);
    }
    
    _sendText(text) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.logger.warn('VoiceAgentManager', 'WebSocket not ready');
            return;
        }
        
        // Send text message to server
        this.ws.send(JSON.stringify({
            type: 'text',
            text: text
        }));
        
        this.logger.info('VoiceAgentManager', 'Text message sent:', text);
        
        // Show thinking state
        if (this.comicBubble) {
            this.comicBubble.showThinking();
        }
        
        if (this.blackCat) {
            this.blackCat.setState('thinking');
        }
    }
    
    /**
     * Connect to WebSocket
     */
    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            // Use safe logger access (fallback to console if logger is null)
            const logger = this.logger || console;
            
            // CRITICAL: Prevent new connections if manager is destroyed
            // Note: _cleaningUp is reset in startConversation(), so we only check _destroyed here
            if (this._destroyed) {
                reject(new Error('Cannot connect: manager destroyed'));
                return;
            }
            
            // CRITICAL: If cleanup is in progress, reject immediately
            // This prevents race conditions where cleanup starts during connection attempt
            // NOTE: _cleaningUp should be reset in startConversation() before calling connectWebSocket(),
            // but we check here defensively in case cleanup starts between startConversation() and connectWebSocket()
            if (this._cleaningUp) {
                logger.warn('VoiceAgentManager', 'Connection rejected: cleanup flag is still true (should have been reset in startConversation)');
                reject(new Error('Cannot connect: cleanup in progress'));
                return;
            }
            
            // CRITICAL: Close existing WebSocket connection before creating a new one
            // This ensures clean state when switching diagrams
            if (this.ws) {
                const oldWs = this.ws;
                this.ws = null;
                try {
                    // Remove all event listeners to prevent callbacks during close
                    oldWs.onopen = null;
                    oldWs.onmessage = null;
                    oldWs.onerror = null;
                    oldWs.onclose = null;
                    // Close the connection
                    if (oldWs.readyState === WebSocket.OPEN || oldWs.readyState === WebSocket.CONNECTING) {
                        oldWs.close(1001, 'Switching to new diagram session');
                    }
                    logger.debug('VoiceAgentManager', 'Closed existing WebSocket before reconnecting');
                } catch (e) {
                    logger.debug('VoiceAgentManager', 'Error closing existing WebSocket', e);
                }
            }
            
            // CRITICAL: Get diagram session ID from current editor or session lifecycle
            // Use currentEditor.sessionId first (most reliable), then sessionLifecycle, then fallback to 'default'
            const diagramSessionId = window.currentEditor?.sessionId || 
                                     window.sessionLifecycle?.currentSessionId || 
                                     window.diagramSelector?.currentSession?.id || 
                                     'default';
            
            // Log session ID source for debugging
            const sessionIdSource = window.currentEditor?.sessionId ? 'currentEditor' :
                                    window.sessionLifecycle?.currentSessionId ? 'sessionLifecycle' :
                                    window.diagramSelector?.currentSession?.id ? 'diagramSelector' :
                                    'default';
            logger.debug('VoiceAgentManager', `Using diagram session ID from ${sessionIdSource}: ${diagramSessionId.substr(-8)}`);
            
            // CRITICAL: Store diagram session ID for cleanup (available even after currentEditor is destroyed)
            this.diagramSessionId = diagramSessionId;
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/voice/${diagramSessionId}`;
            
            // Try to get token from localStorage
            const token = localStorage.getItem('access_token');
            const wsUrlWithAuth = token ? `${wsUrl}?token=${token}` : wsUrl;
            
            this.ws = new WebSocket(wsUrlWithAuth);
            
            this.ws.onopen = () => {
                // CRITICAL: Check again if cleanup started during connection
                if (this._cleaningUp || this._destroyed) {
                    logger.debug('VoiceAgentManager', 'Cleanup started during connection, closing WebSocket');
                    this.ws.close();
                    reject(new Error('Cleanup started during connection'));
                    return;
                }
                
                logger.info('VoiceAgentManager', 'WebSocket connected');
                
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
                    logger.error('VoiceAgentManager', 'Message parse error:', error);
                }
            };
            
            this.ws.onerror = (event) => {
                // WebSocket error events don't provide detailed error info
                // Extract meaningful information from the WebSocket connection state
                const wsState = this.ws ? {
                    readyState: this.ws.readyState,
                    url: this.ws.url,
                    protocol: this.ws.protocol,
                    extensions: this.ws.extensions
                } : null;
                
                const errorMessage = `WebSocket connection failed. State: ${wsState ? `readyState=${wsState.readyState} (${['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'][wsState.readyState] || 'UNKNOWN'}), url=${wsState.url}` : 'WebSocket not initialized'}`;
                
                logger.error('VoiceAgentManager', 'WebSocket error:', new Error(errorMessage));
                
                if (this.eventBus) {
                    this.eventBus.emit('voice:ws_error', { 
                        error: errorMessage,
                        wsState: wsState
                    });
                }
                
                // Reset UI state on error
                if (this.comicBubble) {
                    this.comicBubble.setVoiceActive(false);
                    this.comicBubble.setStatus('error');
                    this.comicBubble.addMessage('连接失败，请重试', 'agent');
                }
                if (this.blackCat) {
                    this.blackCat.setState('error');
                }
                
                reject(new Error(errorMessage));
            };
            
            this.ws.onclose = (event) => {
                // CloseEvent provides code, reason, and wasClean properties
                const closeInfo = event ? {
                    code: event.code,
                    reason: event.reason || 'No reason provided',
                    wasClean: event.wasClean
                } : null;
                
                if (closeInfo && !closeInfo.wasClean) {
                    // Unexpected closure - log as error with details
                    const closeMessage = `WebSocket closed unexpectedly. Code: ${closeInfo.code}, Reason: ${closeInfo.reason}`;
                    logger.error('VoiceAgentManager', 'WebSocket closed unexpectedly:', new Error(closeMessage));
                } else {
                    logger.info('VoiceAgentManager', 'WebSocket closed', closeInfo);
                }
                
                this.isActive = false;
                this.isVoiceActive = false;
                
                if (this.stateManager) {
                    this.stateManager.updateVoice({ 
                        active: false,
                        stoppedAt: Date.now(),
                        closeCode: closeInfo?.code,
                        closeReason: closeInfo?.reason,
                        wasClean: closeInfo?.wasClean
                    });
                }
                
                if (this.eventBus) {
                    this.eventBus.emit('voice:ws_closed', { 
                        code: closeInfo?.code,
                        reason: closeInfo?.reason,
                        wasClean: closeInfo?.wasClean
                    });
                }
                
                // Reset UI state
                if (this.comicBubble) {
                    this.comicBubble.setVoiceActive(false);
                    this.comicBubble.setStatus('idle');
                }
                if (this.blackCat) {
                    this.blackCat.setState('idle');
                }
            };
        });
    }
    
    /**
     * Start audio capture using AudioWorkletNode (modern API)
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
        
        try {
            // Load the audio worklet module
            await this.audioContext.audioWorklet.addModule('/static/js/audio/pcm-processor.js');
            this.logger.debug('VoiceAgentManager', 'Audio worklet module loaded');
            
            // Create source from microphone
            const source = this.audioContext.createMediaStreamSource(this.micStream);
            
            // Create AudioWorkletNode
            this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'pcm-processor');
            
            // Handle messages from the worklet (audio data)
            this.audioWorkletNode.port.onmessage = (event) => {
                if (!this.isVoiceActive) return;
                
                if (event.data.type === 'audio') {
                    // Convert ArrayBuffer to base64
                    const audioBase64 = this.arrayBufferToBase64(event.data.data);
                    
                    // Send to server
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send(JSON.stringify({
                            type: 'audio',
                            data: audioBase64
                        }));
                        
                        this.logger.debug('VoiceAgentManager', `Sending audio: ${event.data.data.byteLength / 2} samples`);
                    }
                }
            };
            
            // Connect: source -> worklet
            source.connect(this.audioWorkletNode);
            
            // Store source reference for cleanup
            this.audioSource = source;
            
            this.logger.info('VoiceAgentManager', 'Audio capture started (AudioWorklet)');
            
        } catch (error) {
            // Fallback to ScriptProcessorNode for older browsers
            this.logger.warn('VoiceAgentManager', 'AudioWorklet not supported, falling back to ScriptProcessor:', error.message);
            await this.startAudioCaptureFallback();
        }
    }
    
    /**
     * Fallback audio capture using deprecated ScriptProcessorNode
     * For browsers that don't support AudioWorklet
     */
    async startAudioCaptureFallback() {
        const source = this.audioContext.createMediaStreamSource(this.micStream);
        
        const processor = this.audioContext.createScriptProcessor(4096, 1, 1);
        
        processor.onaudioprocess = (e) => {
            if (!this.isVoiceActive) return;
            
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
                
                this.logger.debug('VoiceAgentManager', `Sending audio: ${pcm16.length} samples`);
            }
        };
        
        source.connect(processor);
        processor.connect(this.audioContext.destination);
        
        this.audioWorklet = processor;
        this.audioSource = source;
        
        this.logger.info('VoiceAgentManager', 'Audio capture started (ScriptProcessor fallback)');
    }
    
    /**
     * Handle server WebSocket message
     */
    handleServerMessage(data) {
        // CRITICAL: Don't process messages if destroyed or cleaning up
        // This prevents audio chunks and other messages from being processed after cleanup
        if (this._destroyed || this._cleaningUp) {
            this.logger.debug('VoiceAgentManager', 'Ignoring message after destruction/cleanup:', data.type);
            return;
        }
        
        switch (data.type) {
            case 'connected':
                this.logger.info('VoiceAgentManager', 'Session connected:', data.session_id);
                this.eventBus.emit('voice:connected', { sessionId: data.session_id });
                
                // Update state manager
                if (this.stateManager) {
                    this.stateManager.updateVoice({ 
                        sessionId: data.session_id,
                        connected: true,
                        connectedAt: Date.now()
                    });
                }
                break;
            
            case 'transcription':
                this.logger.info('VoiceAgentManager', 'Transcription:', data.text);
                this.eventBus.emit('voice:transcription', { text: data.text });
                
                // Update state manager
                if (this.stateManager) {
                    this.stateManager.updateVoice({ 
                        lastTranscription: data.text,
                        lastTranscriptionTime: Date.now()
                    });
                }
                
                // Add user message to chat window (voice input)
                if (this.comicBubble && data.text) {
                    this.comicBubble.addMessage(data.text, 'user');
                }
                
                if (this.blackCat) {
                    this.blackCat.setState('thinking');
                }
                
                if (this.comicBubble) {
                    this.comicBubble.showThinking();
                }
                break;
            
            case 'text_chunk':
                this.logger.debug('VoiceAgentManager', 'Text chunk:', data.text);
                this.eventBus.emit('voice:text_chunk', { text: data.text });
                
                if (this.comicBubble) {
                    // Start streaming if not already
                    if (!this.comicBubble.currentStreamingMessage) {
                        this.comicBubble.startStreaming();
                    }
                    this.comicBubble.appendText(data.text);
                }
                break;
            
            case 'audio_chunk':
                // CRITICAL: Double-check destroyed flag before playing audio
                // This prevents audio from playing after cleanupBackendSession() is called
                if (!this._destroyed && !this._cleaningUp) {
                    this.logger.debug('VoiceAgentManager', `Audio chunk: ${data.audio.length} bytes`);
                    
                    // Emit event through EventBus
                    this.eventBus.emit('voice:audio_chunk', { audio: data.audio });
                    
                    this.playAudioChunk(data.audio);
                } else {
                    this.logger.debug('VoiceAgentManager', 'Ignoring audio chunk (destroyed/cleaning up)');
                }
                
                if (this.blackCat) {
                    this.blackCat.setState('speaking');
                }
                break;
            
            case 'speech_started':
                this.logger.info('VoiceAgentManager', 'Speech started');
                this.eventBus.emit('voice:speech_started', { audioStartMs: data.audio_start_ms });
                
                // Update state manager
                if (this.stateManager) {
                    this.stateManager.updateVoice({ 
                        isSpeaking: true,
                        speechStartedAt: Date.now()
                    });
                }
                
                if (this.blackCat) {
                    this.blackCat.setState('listening');
                }
                
                // Interrupt playback
                this.audioQueue = [];
                break;
            
            case 'speech_stopped':
                this.logger.info('VoiceAgentManager', 'Speech stopped');
                this.eventBus.emit('voice:speech_stopped', { audioEndMs: data.audio_end_ms });
                
                // Update state manager
                if (this.stateManager) {
                    this.stateManager.updateVoice({ 
                        isSpeaking: false,
                        speechStoppedAt: Date.now()
                    });
                }
                break;
            
            case 'response_done':
                this.logger.info('VoiceAgentManager', 'Response done');
                this.eventBus.emit('voice:response_done', {});
                
                // Update state manager
                if (this.stateManager) {
                    this.stateManager.updateVoice({ 
                        lastResponseTime: Date.now(),
                        responseCount: (this.stateManager.getVoiceState()?.responseCount || 0) + 1
                    });
                }
                
                // Finish streaming message
                if (this.comicBubble) {
                    this.comicBubble.finishStreaming();
                    this.comicBubble.setStatus('active');
                }
                
                if (this.blackCat) {
                    setTimeout(() => {
                        if (this.isActive && !this.isVoiceActive) {
                            this.blackCat.setState('idle');
                        } else if (this.isVoiceActive) {
                            this.blackCat.setState('listening');
                        }
                    }, 500);
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
                
                // Update state manager
                if (this.stateManager) {
                    this.stateManager.updateVoice({ 
                        error: data.error,
                        errorTime: Date.now()
                    });
                }
                
                if (this.blackCat) {
                    this.blackCat.setState('error');
                }
                
                if (this.comicBubble) {
                    this.comicBubble.addMessage('Oops! Something went wrong.', 'agent');
                    this.comicBubble.setStatus('error');
                }
                break;
            
            // Informational events (forwarded through EventBus for future use)
            case 'session_created':
                this.logger.debug('VoiceAgentManager', 'Session created:', data.session);
                this.eventBus.emit('voice:session_created', { session: data.session });
                break;
            
            case 'session_updated':
                this.logger.debug('VoiceAgentManager', 'Session updated:', data.session);
                this.eventBus.emit('voice:session_updated', { session: data.session });
                break;
            
            case 'response_created':
                this.logger.debug('VoiceAgentManager', 'Response created:', data.response);
                this.eventBus.emit('voice:response_created', { response: data.response });
                break;
            
            case 'audio_buffer_committed':
                this.logger.debug('VoiceAgentManager', 'Audio buffer committed:', data.item_id);
                this.eventBus.emit('voice:audio_buffer_committed', { itemId: data.item_id });
                break;
            
            case 'audio_buffer_cleared':
                this.logger.debug('VoiceAgentManager', 'Audio buffer cleared');
                this.eventBus.emit('voice:audio_buffer_cleared', {});
                break;
            
            case 'item_created':
                this.logger.debug('VoiceAgentManager', 'Item created:', data.item);
                this.eventBus.emit('voice:item_created', { item: data.item });
                break;
            
            case 'response_text_done':
                this.logger.debug('VoiceAgentManager', 'Response text done:', data.text);
                this.eventBus.emit('voice:response_text_done', { text: data.text });
                break;
            
            case 'response_audio_done':
                this.logger.debug('VoiceAgentManager', 'Response audio done');
                this.eventBus.emit('voice:response_audio_done', {});
                break;
            
            case 'response_audio_transcript_done':
                this.logger.debug('VoiceAgentManager', 'Response audio transcript done:', data.transcript);
                this.eventBus.emit('voice:response_audio_transcript_done', { transcript: data.transcript });
                break;
            
            case 'output_item_added':
                this.logger.debug('VoiceAgentManager', 'Output item added:', data.item);
                this.eventBus.emit('voice:output_item_added', { item: data.item });
                break;
            
            case 'output_item_done':
                this.logger.debug('VoiceAgentManager', 'Output item done:', data.item);
                this.eventBus.emit('voice:output_item_done', { item: data.item });
                break;
            
            case 'content_part_added':
                this.logger.debug('VoiceAgentManager', 'Content part added:', data.part);
                this.eventBus.emit('voice:content_part_added', { part: data.part });
                break;
            
            case 'content_part_done':
                this.logger.debug('VoiceAgentManager', 'Content part done:', data.part);
                this.eventBus.emit('voice:content_part_done', { part: data.part });
                break;
            
            default:
                this.logger.debug('VoiceAgentManager', 'Unhandled message type:', data.type);
                // Still emit through EventBus for potential future listeners
                this.eventBus.emit(`voice:${data.type}`, data);
                break;
        }
    }
    
    /**
     * Execute action from voice command
     */
    executeAction(action, params) {
        this.logger.info('VoiceAgentManager', 'Executing action via Event Bus:', action, params);
        
        // Track action in State Manager
        if (this.stateManager) {
            this.stateManager.updateVoice({ 
                lastAction: action,
                lastActionTime: Date.now()
            });
        }
        
        switch (action) {
            // ========== Panel Control (via Event Bus) ==========
            case 'open_thinkguide':
                this.eventBus.emit('panel:open_requested', { panel: 'thinkguide', source: 'voice_agent' });
                this.celebrate();
                break;
            
            case 'close_thinkguide':
                this.eventBus.emit('panel:close_requested', { panel: 'thinkguide', source: 'voice_agent' });
                this.celebrate(800);
                break;
            
            case 'open_node_palette':
                this.eventBus.emit('panel:open_requested', { panel: 'nodePalette', source: 'voice_agent' });
                this.celebrate();
                break;
            
            case 'close_node_palette':
                this.eventBus.emit('panel:close_requested', { panel: 'nodePalette', source: 'voice_agent' });
                this.celebrate(800);
                break;
            
            case 'open_mindmate':
                this.eventBus.emit('panel:open_requested', { panel: 'mindmate', source: 'voice_agent' });
                this.celebrate();
                break;
            
            case 'close_mindmate':
                this.eventBus.emit('panel:close_requested', { panel: 'mindmate', source: 'voice_agent' });
                this.celebrate(800);
                break;
            
            case 'close_all_panels':
                this.eventBus.emit('panel:close_all_requested', { source: 'voice_agent' });
                this.celebrate(800);
                break;
            
            // ========== Interaction Control ==========
            case 'auto_complete':
                this.eventBus.emit('diagram:auto_complete_requested', { source: 'voice_agent' });
                this.logger.info('VoiceAgentManager', 'Auto-complete requested via Event Bus');
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
                if (params.node_id || params.node_index !== undefined) {
                    this.eventBus.emit('selection:select_requested', { 
                        nodeId: params.node_id,
                        nodeIndex: params.node_index 
                    });
                    this.logger.info('VoiceAgentManager', 'Node selection requested via Event Bus');
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
        this.logger.info('VoiceAgentManager', 'Applying diagram update via Event Bus:', action, updates);
        
        // All diagram updates go through Event Bus - fully native integration
        // State Manager is updated by the listeners (InteractiveEditor)
        switch (action) {
            case 'update_center':
                // Pass through all structured data from LLM (left/right, title, event, whole, dimension, etc.)
                // No keyword parsing needed - LLM handles it!
                this.eventBus.emit('diagram:update_center', { 
                    ...updates,  // Spread all fields (left, right, title, event, whole, dimension, new_text, etc.)
                    source: 'voice_agent'
                });
                // Update State Manager directly for voice action tracking
                if (this.stateManager) {
                    this.stateManager.updateVoice({ lastAction: 'update_center' });
                }
                this.celebrate();
                break;
            
            case 'update_node':
            case 'update_nodes':
                const nodeUpdates = Array.isArray(updates) ? updates : [updates];
                this.eventBus.emit('diagram:update_nodes', { 
                    nodes: nodeUpdates,
                    source: 'voice_agent'
                });
                if (this.stateManager) {
                    this.stateManager.updateVoice({ lastAction: 'update_nodes' });
                }
                this.celebrate();
                break;
            
            case 'add_node':
            case 'add_nodes':
                const nodesToAdd = Array.isArray(updates) ? updates : [updates];
                this.eventBus.emit('diagram:add_nodes', { 
                    nodes: nodesToAdd,
                    source: 'voice_agent'
                });
                if (this.stateManager) {
                    this.stateManager.updateVoice({ lastAction: 'add_nodes' });
                }
                this.celebrate();
                break;
            
            case 'delete_node':
            case 'remove_nodes':
                // Handle both string nodeIds and structured objects with category
                const nodeIdsToRemove = Array.isArray(updates) ? updates : [updates];
                // Normalize: convert strings to objects if needed, preserve category if present
                const normalizedNodeIds = nodeIdsToRemove.map(item => {
                    if (typeof item === 'string') {
                        return item;
                    } else if (item && typeof item === 'object') {
                        return item; // Already structured with node_id and possibly category
                    } else {
                        return item;
                    }
                });
                this.eventBus.emit('diagram:remove_nodes', { 
                    nodeIds: normalizedNodeIds,
                    source: 'voice_agent'
                });
                if (this.stateManager) {
                    this.stateManager.updateVoice({ lastAction: 'remove_nodes' });
                }
                this.celebrate();
                break;
            
            default:
                // Generic update event for any other actions
                this.eventBus.emit('diagram:update_requested', { 
                    action, 
                    updates,
                    source: 'voice_agent'
                });
                break;
        }
    }
    
    /**
     * Collect context from State Manager
     */
    collectContext() {
        const state = this.stateManager.getState();
        
        // CRITICAL: Get diagram type from current editor or session lifecycle
        const diagram_type = window.currentEditor?.diagramType || 
                            window.currentEditor?.sessionDiagramType ||
                            window.sessionLifecycle?.diagramType ||
                            'circle_map';
        
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
        
        // Get current diagram data with structured node info (including IDs)
        if (window.currentEditor && window.currentEditor.currentSpec) {
            const spec = window.currentEditor.currentSpec;
            const rawNodes = spec.children || spec.context || spec.attributes || spec.adjectives || spec.items || [];
            
            // Determine ID prefix based on diagram type
            const prefixMap = {
                'circle_map': 'context',
                'bubble_map': 'attribute',
                'tree_map': 'item',
                'flow_map': 'step',
                'brace_map': 'part',
                'mindmap': 'branch',
                'concept_map': 'concept',
                'double_bubble_map': 'node'
            };
            const prefix = prefixMap[context.diagram_type] || 'node';
            
            // Convert to structured format with IDs
            const structuredNodes = rawNodes.map((node, index) => {
                if (typeof node === 'string') {
                    return {
                        id: `${prefix}_${index}`,
                        index: index,
                        text: node
                    };
                } else if (typeof node === 'object') {
                    return {
                        id: node.id || `${prefix}_${index}`,
                        index: index,
                        text: node.text || node.label || node.content || String(node)
                    };
                }
                return { id: `${prefix}_${index}`, index: index, text: String(node) };
            });
            
            context.diagram_data = {
                center: {
                    text: spec.topic || ''
                },
                children: structuredNodes
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
        // CRITICAL: Prevent playback if destroyed or audio context is closed
        if (this._destroyed || !this.audioContext || this.audioContext.state === 'closed') {
            this.isPlaying = false;
            this.currentAudioSource = null;
            this.audioQueue = [];
            return;
        }
        
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
            // CRITICAL: Check if destroyed before playing next audio
            if (this._destroyed) {
                this.currentAudioSource = null;
                this.isPlaying = false;
                return;
            }
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
                if (this.isActive && !this.isVoiceActive) {
                    this.blackCat.setState('idle');
                } else if (this.isVoiceActive) {
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
     * Cleanup backend voice session (called when session ends via lifecycle event)
     * CRITICAL: This immediately terminates all voice agent activity (audio, WebSocket, microphone)
     * before calling the backend cleanup API. This ensures instant termination when user leaves canvas.
     * 
     * @param {string} diagramSessionId - Diagram session ID from lifecycle event
     */
    cleanupBackendSession(diagramSessionId) {
        const logger = this.logger || console;
        
        // CRITICAL: Set cleanup flag immediately to prevent new connections and message processing
        this._cleaningUp = true;
        
        // CRITICAL: Remove event listeners IMMEDIATELY to prevent handlers from executing after cleanup
        // This prevents race conditions where events fire between cleanupBackendSession() and destroy()
        if (this.eventBus && this.ownerId) {
            this.eventBus.removeAllListenersForOwner(this.ownerId);
            logger.debug('VoiceAgentManager', 'Event listeners removed in cleanupBackendSession');
        }
        
        // CRITICAL: Immediately stop all voice agent activity before backend cleanup
        // This ensures instant termination when user leaves canvas, even if destroy() hasn't been called yet
        
        // 1. Stop audio playback IMMEDIATELY (if agent is speaking)
        if (this.currentAudioSource) {
            try {
                // Remove onended callback to prevent recursive playback
                this.currentAudioSource.onended = null;
                this.currentAudioSource.stop();
                this.currentAudioSource.disconnect();
                logger.debug('VoiceAgentManager', 'Stopped audio playback in cleanupBackendSession');
            } catch (e) {
                // Ignore if already stopped or invalid state
                logger.debug('VoiceAgentManager', 'Error stopping audio in cleanupBackendSession (may already be stopped)', e);
            }
            this.currentAudioSource = null;
        }
        
        // 2. Clear audio queue to prevent any queued audio from playing
        this.audioQueue = [];
        this.isPlaying = false;
        
        // 3. Suspend audio context immediately to stop all audio processing
        if (this.audioContext && this.audioContext.state !== 'closed') {
            try {
                this.audioContext.suspend().catch(e => {
                    logger.debug('VoiceAgentManager', 'Error suspending audio context in cleanupBackendSession', e);
                });
            } catch (e) {
                logger.debug('VoiceAgentManager', 'Error suspending audio context in cleanupBackendSession', e);
            }
        }
        
        // 4. Stop voice input (microphone) IMMEDIATELY
        if (this.isVoiceActive) {
            this.stopVoiceInput();
            logger.debug('VoiceAgentManager', 'Stopped voice input in cleanupBackendSession');
        }
        
        // 5. Close WebSocket connection IMMEDIATELY
        if (this.ws) {
            try {
                // CRITICAL: Remove all event handlers BEFORE closing to prevent handlers from firing after cleanup
                // This prevents errors when handlers try to access null logger or other destroyed properties
                this.ws.onopen = null;
                this.ws.onmessage = null;
                this.ws.onerror = null;
                this.ws.onclose = null;
                
                // Send stop message if connection is still open
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({ type: 'stop' }));
                }
                this.ws.close();
                logger.debug('VoiceAgentManager', 'Closed WebSocket in cleanupBackendSession');
            } catch (e) {
                logger.debug('VoiceAgentManager', 'Error closing WebSocket in cleanupBackendSession', e);
            }
            this.ws = null;
        }
        
        // 6. Mark conversation as inactive
        this.isActive = false;
        this.isVoiceActive = false;
        
        // Update StateManager
        if (this.stateManager) {
            this.stateManager.updateVoice({ 
                active: false,
                isListening: false,
                isSpeaking: false,
                cleanupStartedAt: Date.now()
            });
        }
        
        // Emit lifecycle event through EventBus
        if (this.eventBus) {
            this.eventBus.emit('voice:cleanup_started', { 
                diagramSessionId: diagramSessionId 
            });
        }
        
        // 7. Get diagram session ID if not provided
        // CRITICAL: Use a local variable (can't reassign function parameter)
        // Use stored diagramSessionId first (available even after currentEditor is destroyed)
        // Fallback: try to get from parameter, current editor, or session manager
        // CRITICAL: Get session ID from multiple sources with proper fallback order
        const sessionIdToCleanup = diagramSessionId || 
                                   this.diagramSessionId || 
                                   window.currentEditor?.sessionId || 
                                   window.sessionLifecycle?.currentSessionId ||
                                   window.diagramSelector?.currentSession?.id;
        
        // 8. Emit lifecycle event before backend cleanup
        if (this.eventBus) {
            this.eventBus.emit('voice:cleanup_backend_requested', { 
                diagramSessionId: sessionIdToCleanup 
            });
        }
        
        // 9. Call backend cleanup endpoint to close WebSocket connections and clean up backend state
        if (sessionIdToCleanup && window.auth) {
            logger.debug('VoiceAgentManager', 'Calling backend cleanup API', {
                diagramSessionId: sessionIdToCleanup.substr(-8),
                source: diagramSessionId ? 'parameter' : (this.diagramSessionId ? 'stored' : 'fallback')
            });
            
            window.auth.fetch(`/api/voice/cleanup/${sessionIdToCleanup}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            }).then(() => {
                logger.debug('VoiceAgentManager', 'Backend cleanup completed', {
                    diagramSessionId: sessionIdToCleanup.substr(-8)
                });
                
                // Emit lifecycle event after successful backend cleanup
                if (this.eventBus) {
                    this.eventBus.emit('voice:cleanup_backend_completed', { 
                        diagramSessionId: sessionIdToCleanup 
                    });
                }
            }).catch(err => {
                logger.warn('VoiceAgentManager', 'Backend voice cleanup failed', {
                    diagramSessionId: sessionIdToCleanup?.substr(-8),
                    error: err.message
                });
                
                // Emit lifecycle event for cleanup failure
                if (this.eventBus) {
                    this.eventBus.emit('voice:cleanup_backend_failed', { 
                        diagramSessionId: sessionIdToCleanup,
                        error: err.message
                    });
                }
            });
        } else {
            logger.warn('VoiceAgentManager', 'Skipping backend cleanup - missing required data', {
                hasParameter: !!diagramSessionId,
                hasStored: !!this.diagramSessionId,
                hasEditor: !!window.currentEditor?.sessionId,
                hasSessionLifecycle: !!window.sessionLifecycle?.currentSessionId,
                hasDiagramSelector: !!window.diagramSelector?.currentSession?.id,
                hasAuth: !!window.auth,
                finalSessionId: sessionIdToCleanup
            });
        }
        
        logger.info('VoiceAgentManager', 'Immediate voice agent termination complete (user left canvas)');
        
        // CRITICAL: DO NOT reset _cleaningUp here - manager will be destroyed next
        // The flag should remain true until destroy() is called to prevent any race conditions
        // If a new manager instance is created, it will have _cleaningUp = false by default
    }
    
    /**
     * Cleanup
     * 
     * CRITICAL: This method is idempotent and safe to call even if cleanupBackendSession()
     * already stopped audio/WebSocket. All operations check for existence before executing.
     * 
     * Order of operations:
     * 1. cleanupBackendSession() is called first (via lifecycle:session_ending event)
     *    - Immediately stops audio, closes WebSocket, stops microphone
     *    - Calls backend cleanup API
     * 2. destroy() is called second (by SessionLifecycleManager)
     *    - Performs final cleanup of resources (AudioContext, event listeners, UI)
     *    - Safe to call even if cleanupBackendSession() already stopped everything
     */
    destroy() {
        // CRITICAL: Prevent double destruction - if already destroyed, return early
        if (this._destroyed) {
            const logger = this.logger || console;
            logger.debug('VoiceAgentManager', 'Already destroyed, skipping duplicate destroy() call');
            return;
        }
        
        // Mark as destroyed immediately to prevent re-entry and stop audio playback
        this._destroyed = true;
        
        // CRITICAL: Guard against null logger (defensive programming)
        const logger = this.logger || console;
        logger.debug('VoiceAgentManager', 'Destroying - performing final cleanup (cleanupBackendSession may have already stopped audio/WebSocket)');
        
        // CRITICAL: Stop audio playback IMMEDIATELY, even if conversation is not active
        // This ensures audio stops even if user left canvas while agent is speaking
        // NOTE: cleanupBackendSession() may have already stopped this, but we check anyway (idempotent)
        if (this.currentAudioSource) {
            try {
                // Remove onended callback to prevent recursive playback
                this.currentAudioSource.onended = null;
                this.currentAudioSource.stop();
                this.currentAudioSource.disconnect();
                logger.debug('VoiceAgentManager', 'Stopped current audio playback');
            } catch (e) {
                // Ignore if already stopped or invalid state
                logger.debug('VoiceAgentManager', 'Error stopping audio source (may already be stopped)', e);
            }
            this.currentAudioSource = null;
        }
        
        // Clear audio queue to prevent any queued audio from playing
        this.audioQueue = [];
        this.isPlaying = false;
        
        // CRITICAL: Suspend audio context immediately to stop all audio processing
        if (this.audioContext && this.audioContext.state !== 'closed') {
            try {
                this.audioContext.suspend().catch(e => {
                    logger.debug('VoiceAgentManager', 'Error suspending audio context', e);
                });
            } catch (e) {
                logger.debug('VoiceAgentManager', 'Error suspending audio context', e);
            }
        }
        
        // CRITICAL: Stop any active conversation (this sends 'stop' message and closes WebSocket)
        if (this.isActive) {
            this.stopConversation();
        }
        
        // CRITICAL: Explicitly close WebSocket if still open (defensive cleanup)
        if (this.ws) {
            try {
                // CRITICAL: Remove all event handlers BEFORE closing to prevent handlers from firing after destroy()
                // This prevents errors when handlers try to access null logger or other destroyed properties
                this.ws.onopen = null;
                this.ws.onmessage = null;
                this.ws.onerror = null;
                this.ws.onclose = null;
                
                // Send stop message if connection is still open
                if (this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({ type: 'stop' }));
                }
                this.ws.close();
                logger.debug('VoiceAgentManager', 'WebSocket explicitly closed in destroy()');
            } catch (e) {
                logger.debug('VoiceAgentManager', 'Error closing WebSocket in destroy()', e);
            }
            this.ws = null;
        }
        
        // Release audio resources
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        if (this.audioWorkletNode) {
            try {
                this.audioWorkletNode.disconnect();
            } catch (e) {}
            this.audioWorkletNode = null;
        }
        
        if (this.audioWorklet) {
            try {
                this.audioWorklet.disconnect();
            } catch (e) {}
            this.audioWorklet = null;
        }
        
        if (this.audioSource) {
            try {
                this.audioSource.disconnect();
            } catch (e) {}
            this.audioSource = null;
        }
        
        if (this.micStream) {
            this.micStream.getTracks().forEach(track => track.stop());
            this.micStream = null;
        }
        
        // Remove all Event Bus listeners using Listener Registry
        // NOTE: Event listeners may have already been removed in cleanupBackendSession(),
        // but we check again here for idempotency
        if (this.eventBus && this.ownerId) {
            this.eventBus.removeAllListenersForOwner(this.ownerId);
            logger.debug('VoiceAgentManager', 'Event listeners removed in destroy() (may have been removed already)');
        }
        
        // Clear session
        this.sessionId = null;
        this.isActive = false;
        this.isVoiceActive = false;
        this.isPlaying = false;
        this.audioQueue = [];
        
        // Update StateManager - mark as destroyed
        if (this.stateManager) {
            this.stateManager.updateVoice({ 
                active: false,
                sessionId: null,
                isListening: false,
                isSpeaking: false,
                destroyedAt: Date.now()
            });
        }
        
        // Emit lifecycle event through EventBus
        if (this.eventBus) {
            this.eventBus.emit('voice:destroyed', {});
        }
        
        // CRITICAL: Cleanup UI references - explicitly hide modal before destroy
        if (this.comicBubble) {
            // Ensure modal is hidden before destroying (prevents lingering visible modals)
            if (this.comicBubble.isWindowVisible) {
                this.comicBubble.hideWindow();
            }
            if (this.comicBubble.isBubbleVisible) {
                this.comicBubble.hideBubble();
            }
            // Now destroy (which will do full cleanup)
            this.comicBubble.destroy();
        }
        
        // Nullify references
        this.callbacks = null;
        this.eventBus = null;
        this.stateManager = null;
        this.comicBubble = null;
        this.blackCat = null;
        this.logger = null;
    }
}

// NOTE: No longer auto-initialized globally.
// Now created per-session in DiagramSelector and managed by SessionLifecycleManager.
