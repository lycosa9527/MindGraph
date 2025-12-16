/**
 * Export Manager
 * ==============
 * 
 * Manages diagram export to PNG, SVG, and JSON formats.
 * Handles file download and export preparation.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class ExportManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Owner ID for Event Bus Listener Registry
        this.ownerId = 'ExportManager';
        
        // Export configuration
        this.exportFormats = ['png', 'svg', 'json', 'mg'];
        this.defaultFilename = 'diagram';
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('ExportManager', 'Export Manager initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for export requests
        this.eventBus.onWithOwner('toolbar:export_requested', (data) => {
            this.handleExport(data.format, data.editor);
        }, this.ownerId);
        
        // Listen for import file data (from ToolbarManager)
        this.eventBus.onWithOwner('toolbar:import_file', (data) => {
            this.handleImportData(data.data, data.filename);
        }, this.ownerId);
        
        this.logger.debug('ExportManager', 'Subscribed to events with owner tracking');
    }
    
    /**
     * Handle export request
     * @param {string} format - Export format (png, svg, json)
     * @param {Object} editor - Editor instance
     */
    async handleExport(format, editor) {
        if (!this.exportFormats.includes(format)) {
            this.logger.error('ExportManager', `Invalid export format: ${format}`);
            this.eventBus.emit('export:error', { 
                format, 
                error: 'Invalid format' 
            });
            return;
        }
        
        if (!editor || !editor.currentSpec) {
            this.logger.error('ExportManager', 'No editor or diagram data available');
            this.eventBus.emit('export:error', { 
                format, 
                error: 'No diagram data' 
            });
            return;
        }
        
        this.logger.info('ExportManager', `Starting ${format.toUpperCase()} export`);
        this.eventBus.emit('export:started', { format });
        
        try {
            let result;
            
            switch(format) {
                case 'png':
                    result = await this.exportToPNG(editor);
                    break;
                case 'svg':
                    result = await this.exportToSVG(editor);
                    break;
                case 'json':
                    result = await this.exportToJSON(editor);
                    break;
                case 'mg':
                    result = await this.exportToMG(editor);
                    break;
            }
            
            if (result.success) {
                this.logger.info('ExportManager', `${format.toUpperCase()} export completed`, {
                    filename: result.filename
                });
                this.eventBus.emit('export:completed', { 
                    format, 
                    filename: result.filename 
                });
            } else {
                throw new Error(result.error || 'Export failed');
            }
            
        } catch (error) {
            // Log detailed error information
            const errorDetails = {
                format,
                message: error.message,
                stack: error.stack,
                name: error.name
            };
            this.logger.error('ExportManager', `Export failed: ${error.message}`, errorDetails);
            this.eventBus.emit('export:error', { 
                format, 
                error: error.message,
                details: errorDetails
            });
        }
    }
    
    /**
     * Export diagram to PNG
     * @param {Object} editor - Editor instance
     * @returns {Promise<Object>} Export result
     */
    async exportToPNG(editor) {
        return new Promise((resolve, reject) => {
            const svg = document.querySelector('#d3-container svg');
            if (!svg) {
                this.logger.error('ExportManager', 'No SVG found for export');
                resolve({
                    success: false,
                    error: 'No diagram to export'
                });
                return;
            }
            
            // Fit diagram for export (ensures full diagram is captured)
            if (editor && typeof editor.fitDiagramForExport === 'function') {
                editor.fitDiagramForExport();
                
                // Wait briefly for viewBox update
                setTimeout(() => {
                    this.performPNGExport(svg, editor).then(resolve).catch(reject);
                }, 100);
            } else {
                // Export immediately if fit method not available
                this.logger.warn('ExportManager', 'fitDiagramForExport not available, exporting with current view');
                this.performPNGExport(svg, editor).then(resolve).catch(reject);
            }
        });
    }
    
    /**
     * Perform the actual PNG export
     * @private
     * @param {SVGElement} svg - SVG element (original, for measuring)
     * @param {Object} editor - Editor instance
     * @returns {Promise<Object>} Export result
     */
    async performPNGExport(svg, editor) {
        return new Promise((resolve, reject) => {
            try {
                // STEP 1: Calculate accurate content bounds from ORIGINAL SVG (before cloning)
                // Using original SVG ensures getBBox works correctly (element is in DOM)
                let contentMinX = Infinity, contentMinY = Infinity;
                let contentMaxX = -Infinity, contentMaxY = -Infinity;
                let hasContent = false;
                let maxStrokeWidth = 0;
                
                const allElements = d3.select(svg).selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
                allElements.each(function() {
                    try {
                        const bbox = this.getBBox();
                        if (bbox.width > 0 && bbox.height > 0) {
                            // Get stroke width to account for visual extent beyond getBBox
                            // getBBox() returns geometric bounds, not including stroke
                            const strokeWidth = parseFloat(d3.select(this).attr('stroke-width')) || 0;
                            const strokeOffset = strokeWidth / 2;
                            
                            contentMinX = Math.min(contentMinX, bbox.x - strokeOffset);
                            contentMinY = Math.min(contentMinY, bbox.y - strokeOffset);
                            contentMaxX = Math.max(contentMaxX, bbox.x + bbox.width + strokeOffset);
                            contentMaxY = Math.max(contentMaxY, bbox.y + bbox.height + strokeOffset);
                            hasContent = true;
                            
                            // Track max stroke width for additional safety margin
                            if (strokeWidth > maxStrokeWidth) {
                                maxStrokeWidth = strokeWidth;
                            }
                        }
                    } catch (e) {
                        // Skip elements without getBBox
                    }
                });
                
                if (!hasContent) {
                    this.logger.warn('ExportManager', 'No content found for PNG export');
                    resolve({ success: false, error: 'No content to export' });
                    return;
                }
                
                // STEP 1b: Secondary check - use SVG's current viewBox as reference
                // This ensures we don't miss content that the renderer already calculated
                const currentViewBox = svg.getAttribute('viewBox');
                if (currentViewBox) {
                    const vbParts = currentViewBox.split(' ').map(Number);
                    if (vbParts.length === 4) {
                        const [vbX, vbY, vbWidth, vbHeight] = vbParts;
                        // Expand bounds to include viewBox if it's larger
                        contentMinX = Math.min(contentMinX, vbX);
                        contentMinY = Math.min(contentMinY, vbY);
                        contentMaxX = Math.max(contentMaxX, vbX + vbWidth);
                        contentMaxY = Math.max(contentMaxY, vbY + vbHeight);
                    }
                }
                
                // STEP 2: Clone SVG for export (preserve original)
                const svgClone = svg.cloneNode(true);
                
                // Remove UI-only elements that should not appear in exports
                this.removeExportExcludedElements(svgClone);
                
                // STEP 3: Calculate optimal viewBox with proper padding
                // Add padding around the actual content (not viewBox-relative)
                // Base padding + additional safety margin for strokes and text rendering
                const basePadding = 40; // Increased from 30 for better margins
                const strokeSafetyMargin = Math.ceil(maxStrokeWidth);
                const padding = basePadding + strokeSafetyMargin;
                const exportViewBoxX = contentMinX - padding;
                const exportViewBoxY = contentMinY - padding;
                const exportWidth = (contentMaxX - contentMinX) + (padding * 2);
                const exportHeight = (contentMaxY - contentMinY) + (padding * 2);
                
                this.logger.debug('ExportManager', 'Export dimensions calculated', {
                    contentBounds: { contentMinX, contentMinY, contentMaxX, contentMaxY },
                    exportViewBox: { x: exportViewBoxX, y: exportViewBoxY, width: exportWidth, height: exportHeight }
                });
                
                // STEP 4: Normalize viewBox to start at (0, 0) for canvas compatibility
                // Canvas.drawImage doesn't handle viewBox offsets, so we translate content
                const normalizedWidth = exportWidth;
                const normalizedHeight = exportHeight;
                
                // Wrap all content in a group with translation to normalize coordinates
                const content = Array.from(svgClone.childNodes);
                const contentGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                contentGroup.setAttribute('transform', `translate(${-exportViewBoxX}, ${-exportViewBoxY})`);
                
                // Move all element nodes to the group
                content.forEach(child => {
                    if (child.nodeType === 1) { // Element node
                        contentGroup.appendChild(child);
                    }
                });
                
                // Clear SVG and rebuild with proper structure
                svgClone.innerHTML = '';
                
                // Add background rect FIRST (underneath everything)
                const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                bgRect.setAttribute('x', '0');
                bgRect.setAttribute('y', '0');
                bgRect.setAttribute('width', normalizedWidth);
                bgRect.setAttribute('height', normalizedHeight);
                bgRect.setAttribute('fill', '#f5f5f5');
                bgRect.setAttribute('class', 'export-background');
                svgClone.appendChild(bgRect);
                
                // Add content group
                svgClone.appendChild(contentGroup);
                
                // Update viewBox and dimensions
                svgClone.setAttribute('viewBox', `0 0 ${normalizedWidth} ${normalizedHeight}`);
                svgClone.setAttribute('width', normalizedWidth);
                svgClone.setAttribute('height', normalizedHeight);
                
                // STEP 5: Add watermark (positioned in normalized coordinates)
                const svgD3 = d3.select(svgClone);
                const watermarkFontSize = Math.max(12, Math.min(20, Math.min(normalizedWidth, normalizedHeight) * 0.025));
                const wmPadding = Math.max(10, Math.min(20, Math.min(normalizedWidth, normalizedHeight) * 0.02));
                const watermarkX = normalizedWidth - wmPadding;
                const watermarkY = normalizedHeight - wmPadding;
                
                svgD3.append('text')
                    .attr('x', watermarkX)
                    .attr('y', watermarkY)
                    .attr('text-anchor', 'end')
                    .attr('dominant-baseline', 'alphabetic')
                    .attr('fill', '#2c3e50')
                    .attr('font-size', watermarkFontSize)
                    .attr('font-family', 'Inter, Segoe UI, sans-serif')
                    .attr('font-weight', '600')
                    .attr('opacity', 0.8)
                    .text('MindGraph');
                
                // STEP 6: Create high-quality canvas (3x scale for Retina displays)
                const scale = 3;
                const canvas = document.createElement('canvas');
                canvas.width = normalizedWidth * scale;
                canvas.height = normalizedHeight * scale;
                const ctx = canvas.getContext('2d');
                
                ctx.scale(scale, scale);
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';
                
                // Fill white background (fallback in case SVG background fails)
                ctx.fillStyle = 'white';
                ctx.fillRect(0, 0, normalizedWidth, normalizedHeight);
                
                // STEP 7: Convert SVG to PNG
                const svgData = new XMLSerializer().serializeToString(svgClone);
                const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
                const url = URL.createObjectURL(svgBlob);
                
                const img = new Image();
                img.onload = () => {
                    ctx.drawImage(img, 0, 0, normalizedWidth, normalizedHeight);
                    
                    canvas.toBlob((blob) => {
                        const pngUrl = URL.createObjectURL(blob);
                        
                        // Generate filename
                        const filename = this.generateFilename(editor, 'png');
                        
                        // Download file
                        this.downloadFile(pngUrl, filename, 'image/png');
                        
                        URL.revokeObjectURL(pngUrl);
                        URL.revokeObjectURL(url);
                        
                        this.logger.info('ExportManager', 'PNG export successful', { 
                            filename,
                            dimensions: { width: normalizedWidth, height: normalizedHeight }
                        });
                        
                        resolve({
                            success: true,
                            filename,
                            format: 'png'
                        });
                    }, 'image/png');
                };
                
                img.onerror = (error) => {
                    const errorMsg = error?.message || 'Unknown error loading SVG';
                    this.logger.error('ExportManager', `Error loading SVG: ${errorMsg}`, {
                        error: errorMsg,
                        url: url.substring(0, 100) + '...',
                        format: 'png'
                    });
                    URL.revokeObjectURL(url);
                    
                    reject({
                        success: false,
                        error: `Failed to load SVG for PNG export: ${errorMsg}`
                    });
                };
                
                img.src = url;
                
            } catch (error) {
                const errorMsg = error?.message || 'Unknown error';
                this.logger.error('ExportManager', `Error exporting to PNG: ${errorMsg}`, {
                    error: errorMsg,
                    stack: error?.stack,
                    name: error?.name,
                    format: 'png'
                });
                reject({
                    success: false,
                    error: `PNG export failed: ${errorMsg}`
                });
            }
        });
    }
    
    /**
     * Export diagram to SVG
     * @param {Object} editor - Editor instance
     * @returns {Promise<Object>} Export result
     */
    async exportToSVG(editor) {
        try {
            const svg = document.querySelector('#d3-container svg');
            if (!svg) {
                this.logger.error('ExportManager', 'No SVG found for export');
                return {
                    success: false,
                    error: 'No diagram to export'
                };
            }
            
            // Clone SVG for export
            const svgClone = svg.cloneNode(true);
            
            // Remove UI-only elements that should not appear in exports
            this.removeExportExcludedElements(svgClone);
            
            // Add watermark
            const viewBox = svgClone.getAttribute('viewBox');
            if (viewBox) {
                const viewBoxParts = viewBox.split(' ').map(Number);
                const width = viewBoxParts[2];
                const height = viewBoxParts[3];
                const viewBoxX = viewBoxParts[0];
                const viewBoxY = viewBoxParts[1];
                
                const svgD3 = d3.select(svgClone);
                const watermarkFontSize = Math.max(12, Math.min(20, Math.min(width, height) * 0.025));
                const wmPadding = Math.max(10, Math.min(20, Math.min(width, height) * 0.02));
                
                svgD3.append('text')
                    .attr('x', viewBoxX + width - wmPadding)
                    .attr('y', viewBoxY + height - wmPadding)
                    .attr('text-anchor', 'end')
                    .attr('dominant-baseline', 'alphabetic')
                    .attr('fill', '#2c3e50')
                    .attr('font-size', watermarkFontSize)
                    .attr('font-family', 'Inter, Segoe UI, sans-serif')
                    .attr('font-weight', '600')
                    .attr('opacity', 0.8)
                    .text('MindGraph');
            }
            
            // Serialize SVG
            const svgData = new XMLSerializer().serializeToString(svgClone);
            
            // Create blob and download
            const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            
            const filename = this.generateFilename(editor, 'svg');
            this.downloadFile(url, filename, 'image/svg+xml');
            
            URL.revokeObjectURL(url);
            
            this.logger.info('ExportManager', 'SVG export successful', { filename });
            
            return {
                success: true,
                filename,
                format: 'svg'
            };
            
        } catch (error) {
            const errorMsg = error?.message || 'Unknown error';
            this.logger.error('ExportManager', `Error exporting to SVG: ${errorMsg}`, {
                error: errorMsg,
                stack: error?.stack,
                name: error?.name,
                format: 'svg'
            });
            return {
                success: false,
                error: `SVG export failed: ${errorMsg}`
            };
        }
    }
    
    /**
     * Export diagram to JSON
     * @param {Object} editor - Editor instance
     * @returns {Promise<Object>} Export result
     */
    async exportToJSON(editor) {
        try {
            if (!editor || !editor.currentSpec) {
                this.logger.error('ExportManager', 'No diagram data available');
                return {
                    success: false,
                    error: 'No diagram data to export'
                };
            }
            
            // Prepare export data
            const exportData = {
                version: '1.0',
                exportedAt: new Date().toISOString(),
                diagramType: editor.diagramType,
                sessionId: editor.sessionId,
                spec: editor.currentSpec,
                metadata: {
                    selectedLLM: window.toolbarManager?.selectedLLM || 'unknown',
                    language: window.languageManager?.getCurrentLanguage() || 'en'
                }
            };
            
            // Convert to JSON string
            const jsonString = JSON.stringify(exportData, null, 2);
            
            // Create blob and download
            const blob = new Blob([jsonString], { type: 'application/json;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            
            const filename = this.generateFilename(editor, 'json');
            this.downloadFile(url, filename, 'application/json');
            
            URL.revokeObjectURL(url);
            
            this.logger.info('ExportManager', 'JSON export successful', { 
                filename,
                specSize: JSON.stringify(editor.currentSpec).length
            });
            
            return {
                success: true,
                filename,
                format: 'json'
            };
            
        } catch (error) {
            const errorMsg = error?.message || 'Unknown error';
            this.logger.error('ExportManager', `Error exporting to JSON: ${errorMsg}`, {
                error: errorMsg,
                stack: error?.stack,
                name: error?.name,
                format: 'json'
            });
            return {
                success: false,
                error: `JSON export failed: ${errorMsg}`
            };
        }
    }
    
    /**
     * Export diagram to MindGraph .mg format
     * Includes diagram data, style, and metadata for full restoration
     * @param {Object} editor - Editor instance
     * @returns {Promise<Object>} Export result
     */
    async exportToMG(editor) {
        try {
            if (!editor || !editor.currentSpec) {
                this.logger.error('ExportManager', 'No diagram data available');
                return {
                    success: false,
                    error: 'No diagram data to export'
                };
            }
            
            const diagramType = editor.diagramType;
            
            // Get current theme/style from styleManager
            const currentTheme = window.styleManager?.getDefaultTheme(diagramType) || {};
            
            // Extract style information
            const styleData = {
                theme: 'default',
                colors: {
                    topicFill: currentTheme.topicFill || currentTheme.centralTopicFill,
                    topicText: currentTheme.topicText || currentTheme.centralTopicText,
                    attributeFill: currentTheme.attributeFill || currentTheme.branchFill,
                    attributeText: currentTheme.attributeText || currentTheme.branchText,
                    background: currentTheme.background || '#f5f5f5'
                },
                fonts: {
                    primary: 'Inter, Segoe UI, sans-serif',
                    topicSize: currentTheme.fontTopic || 18,
                    attributeSize: currentTheme.fontAttribute || currentTheme.fontBranch || 14
                }
            };
            
            // Build metadata
            const metadata = {
                app_version: window.MINDGRAPH_VERSION || 'unknown',
                language: window.languageManager?.getCurrentLanguage() || 'en',
                source_llm: window.toolbarManager?.selectedLLM || 'unknown',
                title: null,
                description: null,
                author: null
            };
            
            // Prepare .mg file data
            const mgData = {
                mindgraph: {
                    version: '1.0',
                    format: 'mg'
                },
                created_at: new Date().toISOString(),
                diagram_type: diagramType,
                spec: editor.currentSpec,
                style: styleData,
                metadata: metadata
            };
            
            // Convert to JSON string (pretty printed for readability)
            const jsonString = JSON.stringify(mgData, null, 2);
            
            // Create blob for download
            const blob = new Blob([jsonString], { type: 'application/octet-stream' });
            
            const suggestedFilename = this.generateFilename(editor, 'mg');
            
            // Use Save As picker if available
            const result = await this.downloadFileWithPicker(
                blob,
                suggestedFilename,
                'mg',
                'application/octet-stream',
                'MindGraph Diagram'
            );
            
            // Handle cancelled save
            if (result.cancelled) {
                this.logger.debug('ExportManager', 'MG export cancelled by user');
                return {
                    success: false,
                    cancelled: true
                };
            }
            
            const filename = result.filename;
            
            this.logger.info('ExportManager', 'MG export successful', { 
                filename,
                diagramType: diagramType,
                usedPicker: result.usedPicker
            });
            
            this.eventBus.emit('file:mg_export_completed', { filename });
            
            return {
                success: true,
                filename,
                format: 'mg'
            };
            
        } catch (error) {
            const errorMsg = error?.message || 'Unknown error';
            this.logger.error('ExportManager', `Error exporting to MG: ${errorMsg}`, {
                error: errorMsg,
                stack: error?.stack,
                name: error?.name,
                format: 'mg'
            });
            this.eventBus.emit('file:mg_export_error', { error: errorMsg });
            return {
                success: false,
                error: `MG export failed: ${errorMsg}`
            };
        }
    }
    
    /**
     * Handle import data from ToolbarManager
     * @param {Object} data - Parsed .mg file data
     * @param {string} filename - Original filename
     */
    async handleImportData(data, filename) {
        this.logger.info('ExportManager', 'Processing import data', { filename });
        
        this.eventBus.emit('file:mg_import_started', { filename });
        
        try {
            // Validate file structure
            const validation = this.validateMGFile(data);
            if (!validation.valid) {
                throw new Error(validation.error);
            }
            
            // Migrate if needed (backward compatibility)
            let processedData = data;
            if (validation.needsMigration) {
                processedData = this.migrateMGFile(data);
                this.logger.info('ExportManager', 'Migrated old file format', {
                    fromVersion: data.mindgraph?.version
                });
            }
            
            // Apply imported diagram
            await this.applyImportedDiagram(processedData);
            
            this.logger.info('ExportManager', 'MG import successful', {
                diagramType: processedData.diagram_type
            });
            
            this.eventBus.emit('file:mg_import_completed', {
                filename,
                diagramType: processedData.diagram_type
            });
            
            // Show success notification
            this.eventBus.emit('notification:show', {
                message: window.languageManager?.getNotification('importSuccess') || 'Diagram imported successfully!',
                type: 'success'
            });
            
        } catch (error) {
            this.logger.error('ExportManager', 'Error importing MG file', error);
            this.eventBus.emit('file:mg_import_error', { error: error.message });
            
            // Show user-friendly error notification
            this.eventBus.emit('notification:show', {
                message: `${window.languageManager?.getNotification('importFailed') || 'Import failed'}: ${error.message}`,
                type: 'error'
            });
        }
    }
    
    /**
     * Validate .mg file structure
     * @param {Object} data - Parsed file data
     * @returns {Object} Validation result { valid: boolean, error?: string, needsMigration?: boolean }
     */
    validateMGFile(data) {
        // Check mindgraph header (required)
        if (!data.mindgraph || !data.mindgraph.format) {
            return { valid: false, error: 'Invalid file format: missing MindGraph header' };
        }
        
        if (data.mindgraph.format !== 'mg') {
            return { valid: false, error: 'Invalid file format: not a .mg file' };
        }
        
        // Version check - accept older versions, reject future versions
        const version = data.mindgraph.version || '1.0';
        const currentVersion = '1.0';
        const [major] = version.split('.').map(Number);
        const [currentMajor] = currentVersion.split('.').map(Number);
        
        if (major > currentMajor) {
            return { 
                valid: false, 
                error: `File version ${version} is newer than supported. Please update MindGraph.` 
            };
        }
        
        // Check required fields
        if (!data.diagram_type) {
            return { valid: false, error: 'Invalid file: missing diagram_type' };
        }
        
        if (!data.spec) {
            return { valid: false, error: 'Invalid file: missing diagram data' };
        }
        
        // Check diagram type is supported
        const validTypes = [
            'bubble_map', 'double_bubble_map', 'circle_map', 'tree_map',
            'brace_map', 'flow_map', 'multi_flow_map', 'bridge_map',
            'concept_map', 'mindmap', 'mind_map',
            'factor_analysis', 'three_position_analysis', 'perspective_analysis',
            'goal_analysis', 'possibility_analysis', 'result_analysis',
            'five_w_one_h', 'whwm_analysis', 'four_quadrant'
        ];
        
        if (!validTypes.includes(data.diagram_type)) {
            return { 
                valid: false, 
                error: `Unsupported diagram type: ${data.diagram_type}` 
            };
        }
        
        // Style and metadata are optional - just log warnings if malformed
        if (data.style && typeof data.style !== 'object') {
            console.warn('Invalid style section in .mg file, will use defaults');
        }
        
        if (data.metadata && typeof data.metadata !== 'object') {
            console.warn('Invalid metadata section in .mg file, ignoring');
        }
        
        return { valid: true, needsMigration: version !== currentVersion };
    }
    
    /**
     * Migrate old .mg file format to current version
     * @param {Object} data - Parsed .mg file data
     * @returns {Object} Migrated data in current format
     */
    migrateMGFile(data) {
        const version = data.mindgraph?.version || '1.0';
        let migrated = { ...data };
        
        // Apply defaults for missing optional fields
        const defaults = {
            style: { theme: 'default', colors: null, fonts: null },
            metadata: {
                app_version: 'unknown',
                language: 'en',
                source_llm: 'unknown',
                author: null,
                title: null,
                description: null
            },
            created_at: new Date().toISOString()
        };
        
        // Merge with defaults
        migrated.style = { ...defaults.style, ...(migrated.style || {}) };
        migrated.metadata = { ...defaults.metadata, ...(migrated.metadata || {}) };
        migrated.created_at = migrated.created_at || defaults.created_at;
        
        // Future migrations would go here:
        // if (version === '1.0') { /* migrate to 1.1 */ }
        
        this.logger.debug('ExportManager', 'File migration complete', {
            fromVersion: version,
            toVersion: '1.0'
        });
        
        return migrated;
    }
    
    /**
     * Apply imported diagram data
     * @param {Object} data - Validated .mg file data
     */
    async applyImportedDiagram(data) {
        const diagramType = data.diagram_type;
        const spec = data.spec;
        const style = data.style;
        
        // Get diagram selector reference
        const diagramSelector = window.diagramSelector;
        if (!diagramSelector) {
            throw new Error('Diagram selector not initialized');
        }
        
        // If already in editor mode, go back to gallery first
        if (diagramSelector.editorActive) {
            await diagramSelector.backToGallery();
            // Small delay to ensure cleanup
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        // Get diagram config for name
        const diagramConfig = diagramSelector.diagramTypes[diagramType];
        if (!diagramConfig) {
            throw new Error(`Unknown diagram type: ${diagramType}`);
        }
        
        // Apply saved style to styleManager before rendering (if valid style data exists)
        if (style && typeof style === 'object' && window.styleManager) {
            this.applyImportedStyle(diagramType, style);
        }
        
        // Use existing transition flow with imported spec
        diagramSelector.transitionToEditor(diagramType, spec, diagramConfig.name);
        
        this.logger.info('ExportManager', 'Imported diagram applied', {
            diagramType,
            specKeys: Object.keys(spec),
            hasStyle: !!style
        });
    }
    
    /**
     * Apply imported style to styleManager
     * @param {string} diagramType - Type of diagram
     * @param {Object} style - Style data from .mg file
     */
    applyImportedStyle(diagramType, style) {
        if (!window.styleManager || !style) return;
        
        try {
            // Get a copy of the default theme to modify
            const currentTheme = { ...window.styleManager.getDefaultTheme(diagramType) };
            
            if (style.colors) {
                // Map generic color names to diagram-specific names
                const colorMapping = {
                    topicFill: ['topicFill', 'centralTopicFill'],
                    topicText: ['topicText', 'centralTopicText'],
                    attributeFill: ['attributeFill', 'branchFill'],
                    attributeText: ['attributeText', 'branchText'],
                    background: ['background']
                };
                
                Object.entries(style.colors).forEach(([key, value]) => {
                    if (value && colorMapping[key]) {
                        colorMapping[key].forEach(themeKey => {
                            if (currentTheme.hasOwnProperty(themeKey)) {
                                currentTheme[themeKey] = value;
                            }
                        });
                    }
                });
            }
            
            if (style.fonts) {
                if (style.fonts.topicSize) currentTheme.fontTopic = style.fonts.topicSize;
                if (style.fonts.attributeSize) {
                    currentTheme.fontAttribute = style.fonts.attributeSize;
                    currentTheme.fontBranch = style.fonts.attributeSize;
                }
            }
            
            // Store imported theme for use during render
            if (window.styleManager.setImportedTheme) {
                window.styleManager.setImportedTheme(diagramType, currentTheme);
            }
            
            this.logger.debug('ExportManager', 'Applied imported style', {
                diagramType,
                colorCount: Object.keys(style.colors || {}).length
            });
            
        } catch (error) {
            this.logger.warn('ExportManager', 'Failed to apply imported style, using defaults', error);
            // Non-fatal: continue with default styles
        }
    }
    
    /**
     * Download file to user's computer
     * @param {string} url - File URL (data URL or blob URL)
     * @param {string} filename - File name
     * @param {string} mimeType - MIME type
     */
    downloadFile(url, filename, mimeType) {
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        
        this.logger.debug('ExportManager', 'File download initiated', { 
            filename, 
            mimeType 
        });
    }
    
    /**
     * Download file with Save As picker dialog (File System Access API)
     * Falls back to simple download if API is not supported
     * @param {Blob} blob - File blob
     * @param {string} suggestedName - Suggested filename
     * @param {string} extension - File extension (e.g., 'mg', 'json')
     * @param {string} mimeType - MIME type
     * @param {string} description - File type description for the picker
     * @returns {Promise<Object>} Result with success status and filename
     */
    async downloadFileWithPicker(blob, suggestedName, extension, mimeType, description) {
        // Check if File System Access API is supported
        if (typeof window.showSaveFilePicker === 'function') {
            try {
                const fileHandle = await window.showSaveFilePicker({
                    suggestedName: suggestedName,
                    types: [{
                        description: description,
                        accept: {
                            [mimeType]: [`.${extension}`]
                        }
                    }]
                });
                
                const writable = await fileHandle.createWritable();
                await writable.write(blob);
                await writable.close();
                
                const savedFilename = fileHandle.name;
                this.logger.info('ExportManager', 'File saved via picker', { 
                    filename: savedFilename
                });
                
                return { success: true, filename: savedFilename, usedPicker: true };
                
            } catch (error) {
                // User cancelled the picker
                if (error.name === 'AbortError') {
                    this.logger.debug('ExportManager', 'Save picker cancelled by user');
                    return { success: false, cancelled: true };
                }
                // NotAllowedError is expected in some contexts (async, iframes, etc.)
                // Fall through to fallback silently
                if (error.name === 'NotAllowedError') {
                    this.logger.debug('ExportManager', 'Save picker not allowed in this context, using fallback');
                } else {
                    // Other unexpected error - log as warning
                    this.logger.warn('ExportManager', 'Save picker failed, using fallback', error);
                }
            }
        }
        
        // Fallback: use simple download
        const url = URL.createObjectURL(blob);
        this.downloadFile(url, suggestedName, mimeType);
        URL.revokeObjectURL(url);
        
        return { success: true, filename: suggestedName, usedPicker: false };
    }
    
    /**
     * Sanitize filename to remove invalid characters
     * @param {string} filename - Original filename
     * @returns {string} Sanitized filename
     */
    sanitizeFilename(filename) {
        return filename
            .replace(/[^a-z0-9_\-\.]/gi, '_')
            .replace(/_{2,}/g, '_')
            .toLowerCase();
    }
    
    /**
     * Generate filename based on diagram type and LLM model
     * Format: {diagram_type}_{llm_model}_{timestamp}.{extension}
     * Example: bubble_map_qwen_2025-10-27T12-30-45.png
     * 
     * @param {Object} editor - Editor instance
     * @param {string} extension - File extension
     * @returns {string} Generated filename
     */
    generateFilename(editor, extension) {
        const diagramType = editor.diagramType || 'diagram';
        
        // Get selected LLM model (from toolbar manager or state)
        const state = this.stateManager.getState();
        const llmModel = state.diagram?.selectedLLM || window.toolbarManager?.selectedLLM || 'qwen';
        
        // Generate ISO timestamp (replace : and . with -)
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        
        const filename = `${diagramType}_${llmModel}_${timestamp}.${extension}`;
        
        this.logger.debug('ExportManager', 'Generated filename', {
            diagramType,
            llmModel,
            extension,
            filename
        });
        
        return filename;
    }
    
    /**
     * Remove UI-only elements that should not appear in exports
     * @param {SVGElement} svgClone - Cloned SVG element
     */
    removeExportExcludedElements(svgClone) {
        if (!svgClone) return;
        
        const svgD3 = d3.select(svgClone);
        
        // Remove learning sheet answer key text (should not appear in exports)
        svgD3.selectAll('.learning-sheet-answer-key').remove();
        
        // Remove selection highlights (class="selected" with stroke modifications)
        // These are UI-only and should not appear in exports
        svgD3.selectAll('.selected').each(function() {
            const element = d3.select(this);
            // Remove selection styling but keep the element
            element.classed('selected', false);
            // Remove selection-specific attributes if they exist
            element.style('filter', null);
        });
        
        // Ensure background rectangles don't have visible strokes
        // Background rectangles should only provide fill color, not borders
        svgD3.selectAll('.background, .background-rect').each(function() {
            const element = d3.select(this);
            // Ensure no stroke is visible
            const stroke = element.attr('stroke');
            if (stroke && stroke !== 'none' && stroke !== 'transparent') {
                element.attr('stroke', 'none');
            }
            // Also check style attribute
            const styleStroke = element.style('stroke');
            if (styleStroke && styleStroke !== 'none' && styleStroke !== 'transparent') {
                element.style('stroke', 'none');
            }
        });
        
        this.logger.debug('ExportManager', 'Removed export-excluded elements');
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        this.logger.info('ExportManager', 'Destroying Export Manager');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('ExportManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
    }
}

// Make available globally
window.ExportManager = ExportManager;

