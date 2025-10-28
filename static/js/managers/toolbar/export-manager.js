/**
 * Export Manager
 * ==============
 * 
 * Manages diagram export to PNG, SVG, and JSON formats.
 * Handles file download and export preparation.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 * @size_target ~400-500 lines
 */

class ExportManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Export configuration
        this.exportFormats = ['png', 'svg', 'json'];
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
        this.eventBus.on('toolbar:export_requested', (data) => {
            this.handleExport(data.format, data.editor);
        });
        
        this.logger.debug('ExportManager', 'Subscribed to events');
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
            this.logger.error('ExportManager', `Export failed: ${error.message}`);
            this.eventBus.emit('export:error', { 
                format, 
                error: error.message 
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
     * @param {SVGElement} svg - SVG element
     * @param {Object} editor - Editor instance
     * @returns {Promise<Object>} Export result
     */
    async performPNGExport(svg, editor) {
        return new Promise((resolve, reject) => {
            try {
                // Clone SVG for export (preserve original)
                const svgClone = svg.cloneNode(true);
                
                // Use viewBox dimensions for accurate export
                const viewBox = svgClone.getAttribute('viewBox');
                let width, height, viewBoxX = 0, viewBoxY = 0;
                
                if (viewBox) {
                    // viewBox format: "minX minY width height"
                    const viewBoxParts = viewBox.split(' ').map(Number);
                    viewBoxX = viewBoxParts[0];
                    viewBoxY = viewBoxParts[1];
                    width = viewBoxParts[2];
                    height = viewBoxParts[3];
                } else {
                    // Fallback to getBoundingClientRect
                    const rect = svg.getBoundingClientRect();
                    width = rect.width;
                    height = rect.height;
                }
                
                // Add watermark to clone
                const svgD3 = d3.select(svgClone);
                const watermarkFontSize = Math.max(12, Math.min(20, Math.min(width, height) * 0.025));
                const wmPadding = Math.max(10, Math.min(20, Math.min(width, height) * 0.02));
                const watermarkX = viewBoxX + width - wmPadding;
                const watermarkY = viewBoxY + height - wmPadding;
                
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
                
                // Use 3x scale for Retina displays
                const scale = 3;
                
                // Create high-quality canvas
                const canvas = document.createElement('canvas');
                canvas.width = width * scale;
                canvas.height = height * scale;
                const ctx = canvas.getContext('2d');
                
                ctx.scale(scale, scale);
                ctx.imageSmoothingEnabled = true;
                ctx.imageSmoothingQuality = 'high';
                
                // Fill white background
                ctx.fillStyle = 'white';
                ctx.fillRect(0, 0, width, height);
                
                // Convert SVG to PNG
                const svgData = new XMLSerializer().serializeToString(svgClone);
                const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
                const url = URL.createObjectURL(svgBlob);
                
                const img = new Image();
                img.onload = () => {
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    canvas.toBlob((blob) => {
                        const pngUrl = URL.createObjectURL(blob);
                        
                        // Generate filename
                        const filename = this.generateFilename(editor, 'png');
                        
                        // Download file
                        this.downloadFile(pngUrl, filename, 'image/png');
                        
                        URL.revokeObjectURL(pngUrl);
                        URL.revokeObjectURL(url);
                        
                        this.logger.info('ExportManager', 'PNG export successful', { filename });
                        
                        resolve({
                            success: true,
                            filename,
                            format: 'png'
                        });
                    }, 'image/png');
                };
                
                img.onerror = (error) => {
                    this.logger.error('ExportManager', 'Error loading SVG', error);
                    URL.revokeObjectURL(url);
                    
                    reject({
                        success: false,
                        error: 'Failed to load SVG for export'
                    });
                };
                
                img.src = url;
                
            } catch (error) {
                this.logger.error('ExportManager', 'Error exporting to PNG', error);
                reject({
                    success: false,
                    error: error.message
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
            this.logger.error('ExportManager', 'Error exporting to SVG', error);
            return {
                success: false,
                error: error.message
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
            this.logger.error('ExportManager', 'Error exporting to JSON', error);
            return {
                success: false,
                error: error.message
            };
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
     * Cleanup resources
     */
    destroy() {
        this.logger.info('ExportManager', 'Destroying Export Manager');
        // Event Bus will handle cleanup
    }
}

// Make available globally
window.ExportManager = ExportManager;

