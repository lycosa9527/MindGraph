# LLM Button Visual Design Specification

## Overview
Professional glowing ring effect for LLM completion states in the Editor status bar.

---

## Design Principles
- **Clean**: Minimal, unobtrusive visual feedback
- **Neat**: Organized color scheme with consistent spacing
- **Professional**: Subtle animations, no flashy effects

---

## Button States

### 1. **Default State**
- Transparent background
- Subtle colored border (40% opacity)
- Muted white text (70% opacity)

### 2. **Hover State**
- Light colored background (20% opacity)
- Stronger border (60% opacity)
- Brighter text (90% opacity)

### 3. **Active State** (Selected LLM)
- Solid colored background (80% opacity)
- Full border (100% opacity)
- White text, bold font

### 4. **Loading State**
- Yellow-tinted background
- Hourglass emoji (⏳) with pulsing opacity
- Disabled interaction

### 5. **✨ Ready State** (NEW - Results Available)
- **Pulsing glowing ring** effect around button
- **Color-coded** by LLM provider
- **Subtle background tint** (15% opacity)
- **Enhanced border** (80% opacity)
- **Animation**: 2-second smooth pulse cycle

### 6. **Active + Ready State**
- Same as Ready State
- **Animation stops** (solid glow, no pulsing)
- Indicates currently viewing this result

### 7. **Error State**
- Red-tinted border (50% opacity)
- Muted text (50% opacity)
- No glow effect

---

## Color Scheme

### Qwen - Blue
```css
Primary: #3498db / rgb(52, 152, 219)
- Glow Light:   rgba(52, 152, 219, 0.6)
- Glow Medium:  rgba(52, 152, 219, 0.4)
- Glow Dark:    rgba(52, 152, 219, 0.2)
- Background:   rgba(52, 152, 219, 0.15)
- Border:       rgba(52, 152, 219, 0.8)
```

### DeepSeek - Purple
```css
Primary: #9b59b6 / rgb(155, 89, 182)
- Glow Light:   rgba(155, 89, 182, 0.6)
- Glow Medium:  rgba(155, 89, 182, 0.4)
- Glow Dark:    rgba(155, 89, 182, 0.2)
- Background:   rgba(155, 89, 182, 0.15)
- Border:       rgba(155, 89, 182, 0.8)
```

### Hunyuan - Orange/Gold
```css
Primary: #f39c12 / rgb(243, 156, 18)
- Glow Light:   rgba(243, 156, 18, 0.6)
- Glow Medium:  rgba(243, 156, 18, 0.4)
- Glow Dark:    rgba(243, 156, 18, 0.2)
- Background:   rgba(243, 156, 18, 0.15)
- Border:       rgba(243, 156, 18, 0.8)
```

### Kimi - Teal/Green
```css
Primary: #1abc9c / rgb(26, 188, 156)
- Glow Light:   rgba(26, 188, 156, 0.6)
- Glow Medium:  rgba(26, 188, 156, 0.4)
- Glow Dark:    rgba(26, 188, 156, 0.2)
- Background:   rgba(26, 188, 156, 0.15)
- Border:       rgba(26, 188, 156, 0.8)
```

---

## Glowing Ring Effect

### Structure
The glow effect uses **multi-layered box-shadow** for depth:

```css
box-shadow: 
    0 0 8px  var(--glow-color-light),   /* Inner ring */
    0 0 12px var(--glow-color-medium),  /* Middle ring */
    0 0 16px var(--glow-color-dark),    /* Outer ring */
    inset 0 0 8px var(--glow-color-light); /* Inner glow */
```

### Animation Cycle
**Duration**: 2 seconds  
**Timing**: ease-in-out (smooth acceleration/deceleration)  
**Loop**: infinite

**Keyframe 0% / 100%** (Resting state):
- Outer glow: 8px → 12px → 16px radius
- Inner glow: 8px radius (inset)

**Keyframe 50%** (Expanded state):
- Outer glow: 12px → 20px → 28px radius
- Inner glow: 12px radius (inset)

### Visual Appearance
```
┌─────────────────────────────────────┐
│                                     │
│   ╔═══════════════════════════╗    │ ← Outer glow (dark)
│   ║ ┌───────────────────────┐ ║    │ ← Middle glow (medium)
│   ║ │  ╔═════════════════╗  │ ║    │ ← Inner glow (light)
│   ║ │  ║     Button      ║  │ ║    │ ← Button with inset glow
│   ║ │  ║  [ Qwen  ]      ║  │ ║    │
│   ║ │  ╚═════════════════╝  │ ║    │
│   ║ └───────────────────────┘ ║    │
│   ╚═══════════════════════════╝    │
│                                     │
└─────────────────────────────────────┘
        ↑ Pulses outward (2s cycle)
```

---

## User Experience Flow

### Autocomplete Scenario

1. **User clicks "Auto Complete" button**
   - All 4 LLM buttons → **Loading state** (yellow, hourglass)

2. **First LLM completes (e.g., Qwen)**
   - Qwen button → **Ready state** (blue glow, pulsing)
   - Qwen button → **Active + Ready** (blue glow, solid, no pulse)
   - Diagram renders with Qwen result

3. **Second LLM completes (e.g., DeepSeek)**
   - DeepSeek button → **Ready state** (purple glow, pulsing)
   - Qwen stays Active + Ready

4. **Third LLM completes (e.g., Hunyuan)**
   - Hunyuan button → **Ready state** (orange glow, pulsing)

5. **Fourth LLM completes (e.g., Kimi)**
   - Kimi button → **Ready state** (teal glow, pulsing)

6. **User clicks DeepSeek button**
   - DeepSeek → **Active + Ready** (purple glow, solid)
   - Qwen → **Ready state** (blue glow, pulsing resumes)
   - Diagram switches to DeepSeek result

7. **Visual State Summary**
   ```
   Status Bar:
   ┌─────────────────────────────────────────────────┐
   │ AI Model:                                       │
   │  [ Qwen ]    [DeepSeek]  [Hunyuan]   [ Kimi ]  │
   │  ⚪ pulse    🟣 solid    🟠 pulse    🔵 pulse   │
   │  (ready)    (active)    (ready)     (ready)    │
   └─────────────────────────────────────────────────┘
   ```

---

## Technical Implementation

### CSS Custom Properties
```css
--glow-color-light:  /* 60% opacity */
--glow-color-medium: /* 40% opacity */
--glow-color-dark:   /* 20% opacity */
```

### Animation Keyframe
```css
@keyframes glow-pulse {
    0%, 100% {
        box-shadow: /* small glow */
    }
    50% {
        box-shadow: /* large glow */
    }
}
```

### Class Application
```javascript
// When LLM completes successfully
button.classList.add('ready');

// When user selects that LLM
button.classList.add('active');
// Result: .llm-btn.ready.active (solid glow, no pulse)
```

---

## Performance Considerations

1. **Hardware Acceleration**
   - `box-shadow` is GPU-accelerated on modern browsers
   - Smooth 60fps animation on most devices

2. **Animation Pausing**
   - Stops when button is active (reduces GPU usage)
   - Only animates buttons with pending results

3. **CSS Variables**
   - Reusable color definitions
   - Easy to maintain and modify

---

## Browser Compatibility

- ✅ Chrome/Edge 90+ (full support)
- ✅ Firefox 88+ (full support)
- ✅ Safari 14+ (full support)
- ✅ CSS custom properties widely supported
- ✅ Box-shadow animations supported everywhere

---

## Future Enhancements

1. **Accessibility**
   - Add `aria-label` with completion status
   - Provide non-visual feedback (screen reader announcements)

2. **User Preferences**
   - Toggle for reduced motion (`prefers-reduced-motion`)
   - Customizable glow intensity

3. **Advanced Animations**
   - Stagger animation start times for cascading effect
   - Success checkmark overlay on completion

---

## Commit History

- `c33dba3` - Add professional glowing ring effect for LLM button completion states
- `c8bf8e2` - Fix Hunyuan API response format parsing
- `9648268` - Add Tencent Hunyuan (混元) LLM support

---

**Author**: lycosa9527  
**Made by**: MindSpring Team  
**Date**: 2025-10-08  
**Version**: 4.1.0

