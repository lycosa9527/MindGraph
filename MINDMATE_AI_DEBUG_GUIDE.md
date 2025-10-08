# MindMate AI Panel - Debug Guide

## Quick Test Steps

1. **Open the Application**
   - Navigate to http://localhost:5000 (or your configured port)
   - Click on any diagram type to enter the editor

2. **Check Browser Console**
   - Open Developer Tools (F12)
   - Go to the Console tab
   - Look for these initialization messages:
     ```
     AI Assistant: Initializing...
     AI Assistant Elements: {panel: true, toggleBtn: true, mindmateBtn: true, ...}
     Bound event to MindMate AI button
     ```

3. **Click the MindMate AI Button**
   - Look for the purple gradient button in the top-right toolbar that says "MindMate AI"
   - Click it
   - Check the console for debug messages:
     ```
     MindMate AI button clicked
     Toggle panel called
     Panel collapsed state after toggle: false
     Opening AI panel
     ```

## Manual Testing (If Button Doesn't Work)

If clicking the button doesn't work, you can manually test the panel using the browser console:

### Test 1: Check if AI Assistant is initialized
```javascript
console.log(window.aiAssistant);
```
Expected: Should show the AIAssistantManager object, not undefined

### Test 2: Manually open the panel
```javascript
window.openMindMatePanel();
```
Expected: Panel should slide in from the right side

### Test 3: Toggle the panel
```javascript
window.testMindMatePanel();
```
Expected: Panel should toggle open/closed with detailed debug logs

### Test 4: Manually close the panel
```javascript
window.closeMindMatePanel();
```
Expected: Panel should slide out to the right

## Common Issues and Solutions

### Issue 1: "AI Assistant panel not found"
**Problem**: The panel element doesn't exist in the DOM
**Solution**: Make sure you're in the editor view, not the gallery view

### Issue 2: Button click doesn't trigger anything
**Problem**: Event listener not attached
**Solution**: Refresh the page and check console for initialization errors

### Issue 3: Panel appears but immediately disappears
**Problem**: CSS transition or z-index issue
**Check**: 
```javascript
let panel = document.getElementById('ai-assistant-panel');
console.log('Display:', panel.style.display);
console.log('Classes:', panel.className);
console.log('Computed style:', window.getComputedStyle(panel).transform);
```

### Issue 4: Panel doesn't slide in smoothly
**Problem**: CSS transition not working
**Check**: Make sure the panel has the class `ai-assistant-panel` and the transition is defined in CSS

## What's New (Fixes Applied)

1. ✅ Fixed DOMContentLoaded timing issue - now initializes even if DOM is already loaded
2. ✅ Added comprehensive debug logging
3. ✅ Added manual control functions (openMindMatePanel, closeMindMatePanel, testMindMatePanel)
4. ✅ Added check to ensure panel doesn't have display:none
5. ✅ Added error messages and alerts for missing elements
6. ✅ Added event.preventDefault() and stopPropagation() to button clicks

## Expected Behavior

When you click the MindMate AI button:
1. The AI panel should slide in from the right (420px wide)
2. The button should highlight with an active state (reversed gradient)
3. The property panel (if open) should automatically close
4. The chat input should automatically focus after 300ms

## Reporting Issues

If the panel still doesn't work after these fixes, please provide:
1. All console log messages (especially errors in red)
2. The output of `window.aiAssistant` in the console
3. The output of `document.getElementById('ai-assistant-panel')` in the console
4. Screenshot of the toolbar area where the MindMate AI button should be

---

**Author**: lycosa9527  
**Made by**: MindSpring Team

