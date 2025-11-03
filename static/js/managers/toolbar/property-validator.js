/**
 * Property Validator
 * ==================
 * 
 * Validates LLM-generated diagram specifications against schema requirements.
 * Handles all 12 diagram types with specific field validation.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class PropertyValidator {
    constructor(logger) {
        this.logger = logger || console;
        
        this.logger.debug('PropertyValidator', 'Property validator initialized');
    }
    
    /**
     * Validate LLM spec against diagram type requirements
     */
    validateLLMSpec(model, spec, expectedDiagramType) {
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
     * Analyze consistency across multiple LLM results
     */
    analyzeConsistency(llmResults, logger = null) {
        const analyzeLogger = logger || this.logger;
        
        const successful = Object.entries(llmResults)
            .filter(([_, result]) => result.success)
            .map(([model, result]) => ({ model, ...result }));
        
        if (successful.length < 2) {
            return {
                modelsAnalyzed: successful.length,
                hasConsistencyIssues: false,
                inconsistencies: []
            };
        }
        
        analyzeLogger.info('PropertyValidator', '=== LLM CONSISTENCY ANALYSIS ===', {
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
        
        analyzeLogger.info('PropertyValidator', 'Spec comparison across models:', specComparison);
        
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
                analyzeLogger.warn('PropertyValidator', '⚠️ LLM INCONSISTENCIES DETECTED', {
                    timestamp: new Date().toISOString(),
                    inconsistencyCount: inconsistencies.length,
                    inconsistencies: inconsistencies
                });
            } else {
                // Only content count variance - this is normal, use INFO
                analyzeLogger.info('PropertyValidator', 'ℹ️ LLM content variance (normal)', {
                    timestamp: new Date().toISOString(),
                    varianceCount: inconsistencies.length,
                    variances: inconsistencies
                });
            }
        } else {
            analyzeLogger.info('PropertyValidator', '✓ All LLM results are consistent', {
                timestamp: new Date().toISOString(),
                modelsCompared: successful.length
            });
        }
        
        return {
            modelsAnalyzed: successful.length,
            hasConsistencyIssues: inconsistencies.length > 0,
            inconsistencies: inconsistencies,
            specComparison: specComparison
        };
    }
}
