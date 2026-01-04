/**
 * SSE Client - Server-Sent Events client with proper incremental rendering
 * 
 * Uses recursive promise chain instead of blocking while loop.
 * This allows browser to repaint between chunks for smooth incremental display.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class SSEClient {
    constructor(eventBus, logger) {
        this.eventBus = eventBus;
        this.logger = logger || console;
        this.activeStreams = new Map(); // Track active streams for cleanup
    }
    
    /**
     * Start SSE stream with callbacks
     * 
     * @param {string} url - API endpoint URL
     * @param {object} requestData - Request payload
     * @param {object} callbacks - Callback functions
     * @param {Function} callbacks.onChunk - Called for each SSE chunk
     * @param {Function} callbacks.onComplete - Called when stream completes
     * @param {Function} callbacks.onError - Called on error
     * @param {AbortController} abortController - Optional abort controller for cancellation
     * @returns {Promise} Resolves when stream completes
     */
    async start(url, requestData, callbacks, abortController = null) {
        const streamId = `${url}_${Date.now()}`;
        const startTime = performance.now();
        
        this.logger.debug('SSEClient', `Starting stream: ${url}`, {
            streamId,
            requestData: this._sanitizeLogData(requestData)
        });
        
        // Track this stream
        this.activeStreams.set(streamId, {
            url,
            startTime,
            abortController
        });
        
        // Emit event
        if (this.eventBus) {
            this.eventBus.emit('sse:stream_started', {
                streamId,
                url
            });
        }
        
        try {
            const response = await auth.fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData),
                signal: abortController?.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let chunkCount = 0;
            
            // Recursive promise chain (allows browser repaints)
            const readChunk = () => {
                return reader.read().then(({ done, value }) => {
                    if (done) {
                        // Stream complete
                        const duration = performance.now() - startTime;
                        this.logger.info('SSEClient', `Stream completed: ${url}`, {
                            streamId,
                            duration: `${duration.toFixed(2)}ms`,
                            chunks: chunkCount
                        });
                        
                        if (this.eventBus) {
                            this.eventBus.emit('sse:stream_completed', {
                                streamId,
                                url,
                                duration,
                                chunks: chunkCount
                            });
                        }
                        
                        this.activeStreams.delete(streamId);
                        
                        if (callbacks.onComplete) {
                            callbacks.onComplete();
                        }
                        
                        return;
                    }
                    
                    // Decode chunk
                    const chunk = decoder.decode(value, { stream: true });
                    buffer += chunk;
                    
                    // Split by newlines
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || ''; // Keep incomplete line in buffer
                    
                    // Process complete lines
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                chunkCount++;
                                
                                if (callbacks.onChunk) {
                                    callbacks.onChunk(data);
                                }
                                
                                if (this.eventBus) {
                                    this.eventBus.emit('sse:chunk_received', {
                                        streamId,
                                        url,
                                        data
                                    });
                                }
                            } catch (e) {
                                this.logger.debug('SSEClient', 'Skipping malformed JSON in stream', {
                                    line
                                });
                            }
                        }
                    }
                    
                    // Continue reading (returns to event loop - KEY FIX!)
                    return readChunk();
                });
            };
            
            // Start reading
            return await readChunk();
            
        } catch (error) {
            const duration = performance.now() - startTime;
            
            // Don't log as error if it was intentionally aborted
            if (error.name === 'AbortError') {
                this.logger.info('SSEClient', `Stream aborted: ${url}`, {
                    streamId,
                    duration: `${duration.toFixed(2)}ms`
                });
                
                if (this.eventBus) {
                    this.eventBus.emit('sse:stream_aborted', {
                        streamId,
                        url,
                        duration
                    });
                }
            } else {
                this.logger.error('SSEClient', `Stream error: ${url}`, {
                    streamId,
                    error: error.message,
                    stack: error.stack,
                    duration: `${duration.toFixed(2)}ms`
                });
                
                if (this.eventBus) {
                    this.eventBus.emit('sse:stream_error', {
                        streamId,
                        url,
                        error: error.message,
                        duration
                    });
                }
            }
            
            this.activeStreams.delete(streamId);
            
            if (callbacks.onError) {
                callbacks.onError(error);
            }
            
            throw error;
        }
    }
    
    /**
     * Abort all active streams
     */
    abortAll() {
        this.logger.info('SSEClient', `Aborting ${this.activeStreams.size} active streams`);
        
        this.activeStreams.forEach((stream, streamId) => {
            if (stream.abortController) {
                stream.abortController.abort();
            }
        });
        
        this.activeStreams.clear();
    }
    
    /**
     * Get active stream count
     */
    getActiveStreamCount() {
        return this.activeStreams.size;
    }
    
    /**
     * Sanitize data for logging
     */
    _sanitizeLogData(data) {
        if (data === null || data === undefined) return data;
        
        try {
            const jsonStr = JSON.stringify(data);
            if (jsonStr.length > 300) {
                return jsonStr.substring(0, 300) + '...(truncated)';
            }
            return JSON.parse(jsonStr);
        } catch (e) {
            return '[Circular reference or non-serializable object]';
        }
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    // Wait for dependencies
    const initSSEClient = () => {
        if (window.eventBus && window.logger) {
            window.sseClient = new SSEClient(window.eventBus, window.logger);
            
            if (window.logger?.debugMode) {
                console.log('%c[SSEClient] SSE Client initialized', 'color: #ff9800; font-weight: bold;');
            }
        } else {
            setTimeout(initSSEClient, 50);
        }
    };
    
    initSSEClient();
}

