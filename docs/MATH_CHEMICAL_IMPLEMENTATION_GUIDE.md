# Math and Chemical Symbols Implementation Guide

This document provides a step-by-step implementation plan for integrating MathLive, MathJax, and mhchem into MindGraph. Based on a complete code review of the existing system.

---

## Table of Contents

1. [Code Review Summary](#code-review-summary)
2. [Current Architecture](#current-architecture)
3. [Implementation Phases](#implementation-phases)
4. [Phase 1: Add MathJax + mhchem for Rendering](#phase-1-add-mathjax--mhchem-for-rendering)
5. [Phase 2: Modify Node Data Model](#phase-2-modify-node-data-model)
6. [Phase 3: Integrate MathLive Editor](#phase-3-integrate-mathlive-editor)
7. [Phase 4: Modify Renderers](#phase-4-modify-renderers)
8. [Phase 5: Testing and Validation](#phase-5-testing-and-validation)
9. [Risk Assessment](#risk-assessment)

---

## Code Review Summary

### Files Reviewed (Verified Against Actual Codebase)

| File | Lines | Purpose | Changes Needed |
|------|-------|---------|----------------|
| `templates/editor.html` | 1018 | Main HTML template | Add MathJax (line 19-20), MathLive (line 19-20), math-renderer.js (line 892), math-input-popup.js (line 910) |
| `static/js/editor/node-editor.js` | 349 | Modal editor for node text | Add math buttons (line 195), add methods (end of file) |
| `static/js/renderers/shared-utilities.js` | 731 | Text wrapping, measurement | Add renderMathOrText (line 324), add exports (line 657) |
| `static/js/utils/` | 1 file | Utilities folder | Create math-renderer.js (new file) |

### Verified Insertion Points

| Action | File | Exact Line | Before/After |
|--------|------|------------|--------------|
| Add MathJax script | editor.html | 19-20 | After D3.js, before `</head>` |
| Add MathLive script | editor.html | 19-20 | After MathJax, before `</head>` |
| Add math-renderer.js load | editor.html | 892 | After sse-client.js |
| Add math-input-popup.js load | editor.html | 910 | After node-editor.js |
| Add math buttons | node-editor.js | 195 | After charCount, before buttonContainer |
| Add detectLatexAtCursor() | node-editor.js | 341 | Before class closing brace |
| Add openMathPopup() | node-editor.js | 341 | Before class closing brace |
| Add renderMathOrText() | shared-utilities.js | 324 | After renderMultiLineText() |

### Key Code Structures Verified

**node-editor.js structure:**
```
Line 13-20:   class NodeEditor constructor
Line 45-253:  createModal() method - MODIFY (add buttons at line 195)
Line 258-290: attachEventListeners() method
Line 295-321: handleSave() method
Line 326-334: handleCancel() method
Line 339-341: close() method
Line 341:     END OF CLASS - ADD NEW METHODS HERE
```

**shared-utilities.js structure:**
```
Line 302-324: renderMultiLineText() - ADD renderMathOrText() AFTER THIS
Line 655-672: MindGraphUtils export object - ADD new function
Line 679-707: Global window exports - ADD new function
```

### Current Text Input Flow

```
User double-clicks node
    ↓
NodeEditor.show() creates modal with <textarea>
    ↓
User types text → handleSave() trims text
    ↓
InteractiveEditor.updateNodeText() updates spec
    ↓
Operations module emits diagram:node_updated event
    ↓
renderDiagram() re-renders with new text
```

### New Flow with Math/Chemistry Buttons

```
User double-clicks node
    ↓
NodeEditor.show() creates modal with:
  - <textarea> for text input
  - [∑ Math] [⚗ Chemistry] buttons below
    ↓
User clicks [∑ Math] button
    ↓
MathInputPopup opens with MathLive WYSIWYG editor
    ↓
User creates equation → clicks [Insert]
    ↓
LaTeX string ($...$) inserted at cursor in textarea
    ↓
User clicks [Save Changes]
    ↓
Text with embedded LaTeX saved to spec
    ↓
Renderer detects LaTeX → MathJax renders to SVG
```

### Current Text Rendering Flow

```
renderGraph(type, spec, theme, dimensions)
    ↓
Individual renderer (e.g., renderBubbleMap)
    ↓
splitAndWrapText(text, fontSize, maxWidth, measureFn)
    ↓
Multiple SVG <text> elements created
    ↓
Each line rendered with data-line-index attribute
```

---

## Current Architecture

### Key Components

1. **NodeEditor** (`static/js/editor/node-editor.js`)
   - Creates modal with textarea for text input
   - Handles save/cancel with callbacks
   - Line 142-170: Creates the textarea element

2. **Text Rendering** (`static/js/renderers/shared-utilities.js`)
   - `splitAndWrapText()`: Splits text by newlines and wraps
   - `renderMultiLineText()`: Renders multiple SVG text elements
   - `extractTextFromSVG()`: Extracts text from SVG elements

3. **Individual Renderers** (e.g., `bubble-map-renderer.js`)
   - Each renderer calls `splitAndWrapText()` for text wrapping
   - Creates multiple `<text>` elements with `data-line-index`

---

## Implementation Phases

### Overview

```
Phase 1: Add MathJax + mhchem (Rendering only)
    ↓
Phase 2: Modify Node Data Model
    ↓
Phase 3: Integrate MathLive Editor
    ↓
Phase 4: Modify Renderers for Math SVG
    ↓
Phase 5: Testing and Validation
```

---

## Phase 1: Add MathJax + mhchem for Rendering

### Code Review: Verified Insertion Points

| File | Current Line | What's There | Action |
|------|--------------|--------------|--------|
| `templates/editor.html` | 19 | `<script src="/static/js/d3.min.js"></script>` | Add MathJax after this |
| `templates/editor.html` | 20 | `</head>` | MathJax must be before this |
| `templates/editor.html` | 892 | `sse-client.js` load | Add math-renderer.js after |
| `templates/editor.html` | 910 | `node-editor.js` load | Add math-input-popup.js after |

### Step 1.1: Add MathJax Script to editor.html

**File:** `templates/editor.html`

**Location:** Line 19-20 (inside `<head>`, after D3.js, before `</head>`)

**VERIFIED: Current code at lines 18-20:**
```html
    <!-- D3.js -->
    <script src="/static/js/d3.min.js"></script>
</head>
```

**Insert between line 19 and 20:**

```html
<!-- D3.js -->
<script src="/static/js/d3.min.js"></script>

<!-- MathJax with mhchem for Math and Chemistry rendering -->
<script>
MathJax = {
    loader: {
        load: ['[tex]/mhchem']
    },
    tex: {
        packages: {'[+]': ['mhchem']},
        inlineMath: [['$', '$'], ['\\(', '\\)']],
        displayMath: [['$$', '$$'], ['\\[', '\\]']]
    },
    svg: {
        fontCache: 'global',
        scale: 1,
        minScale: 0.5
    },
    startup: {
        ready: () => {
            MathJax.startup.defaultReady();
            console.log('[MindGraph] MathJax with mhchem loaded');
            window.MathJaxReady = true;
            // Dispatch custom event for modules waiting for MathJax
            window.dispatchEvent(new CustomEvent('mathjax:ready'));
        }
    }
};
</script>
<script id="MathJax-script" async 
    src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js">
</script>
```

### Step 1.2: Create Math Rendering Utility

**File:** `static/js/utils/math-renderer.js` (NEW FILE)

```javascript
/**
 * MathRenderer - Utility for rendering LaTeX math to SVG
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司
 */

class MathRenderer {
    constructor() {
        this.ready = false;
        this.pendingRenders = [];
        
        // Wait for MathJax to be ready
        if (window.MathJaxReady) {
            this.ready = true;
        } else {
            window.addEventListener('mathjax:ready', () => {
                this.ready = true;
                this.processPendingRenders();
            });
        }
    }
    
    /**
     * Check if text contains LaTeX math notation
     * @param {string} text - Text to check
     * @returns {boolean} True if contains math
     */
    containsMath(text) {
        if (!text) return false;
        
        // Check for various LaTeX delimiters
        const mathPatterns = [
            /\$[^$]+\$/,           // Inline: $...$
            /\\\([^)]+\\\)/,       // Inline: \(...\)
            /\$\$[^$]+\$\$/,       // Display: $$...$$
            /\\\[[^\]]+\\\]/,      // Display: \[...\]
            /\\ce\{[^}]+\}/,       // mhchem: \ce{...}
            /\\frac\{/,            // Common LaTeX commands
            /\\sqrt\{/,
            /\\sum/,
            /\\int/,
            /\^{[^}]+}/,           // Superscript: ^{...}
            /_{[^}]+}/             // Subscript: _{...}
        ];
        
        return mathPatterns.some(pattern => pattern.test(text));
    }
    
    /**
     * Check if text contains chemical notation
     * @param {string} text - Text to check
     * @returns {boolean} True if contains chemistry
     */
    containsChemistry(text) {
        if (!text) return false;
        
        // Check for mhchem notation
        return /\\ce\{[^}]+\}/.test(text);
    }
    
    /**
     * Render LaTeX to SVG
     * @param {string} latex - LaTeX string to render
     * @returns {Promise<{svg: string, width: number, height: number}>}
     */
    async renderToSVG(latex) {
        if (!this.ready) {
            return new Promise((resolve, reject) => {
                this.pendingRenders.push({ latex, resolve, reject });
            });
        }
        
        try {
            // Wait for MathJax to be fully loaded
            await MathJax.startup.promise;
            
            // Convert LaTeX to SVG
            const node = await MathJax.tex2svgPromise(latex, {
                display: false // inline mode by default
            });
            
            const svg = node.querySelector('svg');
            if (!svg) {
                throw new Error('MathJax did not produce SVG output');
            }
            
            // Get dimensions (MathJax uses ex units, convert to pixels)
            const width = this.exToPixels(svg.getAttribute('width') || '1ex');
            const height = this.exToPixels(svg.getAttribute('height') || '1ex');
            
            // Clean up MathJax container
            MathJax.startup.document.clear();
            
            return {
                svg: svg.outerHTML,
                width: width,
                height: height
            };
        } catch (error) {
            logger.error('MathRenderer', 'Error rendering LaTeX', { latex, error });
            throw error;
        }
    }
    
    /**
     * Convert ex units to pixels (approximate)
     * @param {string} exValue - Value like "2.5ex"
     * @returns {number} Pixel value
     */
    exToPixels(exValue) {
        const match = exValue.match(/([0-9.]+)ex/);
        if (match) {
            // 1ex ≈ 8px (varies by font, but reasonable default)
            return parseFloat(match[1]) * 8;
        }
        return parseFloat(exValue) || 0;
    }
    
    /**
     * Process pending renders after MathJax loads
     */
    processPendingRenders() {
        while (this.pendingRenders.length > 0) {
            const { latex, resolve, reject } = this.pendingRenders.shift();
            this.renderToSVG(latex).then(resolve).catch(reject);
        }
    }
    
    /**
     * Extract plain text from LaTeX for fallback display
     * @param {string} latex - LaTeX string
     * @returns {string} Plain text approximation
     */
    extractPlainText(latex) {
        if (!latex) return '';
        
        return latex
            .replace(/\\\(/g, '')
            .replace(/\\\)/g, '')
            .replace(/\$/g, '')
            .replace(/\\ce\{([^}]+)\}/g, '$1')
            .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '($1/$2)')
            .replace(/\\sqrt\{([^}]+)\}/g, '√($1)')
            .replace(/\^{([^}]+)}/g, '^$1')
            .replace(/_{([^}]+)}/g, '_$1')
            .replace(/\\\w+/g, '');
    }
}

// Create singleton instance
if (typeof window !== 'undefined') {
    window.mathRenderer = new MathRenderer();
    window.MathRenderer = MathRenderer;
}
```

### Step 1.3: Add Script to editor.html

**File:** `templates/editor.html`

**VERIFIED: Current code at lines 891-893:**
```html
    <script src="/static/js/core/session-lifecycle.js"></script>
    <script src="/static/js/utils/sse-client.js"></script>
    
    <script src="/static/js/theme-config.js"></script>
```

**Insert after line 892 (after sse-client.js):**

```html
    <script src="/static/js/utils/sse-client.js"></script>
    
    <!-- Math/Chemistry Rendering Support -->
    <script src="/static/js/utils/math-renderer.js"></script>
    
    <script src="/static/js/theme-config.js"></script>
```

---

## Phase 2: Modify Node Data Model

### Step 2.1: Define Content Types

The node data model will be extended to support content types:

```javascript
// Content types for node text
const CONTENT_TYPES = {
    TEXT: 'text',           // Plain text (default)
    MATH: 'math',           // Mathematical expression (LaTeX)
    CHEMISTRY: 'chemistry', // Chemical formula (mhchem)
    MIXED: 'mixed'          // Contains both text and math
};
```

### Step 2.2: No Spec Changes Required (Backward Compatible)

The spec structure remains the same. Content type is detected automatically from text content using `mathRenderer.containsMath()`.

**Detection Logic:**
```javascript
function detectContentType(text) {
    if (!text) return CONTENT_TYPES.TEXT;
    
    const hasMath = window.mathRenderer?.containsMath(text);
    const hasChemistry = window.mathRenderer?.containsChemistry(text);
    
    if (hasChemistry) return CONTENT_TYPES.CHEMISTRY;
    if (hasMath) return CONTENT_TYPES.MATH;
    return CONTENT_TYPES.TEXT;
}
```

---

## Phase 3: Integrate MathLive Editor

### Design: Buttons Below Textarea

Instead of mode switching, we add two buttons below the textarea:
- **Math (∑)**: Opens MathLive popup for equation input
- **Chemistry (⚗)**: Opens MathLive popup with mhchem template

When user creates an equation in the popup, the LaTeX is inserted at the cursor position in the textarea.

```
┌─────────────────────────────────────┐
│  Edit Node Content                  │
├─────────────────────────────────────┤
│  Text:                              │
│  ┌─────────────────────────────────┐│
│  │ The area of a circle is $A =   ││
│  │ \pi r^2$ where r is the radius ││
│  │                                 ││
│  └─────────────────────────────────┘│
│                                     │
│  [∑ Math]  [⚗ Chemistry]           │
│                                     │
│           [Cancel]  [Save Changes]  │
└─────────────────────────────────────┘
```

### Step 3.1: Add MathLive Script

**File:** `templates/editor.html`

**Location:** After MathJax script, add:

```html
<!-- MathLive for WYSIWYG math input popup -->
<link rel="stylesheet" href="https://unpkg.com/mathlive/dist/mathlive-static.css">
<script defer src="https://unpkg.com/mathlive"></script>
<script>
// Wait for MathLive to load
document.addEventListener('DOMContentLoaded', () => {
    if (typeof MathfieldElement !== 'undefined') {
        console.log('[MindGraph] MathLive loaded');
        window.MathLiveReady = true;
    }
});
</script>
```

### Visual Mockup: MathInputPopup

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌──────┐  Insert Math Equation                             │
│  │  ∑   │                                                   │
│  └──────┘                                                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                                                         ││
│  │     a² + b² = c²                    (MathLive WYSIWYG) ││
│  │                                                         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  Preview:                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                  a² + b² = c²       (MathJax rendered) ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  Quick Insert:                                              │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐  │
│  │ x² │ │ √x │ │ a/b│ │ π  │ │ ∑  │ │ ∫  │ │ ±  │ │ ≠  │  │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘  │
│                                                             │
│                              ┌────────┐  ┌────────────────┐│
│                              │ Cancel │  │     Insert     ││
│                              └────────┘  └────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Step 3.2: Create MathInputPopup Component

**File:** `static/js/editor/math-input-popup.js` (NEW FILE)

```javascript
/**
 * MathInputPopup - Popup for WYSIWYG math/chemistry input using MathLive
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司
 */

class MathInputPopup {
    constructor() {
        this.overlay = null;
        this.mathField = null;
        this.onInsert = null;
        this.mode = 'math'; // 'math' or 'chemistry'
    }
    
    /**
     * Show the math input popup
     * @param {string} mode - 'math' or 'chemistry'
     * @param {Function} onInsert - Callback with LaTeX string when user clicks Insert
     * @param {string} initialValue - Optional initial LaTeX value
     */
    show(mode, onInsert, initialValue = '') {
        this.mode = mode;
        this.onInsert = onInsert;
        
        // Create overlay
        this.overlay = d3.select('body')
            .append('div')
            .attr('class', 'math-input-overlay')
            .style('position', 'fixed')
            .style('top', 0)
            .style('left', 0)
            .style('width', '100%')
            .style('height', '100%')
            .style('background', 'rgba(0, 0, 0, 0.7)')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .style('z-index', 10001) // Above NodeEditor
            .style('backdrop-filter', 'blur(4px)');
        
        // Create popup container
        const popup = this.overlay.append('div')
            .attr('class', 'math-input-popup')
            .style('background', 'white')
            .style('border-radius', '16px')
            .style('padding', '24px')
            .style('min-width', '500px')
            .style('max-width', '700px')
            .style('box-shadow', '0 12px 40px rgba(0, 0, 0, 0.3)');
        
        // Header
        const header = popup.append('div')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('gap', '12px')
            .style('margin-bottom', '20px');
        
        header.append('div')
            .style('width', '40px')
            .style('height', '40px')
            .style('background', mode === 'chemistry' 
                ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                : 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)')
            .style('border-radius', '10px')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .style('font-size', '20px')
            .style('color', 'white')
            .text(mode === 'chemistry' ? '⚗' : '∑');
        
        const lang = window.languageManager;
        header.append('h3')
            .style('margin', 0)
            .style('color', '#1a1a1a')
            .style('font-size', '18px')
            .text(mode === 'chemistry' 
                ? (lang?.translate('insertChemistry') || 'Insert Chemical Formula')
                : (lang?.translate('insertMath') || 'Insert Math Equation'));
        
        // MathLive field container
        const fieldContainer = popup.append('div')
            .style('margin-bottom', '16px');
        
        // Create MathLive element
        this.mathField = document.createElement('math-field');
        this.mathField.style.width = '100%';
        this.mathField.style.fontSize = '24px';
        this.mathField.style.padding = '16px';
        this.mathField.style.border = '2px solid #e2e8f0';
        this.mathField.style.borderRadius = '12px';
        this.mathField.style.minHeight = '80px';
        
        // Set initial value
        if (initialValue) {
            this.mathField.value = initialValue;
        } else if (mode === 'chemistry') {
            // Start with mhchem template
            this.mathField.value = '\\ce{}';
        }
        
        fieldContainer.node().appendChild(this.mathField);
        
        // Focus the math field
        setTimeout(() => {
            this.mathField.focus();
        }, 100);
        
        // Preview section
        const previewSection = popup.append('div')
            .style('margin-bottom', '20px');
        
        previewSection.append('label')
            .style('display', 'block')
            .style('margin-bottom', '8px')
            .style('color', '#6b7280')
            .style('font-size', '13px')
            .style('font-weight', '600')
            .text(lang?.translate('preview') || 'Preview');
        
        const previewContainer = previewSection.append('div')
            .attr('id', 'math-preview')
            .style('padding', '16px')
            .style('background', '#f9fafb')
            .style('border-radius', '8px')
            .style('min-height', '50px')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center');
        
        // Update preview on input
        this.mathField.addEventListener('input', () => {
            this.updatePreview(previewContainer.node());
        });
        
        // Initial preview
        this.updatePreview(previewContainer.node());
        
        // Quick insert buttons for common symbols
        if (mode === 'chemistry') {
            this.addChemistryQuickButtons(popup);
        } else {
            this.addMathQuickButtons(popup);
        }
        
        // Buttons
        const buttonContainer = popup.append('div')
            .style('display', 'flex')
            .style('justify-content', 'flex-end')
            .style('gap', '12px')
            .style('margin-top', '20px');
        
        // Cancel button
        buttonContainer.append('button')
            .style('padding', '10px 20px')
            .style('border', '2px solid #e2e8f0')
            .style('background', 'white')
            .style('color', '#64748b')
            .style('border-radius', '8px')
            .style('cursor', 'pointer')
            .style('font-weight', '600')
            .text(lang?.translate('cancel') || 'Cancel')
            .on('click', () => this.close());
        
        // Insert button
        buttonContainer.append('button')
            .style('padding', '10px 24px')
            .style('border', 'none')
            .style('background', mode === 'chemistry'
                ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                : 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)')
            .style('color', 'white')
            .style('border-radius', '8px')
            .style('cursor', 'pointer')
            .style('font-weight', '600')
            .text(lang?.translate('insert') || 'Insert')
            .on('click', () => this.handleInsert());
        
        // Close on overlay click
        this.overlay.on('click', (event) => {
            if (event.target === this.overlay.node()) {
                this.close();
            }
        });
        
        // Close on Escape
        document.addEventListener('keydown', this.handleKeyDown = (event) => {
            if (event.key === 'Escape') {
                this.close();
            }
        });
    }
    
    /**
     * Add quick insert buttons for math symbols
     */
    addMathQuickButtons(popup) {
        const quickSection = popup.append('div')
            .style('margin-bottom', '16px');
        
        quickSection.append('label')
            .style('display', 'block')
            .style('margin-bottom', '8px')
            .style('color', '#6b7280')
            .style('font-size', '13px')
            .style('font-weight', '600')
            .text('Quick Insert');
        
        const buttons = quickSection.append('div')
            .style('display', 'flex')
            .style('flex-wrap', 'wrap')
            .style('gap', '8px');
        
        const mathSymbols = [
            { label: 'x²', latex: 'x^2' },
            { label: '√x', latex: '\\sqrt{x}' },
            { label: 'a/b', latex: '\\frac{a}{b}' },
            { label: 'π', latex: '\\pi' },
            { label: '∑', latex: '\\sum_{i=1}^{n}' },
            { label: '∫', latex: '\\int_{a}^{b}' },
            { label: '±', latex: '\\pm' },
            { label: '≠', latex: '\\neq' },
            { label: '≤', latex: '\\leq' },
            { label: '≥', latex: '\\geq' },
            { label: '∞', latex: '\\infty' },
            { label: 'θ', latex: '\\theta' }
        ];
        
        mathSymbols.forEach(sym => {
            buttons.append('button')
                .style('padding', '6px 12px')
                .style('border', '1px solid #e2e8f0')
                .style('background', '#f9fafb')
                .style('border-radius', '6px')
                .style('cursor', 'pointer')
                .style('font-size', '14px')
                .text(sym.label)
                .on('click', () => {
                    this.mathField.executeCommand(['insert', sym.latex]);
                    this.mathField.focus();
                });
        });
    }
    
    /**
     * Add quick insert buttons for chemistry symbols
     */
    addChemistryQuickButtons(popup) {
        const quickSection = popup.append('div')
            .style('margin-bottom', '16px');
        
        quickSection.append('label')
            .style('display', 'block')
            .style('margin-bottom', '8px')
            .style('color', '#6b7280')
            .style('font-size', '13px')
            .style('font-weight', '600')
            .text('Common Formulas');
        
        const buttons = quickSection.append('div')
            .style('display', 'flex')
            .style('flex-wrap', 'wrap')
            .style('gap', '8px');
        
        const chemSymbols = [
            { label: 'H₂O', latex: '\\ce{H2O}' },
            { label: 'CO₂', latex: '\\ce{CO2}' },
            { label: 'O₂', latex: '\\ce{O2}' },
            { label: 'NaCl', latex: '\\ce{NaCl}' },
            { label: 'H₂SO₄', latex: '\\ce{H2SO4}' },
            { label: 'NaOH', latex: '\\ce{NaOH}' },
            { label: '→', latex: '\\ce{->}' },
            { label: '⇌', latex: '\\ce{<=>}' },
            { label: '↑', latex: '\\ce{^}' },
            { label: '↓', latex: '\\ce{v}' },
            { label: 'Fe²⁺', latex: '\\ce{Fe^{2+}}' },
            { label: 'Δ', latex: '\\ce{->[\\Delta]}' }
        ];
        
        chemSymbols.forEach(sym => {
            buttons.append('button')
                .style('padding', '6px 12px')
                .style('border', '1px solid #e2e8f0')
                .style('background', '#f9fafb')
                .style('border-radius', '6px')
                .style('cursor', 'pointer')
                .style('font-size', '14px')
                .text(sym.label)
                .on('click', () => {
                    this.mathField.value = sym.latex;
                    this.mathField.focus();
                    this.updatePreview(document.getElementById('math-preview'));
                });
        });
    }
    
    /**
     * Update the preview using MathJax
     */
    async updatePreview(container) {
        const latex = this.mathField.value;
        
        if (!latex || !window.MathJaxReady) {
            container.innerHTML = '<span style="color: #9ca3af;">Enter an equation above</span>';
            return;
        }
        
        try {
            container.innerHTML = '';
            const node = await MathJax.tex2svgPromise(latex);
            container.appendChild(node);
        } catch (error) {
            container.innerHTML = '<span style="color: #ef4444;">Invalid syntax</span>';
        }
    }
    
    /**
     * Handle insert button click
     */
    handleInsert() {
        const latex = this.mathField.value;
        
        if (!latex) {
            this.close();
            return;
        }
        
        // Wrap in $ for inline math
        const wrappedLatex = `$${latex}$`;
        
        if (this.onInsert) {
            this.onInsert(wrappedLatex);
        }
        
        this.close();
    }
    
    /**
     * Close the popup
     */
    close() {
        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }
        
        if (this.handleKeyDown) {
            document.removeEventListener('keydown', this.handleKeyDown);
        }
        
        this.mathField = null;
        this.onInsert = null;
    }
}

// Create singleton instance
if (typeof window !== 'undefined') {
    window.mathInputPopup = new MathInputPopup();
    window.MathInputPopup = MathInputPopup;
}
```

### Visual Mockup: NodeEditor with Insert Buttons

**Insert Mode** (cursor NOT inside equation):
```
┌─────────────────────────────────────────────────────┐
│  ┌──────┐  Edit Node Content                        │
│  │  ✏️  │                                           │
│  └──────┘                                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Text:                                              │
│  ┌─────────────────────────────────────────────────┐│
│  │ The Pythagorean theorem states that|            ││  ← cursor here
│  │ $a^2 + b^2 = c^2$ for right triangles.         ││
│  └─────────────────────────────────────────────────┘│
│                                              45 chars│
│                                                     │
│  ┌─────────────┐  ┌─────────────────┐              │
│  │  ∑  Math    │  │  ⚗  Chemistry   │              │
│  └─────────────┘  └─────────────────┘              │
│                                                     │
│                        ┌────────┐  ┌──────────────┐│
│                        │ Cancel │  │ Save Changes ││
│                        └────────┘  └──────────────┘│
└─────────────────────────────────────────────────────┘
```

**Edit Mode** (cursor INSIDE an existing equation):
```
┌─────────────────────────────────────────────────────┐
│  ┌──────┐  Edit Node Content                        │
│  │  ✏️  │                                           │
│  └──────┘                                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Text:                                              │
│  ┌─────────────────────────────────────────────────┐│
│  │ The Pythagorean theorem states that             ││
│  │ $a^2 + b|^2 = c^2$ for right triangles.        ││  ← cursor inside $...$
│  └─────────────────────────────────────────────────┘│
│                                              45 chars│
│                                                     │
│  ┌───────────────┐  ┌─────────────────┐            │
│  │  ∑  Edit Math │  │  ⚗  Chemistry   │  ← label changes!
│  └───────────────┘  └─────────────────┘            │
│                                                     │
│                        ┌────────┐  ┌──────────────┐│
│                        │ Cancel │  │ Save Changes ││
│                        └────────┘  └──────────────┘│
└─────────────────────────────────────────────────────┘
```

When clicking "Edit Math", the popup opens pre-filled with `a^2 + b^2 = c^2`.

### Step 3.3: Modify NodeEditor to Add Buttons

**File:** `static/js/editor/node-editor.js`

**VERIFIED: Current code at lines 194-201:**
```javascript
            } else {
                charCount.style('color', '#94a3b8').style('font-weight', '500');
            }
        });
        
        // Buttons container   ← Line 196
        const buttonContainer = this.modal.append('div')
            .style('display', 'flex')
            .style('justify-content', 'flex-end')
            .style('gap', '12px')
            .style('margin-top', '28px');
```

**Insert between line 194 (end of character count) and line 196 (buttons container):**

**NOTE:** The `lang` variable is already defined at line 118 in createModal():
```javascript
const lang = window.languageManager;
```

```javascript
// Math and Chemistry insert buttons
const insertButtonsContainer = this.modal.append('div')
    .attr('class', 'math-insert-buttons')
    .style('display', 'flex')
    .style('gap', '10px')
    .style('margin-top', '12px')
    .style('margin-bottom', '8px');

// Math button
insertButtonsContainer.append('button')
    .attr('class', 'btn-insert-math')
    .style('display', 'flex')
    .style('align-items', 'center')
    .style('gap', '6px')
    .style('padding', '8px 14px')
    .style('border', '2px solid #8b5cf6')
    .style('background', 'white')
    .style('color', '#8b5cf6')
    .style('border-radius', '8px')
    .style('cursor', 'pointer')
    .style('font-size', '13px')
    .style('font-weight', '600')
    .style('transition', 'all 0.2s')
    .html('<span style="font-size: 16px;">∑</span> ' + (lang?.translate('math') || 'Math'))
    .on('mouseover', function() {
        d3.select(this)
            .style('background', '#8b5cf6')
            .style('color', 'white');
    })
    .on('mouseout', function() {
        d3.select(this)
            .style('background', 'white')
            .style('color', '#8b5cf6');
    })
    .on('click', () => this.openMathPopup('math'));

// Chemistry button
insertButtonsContainer.append('button')
    .attr('class', 'btn-insert-chemistry')
    .style('display', 'flex')
    .style('align-items', 'center')
    .style('gap', '6px')
    .style('padding', '8px 14px')
    .style('border', '2px solid #10b981')
    .style('background', 'white')
    .style('color', '#10b981')
    .style('border-radius', '8px')
    .style('cursor', 'pointer')
    .style('font-size', '13px')
    .style('font-weight', '600')
    .style('transition', 'all 0.2s')
    .html('<span style="font-size: 16px;">⚗</span> ' + (lang?.translate('chemistry') || 'Chemistry'))
    .on('mouseover', function() {
        d3.select(this)
            .style('background', '#10b981')
            .style('color', 'white');
    })
    .on('mouseout', function() {
        d3.select(this)
            .style('background', 'white')
            .style('color', '#10b981');
    })
    .on('click', () => this.openMathPopup('chemistry'));
```

### Step 3.4: Add openMathPopup Method to NodeEditor (with Re-Edit Support)

**File:** `static/js/editor/node-editor.js`

**VERIFIED: Current code at lines 339-347:**
```javascript
    close() {
        d3.select('.node-editor-overlay').remove();
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.NodeEditor = NodeEditor;
}
```

**Insert new methods before the closing brace of the class (before line 342):**

```javascript
/**
 * Detect if cursor is inside a LaTeX block ($...$) or chemistry block (\ce{...})
 * @returns {Object|null} { start, end, latex, type } or null if not inside
 */
detectLatexAtCursor() {
    const text = this.textInput.value;
    const cursorPos = this.textInput.selectionStart;
    
    // Find all LaTeX blocks in text
    const patterns = [
        { regex: /\$([^$]+)\$/g, type: 'math' },           // $...$
        { regex: /\\\(([^)]+)\\\)/g, type: 'math' },       // \(...\)
        { regex: /\\ce\{([^}]+)\}/g, type: 'chemistry' }   // \ce{...}
    ];
    
    for (const pattern of patterns) {
        let match;
        pattern.regex.lastIndex = 0; // Reset regex state
        
        while ((match = pattern.regex.exec(text)) !== null) {
            const start = match.index;
            const end = match.index + match[0].length;
            
            // Check if cursor is inside this block
            if (cursorPos >= start && cursorPos <= end) {
                return {
                    start: start,
                    end: end,
                    fullMatch: match[0],
                    innerLatex: match[1], // Content inside delimiters
                    type: pattern.type
                };
            }
        }
    }
    
    return null;
}

/**
 * Open MathLive popup for math/chemistry input
 * Supports both inserting new equations and editing existing ones
 * @param {string} mode - 'math' or 'chemistry'
 */
openMathPopup(mode) {
    if (!window.mathInputPopup) {
        logger.warn('NodeEditor', 'MathInputPopup not available');
        return;
    }
    
    // Check if cursor is inside an existing LaTeX block
    const existingBlock = this.detectLatexAtCursor();
    
    if (existingBlock) {
        // EDIT MODE: Re-edit existing equation
        logger.debug('NodeEditor', 'Editing existing equation', existingBlock);
        
        // Use the detected type, not the button clicked
        const editMode = existingBlock.type;
        
        window.mathInputPopup.show(editMode, (newLatex) => {
            // Replace the old LaTeX block with new one
            const currentText = this.textInput.value;
            const before = currentText.substring(0, existingBlock.start);
            const after = currentText.substring(existingBlock.end);
            
            this.textInput.value = before + newLatex + after;
            
            // Position cursor after the new LaTeX
            const newPos = existingBlock.start + newLatex.length;
            this.textInput.selectionStart = newPos;
            this.textInput.selectionEnd = newPos;
            
            // Focus back on textarea
            this.textInput.focus();
            
            // Trigger input event to update character count
            this.textInput.dispatchEvent(new Event('input', { bubbles: true }));
            
            logger.debug('NodeEditor', 'Updated existing equation', { 
                oldLatex: existingBlock.fullMatch, 
                newLatex 
            });
            
        }, existingBlock.innerLatex); // Pre-fill with existing content
        
    } else {
        // INSERT MODE: Add new equation at cursor
        const cursorPos = this.textInput.selectionStart;
        
        window.mathInputPopup.show(mode, (latex) => {
            // Insert LaTeX at cursor position
            const currentText = this.textInput.value;
            const before = currentText.substring(0, cursorPos);
            const after = currentText.substring(cursorPos);
            
            this.textInput.value = before + latex + after;
            
            // Update cursor position to after inserted text
            const newPos = cursorPos + latex.length;
            this.textInput.selectionStart = newPos;
            this.textInput.selectionEnd = newPos;
            
            // Focus back on textarea
            this.textInput.focus();
            
            // Trigger input event to update character count
            this.textInput.dispatchEvent(new Event('input', { bubbles: true }));
            
            logger.debug('NodeEditor', 'Inserted new equation', { mode, latex });
        });
    }
}
```

### Step 3.5: Update Button Labels for Edit Mode

**File:** `static/js/editor/node-editor.js`

**Add cursor position listener to update button labels:**

```javascript
// After creating the textarea, add cursor position listener
d3.select(this.textInput).on('click keyup', () => {
    this.updateMathButtonLabels();
});

/**
 * Update Math/Chemistry button labels based on cursor position
 * Shows "Edit" when cursor is inside an existing equation
 */
updateMathButtonLabels() {
    const existingBlock = this.detectLatexAtCursor();
    const lang = window.languageManager;
    
    const mathBtn = this.modal.select('.btn-insert-math');
    const chemBtn = this.modal.select('.btn-insert-chemistry');
    
    if (existingBlock) {
        if (existingBlock.type === 'math') {
            mathBtn.html('<span style="font-size: 16px;">∑</span> ' + 
                (lang?.translate('editMath') || 'Edit Math'));
            chemBtn.html('<span style="font-size: 16px;">⚗</span> ' + 
                (lang?.translate('chemistry') || 'Chemistry'));
        } else {
            mathBtn.html('<span style="font-size: 16px;">∑</span> ' + 
                (lang?.translate('math') || 'Math'));
            chemBtn.html('<span style="font-size: 16px;">⚗</span> ' + 
                (lang?.translate('editChemistry') || 'Edit Chemistry'));
        }
    } else {
        // Reset to default labels
        mathBtn.html('<span style="font-size: 16px;">∑</span> ' + 
            (lang?.translate('math') || 'Math'));
        chemBtn.html('<span style="font-size: 16px;">⚗</span> ' + 
            (lang?.translate('chemistry') || 'Chemistry'));
    }
}
```

### Step 3.6: Add Script to editor.html

**File:** `templates/editor.html`

**VERIFIED: Current code at lines 909-912:**
```html
    <script src="/static/js/editor/canvas-manager.js"></script>
    <script src="/static/js/editor/node-editor.js"></script>
    <script src="/static/js/editor/diagram-validator.js"></script>
    <script src="/static/js/editor/learning-mode-manager.js"></script>
```

**Insert after line 910 (after node-editor.js):**

```html
    <script src="/static/js/editor/node-editor.js"></script>
    <script src="/static/js/editor/math-input-popup.js"></script>
    <script src="/static/js/editor/diagram-validator.js"></script>
```

---

## Phase 4: Modify Renderers

### Step 4.1: Add Math Rendering to shared-utilities.js

**File:** `static/js/renderers/shared-utilities.js`

**VERIFIED: Current code at lines 322-326:**
```javascript
            }
        });
    });
}

function splitAndWrapText(text, fontSize, maxWidth, measureFn) {
```

**Insert after line 324 (after renderMultiLineText function, before splitAndWrapText):**

```javascript
/**
 * Render text that may contain math/chemistry notation
 * Falls back to plain text if MathJax not available or content is plain text
 * 
 * @param {Object} svg - D3 SVG selection
 * @param {string} text - Text content (may contain LaTeX)
 * @param {number} x - X position (center)
 * @param {number} y - Y position (center)
 * @param {Object} attrs - Attributes to apply
 * @returns {Promise<{width: number, height: number}>} Rendered dimensions
 */
async function renderMathOrText(svg, text, x, y, attrs) {
    // Check if text contains math/chemistry
    const hasMath = window.mathRenderer?.containsMath(text);
    
    if (!hasMath || !window.MathJaxReady) {
        // Fall back to regular text rendering
        const fontSize = attrs?.['font-size'] || 14;
        const lineHeight = Math.round(fontSize * 1.2);
        const maxWidth = attrs?.['max-width'] || 200;
        
        // Use existing text wrapping
        const lines = splitAndWrapText(text, fontSize, maxWidth, (t, fs) => {
            return t.length * fs * 0.6; // Approximate width
        });
        
        const startY = y - (lines.length - 1) * lineHeight / 2;
        renderMultiLineText(svg, lines, x, startY, lineHeight, attrs);
        
        return {
            width: Math.max(...lines.map(l => l.length * fontSize * 0.6)),
            height: lines.length * lineHeight
        };
    }
    
    try {
        // Render math to SVG
        const result = await window.mathRenderer.renderToSVG(text);
        
        // Create a group for the math content
        const mathGroup = svg.append('g')
            .attr('class', 'math-content')
            .attr('transform', `translate(${x - result.width/2}, ${y - result.height/2})`);
        
        // Parse and append the MathJax SVG
        const parser = new DOMParser();
        const mathDoc = parser.parseFromString(result.svg, 'image/svg+xml');
        const mathSvg = mathDoc.documentElement;
        
        // Append the math SVG content
        mathGroup.node().appendChild(mathSvg);
        
        // Apply common attributes
        if (attrs) {
            if (attrs['data-node-id']) {
                mathGroup.attr('data-node-id', attrs['data-node-id']);
            }
            if (attrs['data-node-type']) {
                mathGroup.attr('data-node-type', attrs['data-node-type']);
            }
            if (attrs.cursor) {
                mathGroup.style('cursor', attrs.cursor);
            }
        }
        
        return {
            width: result.width,
            height: result.height
        };
        
    } catch (error) {
        logger.error('SharedUtilities', 'Error rendering math, falling back to text', error);
        
        // Fallback to plain text
        const plainText = window.mathRenderer?.extractPlainText(text) || text;
        svg.append('text')
            .attr('x', x)
            .attr('y', y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .text(plainText);
        
        return { width: plainText.length * 8, height: 16 };
    }
}

```

**Also add to exports (line 657-672 in shared-utilities.js):**

**VERIFIED: Current MindGraphUtils object:**
```javascript
    window.MindGraphUtils = {
        getMeasurementContainer,
        getTextRadius,
        cleanupMeasurementContainer,
        getWatermarkText,
        addWatermark,
        getColorScale,
        getThemeDefaults,
        createSVG,
        centerContent,
        wrapText,
        splitAndWrapText,
        splitTextLines,
        extractTextFromSVG,
        knockoutTextForLearningSheet
    };
```

**Add `renderMathOrText` to this list.**

**Also add global exposure (around line 705):**
```javascript
    if (typeof window.renderMathOrText === 'undefined') {
        window.renderMathOrText = renderMathOrText;
    }
```

### Step 4.2: Modify Individual Renderers

Each renderer needs to check for math content and use `renderMathOrText` instead of regular text rendering.

**Example modification for `bubble-map-renderer.js`:**

**Before (lines 289-313):**
```javascript
// Render attribute text - use multiple text elements
const attrText = node.text || '';
const attrLines = splitAndWrapText(attrText, ...);
// ... multiple text elements
```

**After:**
```javascript
// Render attribute text - check for math content
const attrText = node.text || '';

// Check if this is math/chemistry content
if (window.mathRenderer?.containsMath(attrText)) {
    // Use async rendering for math
    renderMathOrText(svg, attrText, node.x, node.y, {
        'data-text-for': `attribute_${node.id}`,
        'data-node-id': `attribute_${node.id}`,
        'data-node-type': 'attribute',
        'cursor': 'pointer',
        'fill': THEME.attributeText
    });
} else {
    // Regular text rendering (existing code)
    const attrLines = splitAndWrapText(attrText, ...);
    // ... existing code
}
```

### Step 4.3: Handle Async Rendering

Since math rendering is async, renderers need to handle this:

**Option A: Render synchronously, update async**
```javascript
// First render placeholder, then update with math
const placeholder = svg.append('text')
    .attr('x', x)
    .attr('y', y)
    .attr('opacity', 0.5)
    .text('Loading...');

renderMathOrText(svg, mathText, x, y, attrs).then(() => {
    placeholder.remove();
});
```

**Option B: Pre-render all math before diagram** (Recommended)
```javascript
// In renderGraph(), pre-process math content
async function preprocessMathContent(spec) {
    const mathNodes = [];
    
    // Collect all math content from spec
    // ... traverse spec and find math content
    
    // Pre-render all math in parallel
    const results = await Promise.all(
        mathNodes.map(node => 
            window.mathRenderer.renderToSVG(node.text)
        )
    );
    
    // Cache results in spec for synchronous access
    mathNodes.forEach((node, i) => {
        node._renderedMath = results[i];
    });
    
    return spec;
}
```

---

## Phase 5: Testing and Validation

### Step 5.1: Test Cases

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Plain text | "Hello World" | Regular text rendering |
| Simple math | "$x^2 + y^2$" | Rendered equation |
| Chemistry | "$\\ce{H2O}$" | H₂O with subscripts |
| Mixed content | "Water is $\\ce{H2O}$" | Text with inline formula |
| Complex equation | "$\\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$" | Quadratic formula |
| Invalid LaTeX | "$\\invalid{" | Graceful fallback to text |

### Step 5.2: Browser Compatibility

| Browser | MathJax | MathLive | Notes |
|---------|---------|----------|-------|
| Chrome 90+ | ✅ | ✅ | Full support |
| Firefox 90+ | ✅ | ✅ | Full support |
| Safari 14+ | ✅ | ✅ | Full support |
| Edge 90+ | ✅ | ✅ | Full support |
| Mobile Safari | ✅ | ⚠️ | Virtual keyboard may overlap |
| Mobile Chrome | ✅ | ✅ | Works with virtual keyboard |

### Step 5.3: Export Validation

- PNG export: Math SVG should rasterize correctly
- SVG export: Math SVG should be embedded inline
- .mg file: LaTeX source should be preserved in spec

---

## Risk Assessment

### Low Risk (Safe to Implement)

| Change | Risk | Mitigation |
|--------|------|------------|
| Add MathJax script | Low | Loads async, doesn't block |
| Add math-renderer.js | Low | New file, no existing code modified |
| Content type detection | Low | Auto-detect, backward compatible |

### Medium Risk (Careful Implementation)

| Change | Risk | Mitigation |
|--------|------|------------|
| Modify NodeEditor | Medium | Add mode toggle without changing existing textarea |
| Modify renderers | Medium | Use fallback to existing text rendering if math fails |
| Async rendering | Medium | Pre-render math before diagram to maintain sync flow |

### High Risk (Requires Thorough Testing)

| Change | Risk | Mitigation |
|--------|------|------------|
| Export functionality | High | Test PNG/SVG export with math content |
| Interactive editing | High | Ensure math nodes can still be selected/edited |
| Mobile support | High | Test MathLive virtual keyboard on mobile |

---

## Implementation Order

### Week 1: Foundation
1. Add MathJax + mhchem scripts to editor.html
2. Create math-renderer.js utility
3. Test basic math rendering in browser console

### Week 2: Rendering
1. Add renderMathOrText() to shared-utilities.js
2. Modify one renderer (bubble-map) as proof of concept
3. Test rendering with math content

### Week 3: Input
1. Add MathLive script
2. Modify NodeEditor for mode toggle
3. Test math input and save

### Week 4: Integration
1. Modify remaining renderers
2. Test export functionality
3. Mobile testing

### Week 5: Polish
1. Fix edge cases
2. Add loading indicators
3. Documentation

---

## Quick Reference: LaTeX Syntax

### Math Examples
```latex
$x^2 + y^2 = z^2$           // Pythagorean theorem
$\frac{a}{b}$               // Fraction
$\sqrt{x}$                  // Square root
$\sum_{i=1}^{n} x_i$        // Summation
$\int_0^1 f(x) dx$          // Integral
```

### Chemistry Examples (mhchem)
```latex
$\ce{H2O}$                  // Water
$\ce{CO2}$                  // Carbon dioxide
$\ce{H2SO4}$                // Sulfuric acid
$\ce{2H2 + O2 -> 2H2O}$     // Reaction equation
$\ce{Fe^{2+}}$              // Iron ion
$\ce{CaCO3 v}$              // Precipitate (with arrow)
```

---

## File Change Summary

| File | Action | Exact Location | Lines Changed (Est.) |
|------|--------|----------------|---------------------|
| `templates/editor.html` | Modify | Lines 19-20, 892, 910 | +45 lines |
| `static/js/utils/math-renderer.js` | Create | New file | ~150 lines |
| `static/js/editor/math-input-popup.js` | Create | New file | ~350 lines |
| `static/js/editor/node-editor.js` | Modify | Lines 195, 339-341 | +120 lines |
| `static/js/renderers/shared-utilities.js` | Modify | Lines 324, 657, 705 | +70 lines |
| `static/js/renderers/*.js` (12 files) | Modify | Text rendering sections | ~20 lines each |

**Total estimated changes:** ~975 lines of code

---

## Pre-Implementation Verification Checklist

Before implementing, verify these files exist and match expected structure:

- [ ] `templates/editor.html` - Line 19 has D3.js script
- [ ] `static/js/editor/node-editor.js` - Line 342 has class closing brace `}`
- [ ] `static/js/renderers/shared-utilities.js` - Line 324 ends renderMultiLineText()
- [ ] `static/js/utils/` directory exists (currently has only sse-client.js)

**Run this command to verify line counts:**
```bash
wc -l templates/editor.html static/js/editor/node-editor.js static/js/renderers/shared-utilities.js
```

Expected output:
```
 1018 templates/editor.html
  349 static/js/editor/node-editor.js
  731 static/js/renderers/shared-utilities.js
```

---

## References

- MathJax Documentation: https://docs.mathjax.org/
- mhchem Documentation: https://mhchem.github.io/MathJax-mhchem/
- MathLive Documentation: https://cortexjs.io/mathlive/

