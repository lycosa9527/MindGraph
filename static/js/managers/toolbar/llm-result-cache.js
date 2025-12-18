/**
 * LLM Result Cache Manager
 * ========================
 * 
 * Handles caching and retrieval of LLM generation results.
 * Provides TTL-based validation to ensure cache freshness.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class LLMResultCache {
    constructor(logger, options = {}) {
        this.logger = logger || console;
        this.results = {};
        this.timestamps = {};
        
        // Configuration
        this.ttlMs = options.ttlMs || 10 * 60 * 1000; // 10 minutes default
        this.maxResults = options.maxResults || 5; // Max 5 models (qwen, deepseek, kimi, hunyuan, doubao)
        
        this.logger.debug('LLMResultCache', 'Cache initialized', {
            ttlMs: this.ttlMs,
            maxResults: this.maxResults
        });
    }
    
    /**
     * Store a result in cache
     */
    store(modelName, result) {
        if (!modelName) {
            this.logger.warn('LLMResultCache', 'Cannot store result - no model name provided');
            return false;
        }
        
        this.results[modelName] = result;
        this.timestamps[modelName] = Date.now();
        
        this.logger.debug('LLMResultCache', `Result cached for ${modelName}`, {
            hasSpec: !!result.result?.spec,
            success: result.success
        });
        
        return true;
    }
    
    /**
     * Retrieve a result from cache if valid
     */
    retrieve(modelName) {
        if (!this.results[modelName]) {
            return null;
        }
        
        // Check TTL
        if (!this._isResultValid(modelName)) {
            this.logger.debug('LLMResultCache', `Cache expired for ${modelName}`);
            delete this.results[modelName];
            delete this.timestamps[modelName];
            return null;
        }
        
        return this.results[modelName];
    }
    
    /**
     * Get all cached models that have results
     */
    getCachedModels() {
        return Object.keys(this.results).filter(modelName => this._isResultValid(modelName));
    }
    
    /**
     * Get cached result for specific model
     */
    getResult(modelName) {
        return this.retrieve(modelName);
    }
    
    /**
     * Check if all models have cached results
     */
    hasAllResults(models) {
        return models.every(model => this.getResult(model) !== null);
    }
    
    /**
     * Clear all cached results
     */
    clear() {
        const count = Object.keys(this.results).length;
        this.results = {};
        this.timestamps = {};
        
        this.logger.debug('LLMResultCache', 'Cache cleared', {
            itemsCleared: count
        });
    }
    
    /**
     * Clear results for specific model
     */
    clearModel(modelName) {
        if (this.results[modelName]) {
            delete this.results[modelName];
            delete this.timestamps[modelName];
            this.logger.debug('LLMResultCache', `Cache cleared for ${modelName}`);
            return true;
        }
        return false;
    }
    
    /**
     * Get all results (for analysis)
     */
    getAllResults() {
        return { ...this.results };
    }
    
    /**
     * Get cache statistics
     */
    getStats() {
        return {
            cachedModels: Object.keys(this.results),
            validResults: this.getCachedModels().length,
            totalCapacity: this.maxResults
        };
    }
    
    /**
     * PRIVATE: Check if result is still valid (within TTL)
     */
    _isResultValid(modelName) {
        if (!this.timestamps[modelName]) {
            return false;
        }
        
        const age = Date.now() - this.timestamps[modelName];
        return age < this.ttlMs;
    }
}
