/**
 * LLM Engine Manager
 * ==================
 * 
 * Handles API calls to LLM services and SSE stream processing.
 * Manages the multi-model generation flow with error handling and validation.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class LLMEngineManager {
    constructor(llmValidationManager, propertyValidator, logger) {
        this.llmValidationManager = llmValidationManager;
        this.propertyValidator = propertyValidator;
        this.logger = logger || console;
        this.activeAbortControllers = new Set();
        
        this.logger.debug('LLMEngineManager', 'LLM Engine Manager initialized');
    }
    
    /**
     * Call LLM API with a specific model
     * Returns a promise that resolves when the request completes
     */
    async callLLMWithModel(model, requestBody, { onSuccess, onError }) {
        const abortController = new AbortController();
        this.activeAbortControllers.add(abortController);
        
        // Track if this request was intentionally cancelled
        let wasCancelled = false;
        
        // Listen for abort to mark as cancelled
        abortController.signal.addEventListener('abort', () => {
            wasCancelled = true;
        }, { once: true });
        
        const startTime = Date.now();
        const modelName = model;
        
        try {
            // Create request body with model specified
            // CRITICAL: Backend expects 'llm' parameter, not 'model'
            const modelRequestBody = {
                ...requestBody,
                llm: modelName  // Backend parameter name is 'llm'
            };
            
            this.logger.debug('LLMEngineManager', `Starting API call for ${modelName}`, {
                model: modelName,
                requestBody: modelRequestBody
            });
            
            const response = await window.auth.fetch('/api/generate_graph', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(modelRequestBody),
                signal: abortController.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Parse regular JSON response
            const data = await response.json();
            
            // Remove abort controller
            this.activeAbortControllers.delete(abortController);
            
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
            
            this.logger.info('LLMEngineManager', `=== RESPONSE FROM ${modelName.toUpperCase()} ===`, {
                timestamp: new Date().toISOString(),
                model: modelName,
                hasData: !!data,
                dataKeys: data ? Object.keys(data) : [],
                success: data.success,
                elapsed: elapsed + 's'
            });
            
            if (data.success) {
                // Validate spec
                const specValidation = this.propertyValidator.validateLLMSpec(
                    modelName, 
                    data.spec, 
                    requestBody.diagram_type
                );
                
                // Log validation details
                if (specValidation && !specValidation.isValid) {
                    this.logger.warn('LLMEngineManager', `⚠️ ${modelName.toUpperCase()} SPEC VALIDATION WARNINGS`, {
                        model: modelName,
                        issues: specValidation.issues,
                        missingFields: specValidation.missingFields,
                        invalidFields: specValidation.invalidFields
                    });
                }
                
                // Normalize diagram type
                let responseDiagramType = data.diagram_type || requestBody.diagram_type;
                if (responseDiagramType === 'mind_map') {
                    responseDiagramType = 'mindmap';
                }
                
                const result = {
                    model: modelName,
                    success: true,
                    result: {
                        spec: data.spec,
                        diagram_type: responseDiagramType,
                        topics: data.topics || [],
                        style_preferences: data.style_preferences || {}
                    },
                    validation: specValidation,
                    elapsed: elapsed
                };
                
                if (onSuccess) {
                    onSuccess(result);
                }
                
                return result;
            } else {
                // Model failed
                const errorMessage = data.error || 'Unknown error';
                const isAuthError = errorMessage.includes('401') || errorMessage.includes('Unauthorized');
                const isNetworkError = errorMessage.includes('network') || errorMessage.includes('NetworkError');
                
                this.logger.error('LLMEngineManager', `=== LLM FAILURE: ${modelName.toUpperCase()} ===`, {
                    timestamp: new Date().toISOString(),
                    model: modelName,
                    error: errorMessage,
                    elapsed: elapsed + 's',
                    isAuthError,
                    isNetworkError
                });
                
                const result = {
                    model: modelName,
                    success: false,
                    error: errorMessage,
                    elapsed: elapsed
                };
                
                if (onError) {
                    onError(result);
                }
                
                return result;
            }
        } catch (error) {
            // Don't log AbortError as error - it's expected during cancellation
            // Check multiple ways to detect abort errors across different browsers/contexts
            const isAbortError = 
                wasCancelled || // Intentional cancellation via our abort controller
                error.name === 'AbortError' ||
                error.name === 'DOMException' ||
                (error.message && (
                    error.message.includes('aborted') ||
                    error.message.includes('signal is aborted') ||
                    error.message.includes('The operation was aborted') ||
                    error.message.includes('The user aborted a request')
                )) ||
                (error.code === 20); // DOMException.ABORT_ERR = 20
            
            if (isAbortError) {
                // Silently handle cancellation - don't log as error
                // Only log at debug level, and only if debug mode is enabled
                this.logger.debug('LLMEngineManager', `Request cancelled for ${modelName}`, {
                    model: modelName,
                    reason: 'User navigation or explicit cancellation'
                });
            } else {
                const errorMsg = error?.message || String(error) || 'Unknown API error';
                const isAuthError = errorMsg.includes('401') || errorMsg.includes('Unauthorized') || 
                                  error?.status === 401;
                const isNetworkError = error?.name === 'NetworkError' || error?.name === 'TypeError' ||
                                     errorMsg.includes('network') || errorMsg.includes('fetch');
                
                this.logger.error('LLMEngineManager', `API error for ${modelName}: ${errorMsg}`, {
                    model: modelName,
                    error: errorMsg,
                    status: error?.status,
                    name: error?.name,
                    stack: error?.stack,
                    isAuthError,
                    isNetworkError
                });
            }
            
            this.activeAbortControllers.delete(abortController);
            
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
            const errorMsg = error?.message || String(error) || 'Unknown error';
            const result = {
                model: modelName,
                success: false,
                error: errorMsg,
                elapsed: elapsed
            };
            
            if (onError) {
                onError(result);
            }
            
            return result;
        }
    }
    
    /**
     * Run parallel API calls for multiple models
     */
    async callMultipleModels(models, requestBody, callbacks = {}) {
        const {
            onEachSuccess,
            onEachError,
            onComplete,
            onProgress
        } = callbacks;
        
        this.logger.info('LLMEngineManager', '=== STARTING MULTI-MODEL LLM GENERATION ===', {
            timestamp: new Date().toISOString(),
            models: models,
            prompt: requestBody.prompt,
            context: {
                diagramType: requestBody.diagram_type,
                language: requestBody.language
            }
        });
        
        const promises = models.map(model =>
            this.callLLMWithModel(model, requestBody, {
                onSuccess: (result) => {
                    if (onEachSuccess) onEachSuccess(result);
                    if (onProgress) onProgress('success', model);
                },
                onError: (result) => {
                    if (onEachError) onEachError(result);
                    if (onProgress) onProgress('error', model);
                }
            })
        );
        
        // Wait for all requests to complete
        const results = await Promise.allSettled(promises);
        
        // Extract actual results
        const llmResults = {};
        results.forEach((result, index) => {
            if (result.status === 'fulfilled') {
                const model = models[index];
                llmResults[model] = result.value;
            } else {
                const model = models[index];
                llmResults[model] = {
                    model: model,
                    success: false,
                    error: result.reason?.message || 'Unknown error'
                };
            }
        });
        
        const totalElapsed = results.reduce((sum, result) => {
            if (result.status === 'fulfilled' && result.value.elapsed) {
                return sum + parseFloat(result.value.elapsed);
            }
            return sum;
        }, 0).toFixed(2);
        
        this.logger.info('LLMEngineManager', '=== ALL MODELS COMPLETED ===', {
            timestamp: new Date().toISOString(),
            totalDuration: totalElapsed + 's',
            results: Object.keys(llmResults).map(mdl => ({
                model: mdl,
                success: llmResults[mdl].success,
                hasSpec: !!llmResults[mdl].result?.spec
            }))
        });
        
        if (onComplete) {
            onComplete(llmResults);
        }
        
        return llmResults;
    }
    
    /**
     * Cancel all in-progress requests
     */
    cancelAllRequests() {
        this.logger.debug('LLMEngineManager', 'Cancelling all active requests', {
            activeCount: this.activeAbortControllers.size
        });
        
        this.activeAbortControllers.forEach(controller => {
            controller.abort();
        });
        this.activeAbortControllers.clear();
    }
    
    /**
     * Get active request count
     */
    getActiveRequestCount() {
        return this.activeAbortControllers.size;
    }
    
    /**
     * Check if any requests are active
     */
    hasActiveRequests() {
        return this.activeAbortControllers.size > 0;
    }
}
