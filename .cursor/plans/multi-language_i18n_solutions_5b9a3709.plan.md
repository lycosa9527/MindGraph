---
name: Multi-language i18n Solutions
overview: Evaluate and propose elegant i18n solutions for scaling from 2 languages (en/zh) to 30+ languages with browser language detection, replacing the current custom translation system used across 147 files.
todos:
  - id: research-complete
    content: Research current i18n implementation and identify solution options
    status: pending
  - id: present-options
    content: Present 4 solution options with pros/cons to user
    status: pending
  - id: wait-decision
    content: Wait for user to choose preferred solution approach
    status: pending
isProject: false
---

# Multi-Language i18n Solutions for MindGraph

## Current State Analysis

Your project currently uses a custom i18n solution:

- **Location**: `frontend/src/composables/useLanguage.ts` and `frontend/src/stores/ui.ts`
- **Languages**: Only English (`en`) and Chinese (`zh`)
- **Usage**: 1,088 translation calls across 147 files
- **Storage**: Language preference stored in localStorage
- **Limitations**: 
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No browser language detection
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Translations hardcoded in single file (not scalable for 30 languages)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No fallback chain (e.g., `en-US` → `en` → default)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No lazy loading of translation files
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No pluralization support
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No date/number formatting per locale

## Solution Options

### Option 1: Vue I18n (vue-i18n) - Recommended for Vue Projects

**Pros:**

- Official Vue.js i18n solution, mature and well-maintained
- Built-in browser language detection via `getBrowserLocale()`
- Supports lazy loading of translation files (critical for 30 languages)
- Rich features: pluralization, number/date formatting, fallback chains
- Excellent TypeScript support
- Active community and extensive documentation
- Can migrate incrementally (works alongside existing code)
- Supports Vue 3 Composition API (`useI18n()` composable)

**Cons:**

- Larger bundle size (~1.5MB, but can be tree-shaken)
- Learning curve for advanced features
- Requires restructuring translation files

**Migration Path:**

- Install `vue-i18n@9` (Vue 3 compatible)
- Move translations to separate JSON files: `locales/en.json`, `locales/zh.json`, etc.
- Replace `useLanguage()` composable with `useI18n()` from vue-i18n
- Add browser detection in app initialization
- Implement lazy loading for non-default languages

**File Structure:**

```
frontend/src/
  locales/
    en.json
    zh.json
    es.json
    fr.json
    ... (30 languages)
  i18n/
    index.ts (i18n setup with browser detection)
```

### Option 2: FormatJS (vue-intl) - Standards-Based Approach

**Pros:**

- Built on ECMA-402 and ICU Message syntax (industry standards)
- Used by major companies (Yahoo, Dropbox, Mozilla, Coinbase)
- Modular architecture (smaller bundle per feature)
- Excellent tooling: CLI for message extraction, eslint plugin
- Strong TypeScript support
- Framework-agnostic core (can reuse logic)

**Cons:**

- Less Vue-specific integration than vue-i18n
- Smaller community for Vue specifically
- More verbose setup
- Requires learning ICU Message syntax

**Migration Path:**

- Install `@formatjs/vue-intl` and `intl-messageformat`
- Convert translations to ICU format
- Set up message extraction tooling
- Configure browser locale detection

### Option 3: Enhanced Custom Solution - Minimal Migration

**Pros:**

- Minimal code changes (keep existing `useLanguage()` API)
- Full control over implementation
- No new dependencies
- Can add features incrementally

**Cons:**

- You maintain all i18n logic yourself
- Need to implement browser detection, lazy loading, fallbacks
- More work to reach feature parity with libraries
- Risk of reinventing the wheel

**Enhancements Needed:**

- Browser language detection using `navigator.languages`
- Fallback chain: `en-US` → `en` → `zh` → default
- Lazy loading: Load translation files on-demand
- Split translations into separate JSON files per language
- Add pluralization support
- Add date/number formatting helpers

### Option 4: Hybrid Approach - Custom + vue-i18n Core

**Pros:**

- Keep your existing API surface
- Use vue-i18n's formatting/pluralization under the hood
- Gradual migration path

**Cons:**

- More complex implementation
- Still need to maintain wrapper code

## Recommended Approach: Vue I18n (Option 1)

For scaling to 30 languages, **Vue I18n** is the best choice because:

1. **Browser Detection**: Built-in `getBrowserLocale()` with fallback chain support
2. **Lazy Loading**: Critical for 30 languages - only load what's needed
3. **File Organization**: Natural separation into `locales/` directory
4. **Migration Path**: Can wrap vue-i18n to maintain your `useLanguage()` API initially
5. **Ecosystem**: Mature tooling, plugins, and community support
6. **Performance**: Tree-shaking and code splitting support

## Implementation Considerations

### Browser Language Detection Strategy

```typescript
// Priority order:
1. User's saved preference (localStorage)
2. Browser's navigator.languages array
3. Fallback chain: exact match → language code → default (en)
```

### Translation File Organization

**Option A: Flat Structure** (Simple)

```
locales/
  en.json
  zh.json
  es.json
  ...
```

**Option B: Namespaced** (Better for large apps)

```
locales/
  en/
    common.json
    auth.json
    editor.json
  zh/
    common.json
    auth.json
    editor.json
```

### Lazy Loading Strategy

- Load default language (en) immediately
- Load user's language on app start
- Load other languages on-demand when user switches
- Cache loaded languages in memory

### Migration Strategy

1. **Phase 1**: Install vue-i18n, set up alongside existing system
2. **Phase 2**: Migrate translations to JSON files, keep both systems running
3. **Phase 3**: Update components to use vue-i18n gradually
4. **Phase 4**: Remove custom `useLanguage()` once all components migrated

## Questions to Consider

1. **Translation Management**: Will you use a translation management service (e.g., Crowdin, Lokalise) or manage JSON files manually?
2. **RTL Support**: Do you need right-to-left language support (Arabic, Hebrew)?
3. **Pluralization**: Do you need complex plural rules (e.g., Russian has 3+ plural forms)?
4. **Date/Number Formatting**: Do you need locale-specific formatting (e.g., `1,234.56` vs `1.234,56`)?
5. **Backend Integration**: Will translations come from API or static files?

## Step-by-Step Implementation Plan (Vue I18n)

### Phase 1: Installation & Setup

#### Step 1.1: Install Dependencies

```bash
cd frontend
npm install vue-i18n@9
```

#### Step 1.2: Create Directory Structure

```
frontend/src/
  locales/
    en.json          # English (default)
    zh.json          # Chinese
    es.json          # Spanish (example)
    fr.json          # French (example)
    ...              # Add more languages as needed
  i18n/
    index.ts         # i18n configuration
    browser.ts       # Browser detection utilities
```

### Phase 2: Configuration Setup

#### Step 2.1: Create Browser Detection Utility (`i18n/browser.ts`)

```typescript
/**
 * Browser language detection utilities
 */

export type SupportedLocale = 'en' | 'zh' | 'es' | 'fr' | 'de' | 'ja' | 'ko' | 'ru' | 'ar' | 'pt' | 'it' | 'nl' | 'pl' | 'tr' | 'vi' | 'th' | 'id' | 'hi' | 'cs' | 'sv' | 'da' | 'fi' | 'no' | 'he' | 'uk' | 'ro' | 'hu' | 'el' | 'bg'

export const SUPPORTED_LOCALES: SupportedLocale[] = [
  'en', 'zh', 'es', 'fr', 'de', 'ja', 'ko', 'ru', 'ar', 'pt',
  'it', 'nl', 'pl', 'tr', 'vi', 'th', 'id', 'hi', 'cs', 'sv',
  'da', 'fi', 'no', 'he', 'uk', 'ro', 'hu', 'el', 'bg'
]

export const DEFAULT_LOCALE: SupportedLocale = 'en'

const LANGUAGE_KEY = 'mindgraph_language'

/**
 * Get user's saved language preference from localStorage
 */
export function getSavedLocale(): SupportedLocale | null {
  if (typeof window === 'undefined') return null
  const saved = localStorage.getItem(LANGUAGE_KEY)
  return saved && SUPPORTED_LOCALES.includes(saved as SupportedLocale)
    ? (saved as SupportedLocale)
    : null
}

/**
 * Save language preference to localStorage
 */
export function saveLocale(locale: SupportedLocale): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(LANGUAGE_KEY, locale)
}

/**
 * Get browser's preferred language from navigator
 * Returns the first supported locale from browser's language list
 */
export function getBrowserLocale(): SupportedLocale {
  if (typeof window === 'undefined') return DEFAULT_LOCALE

  const browserLanguages = navigator.languages || [navigator.language]

  // Try exact match first (e.g., 'en-US' -> 'en')
  for (const browserLang of browserLanguages) {
    const langCode = browserLang.split('-')[0].toLowerCase()
    if (SUPPORTED_LOCALES.includes(langCode as SupportedLocale)) {
      return langCode as SupportedLocale
    }
  }

  // Try full locale match (e.g., 'zh-CN', 'en-US')
  for (const browserLang of browserLanguages) {
    const normalized = browserLang.toLowerCase().replace('_', '-')
    // Check if any supported locale matches
    for (const supported of SUPPORTED_LOCALES) {
      if (normalized.startsWith(supported)) {
        return supported
      }
    }
  }

  return DEFAULT_LOCALE
}

/**
 * Detect initial locale with fallback chain:
 * 1. Saved preference (localStorage)
 * 2. Browser language
 * 3. Default (en)
 */
export function detectInitialLocale(): SupportedLocale {
  return getSavedLocale() || getBrowserLocale() || DEFAULT_LOCALE
}
```

#### Step 2.2: Create i18n Configuration (`i18n/index.ts`)

```typescript
import { createI18n, type I18n } from 'vue-i18n'
import { detectInitialLocale, saveLocale, type SupportedLocale, DEFAULT_LOCALE } from './browser'

// Import default language synchronously (always loaded)
import enMessages from '@/locales/en.json'

// Type for translation messages
type MessageSchema = typeof enMessages

// Lazy load translation files
const loadLocaleMessages = async (locale: SupportedLocale): Promise<Record<string, unknown>> => {
  // Default language already loaded
  if (locale === 'en') {
    return enMessages
  }

  // Dynamically import other languages
  try {
    const messages = await import(`@/locales/${locale}.json`)
    return messages.default
  } catch (error) {
    console.warn(`Failed to load locale ${locale}, falling back to English`, error)
    return enMessages
  }
}

// Create i18n instance
export function setupI18n(locale: SupportedLocale = detectInitialLocale()): I18n<MessageSchema> {
  const i18n = createI18n<MessageSchema>({
    legacy: false, // Use Composition API mode
    locale,
    fallbackLocale: DEFAULT_LOCALE,
    messages: {
      en: enMessages, // Pre-loaded default
    },
    missingWarn: import.meta.env.DEV,
    fallbackWarn: import.meta.env.DEV,
  })

  // Load initial locale if not English
  if (locale !== 'en') {
    loadLocaleMessages(locale).then((messages) => {
      i18n.global.setLocaleMessage(locale, messages)
    })
  }

  return i18n
}

// Initialize i18n
export const i18n = setupI18n()

// Helper to change locale with persistence
export async function setLocale(locale: SupportedLocale): Promise<void> {
  // Load messages if not already loaded
  if (!i18n.global.availableLocales.includes(locale)) {
    const messages = await loadLocaleMessages(locale)
    i18n.global.setLocaleMessage(locale, messages)
  }

  i18n.global.locale.value = locale
  saveLocale(locale)
  document.documentElement.lang = locale
}

export default i18n
```

#### Step 2.3: Update Main App Entry (`main.ts`)

```typescript
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { i18n } from './i18n' // Add this import

const app = createApp(App)

app.use(router)
app.use(i18n) // Add this line

app.mount('#app')
```

### Phase 3: Migrate Translation Files

#### Step 3.1: Extract Current Translations to JSON

**Create `locales/en.json`:**

```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "edit": "Edit",
    "confirm": "Confirm",
    "close": "Close",
    "loading": "Loading...",
    "success": "Success",
    "error": "Error",
    "warning": "Warning",
    "refresh": "Refresh"
  },
  "auth": {
    "login": "Login",
    "register": "Register",
    "logout": "Logout",
    "username": "Username",
    "phone": "Phone Number",
    "password": "Password",
    "captcha": "Captcha",
    "enterCaptcha": "Enter captcha",
    "clickToRefresh": "Click image to refresh",
    "loginFailed": "Login failed",
    "sessionExpired": "Session expired. Please login again.",
    "smsLogin": "SMS Login",
    "resetPassword": "Reset Password",
    "backToLogin": "Back to Login"
  },
  "editor": {
    "newDiagram": "New Diagram",
    "saveDiagram": "Save Diagram",
    "exportImage": "Export Image",
    "undo": "Undo",
    "redo": "Redo",
    "zoomIn": "Zoom In",
    "zoomOut": "Zoom Out",
    "fitToScreen": "Fit to Screen",
    "selectDiagramType": "Select Diagram Type"
  },
  "diagram": {
    "newAttribute": "New Attribute",
    "newBranch": "New Branch",
    "newSubitem": "Sub-item",
    "newStep": "New Step",
    "newSubstep": "New Substep",
    "newPart": "New Part",
    "newChild": "New Child"
  },
  "panel": {
    "mindmate": "MindMate AI",
    "nodePalette": "Node Palette",
    "properties": "Properties"
  },
  "askonce": {
    "title": "AskOnce"
  },
  "notification": {
    "saved": "Changes saved successfully",
    "deleted": "Item deleted successfully",
    "sessionInvalidated": "You have been logged out because you exceeded the maximum number of devices",
    "newVersionAvailable": "New version available. Click to refresh."
  }
}
```

**Create `locales/zh.json`** (same structure, Chinese translations)

#### Step 3.2: Update TypeScript Config for JSON Imports

**Update `tsconfig.json` or `vite.config.ts`:**

```typescript
// vite.config.ts
export default defineConfig({
  // ... existing config
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

### Phase 4: Create Migration Wrapper (Optional - for gradual migration)

#### Step 4.1: Update `composables/useLanguage.ts` to use vue-i18n

```typescript
import { useI18n } from 'vue-i18n'
import { setLocale, type SupportedLocale } from '@/i18n'
import { computed } from 'vue'

/**
 * Language Composable - Wrapper around vue-i18n
 * Maintains backward compatibility with existing code
 */
export function useLanguage() {
  const { t: vueT, locale } = useI18n()

  const currentLanguage = computed(() => locale.value as SupportedLocale)
  const isZh = computed(() => locale.value === 'zh')
  const isEn = computed(() => locale.value === 'en')

  // Wrapper function to maintain existing API
  function t(key: string, fallback?: string): string {
    const translation = vueT(key)
    // If translation equals key, it means missing translation
    return translation === key ? (fallback || key) : translation
  }

  function setLanguage(lang: SupportedLocale): void {
    setLocale(lang)
  }

  function toggleLanguage(): void {
    const newLang: SupportedLocale = locale.value === 'en' ? 'zh' : 'en'
    setLocale(newLang)
  }

  function getNotification(key: string, ...args: unknown[]): string {
    let message = t(`notification.${key}`)

    // Simple template replacement
    args.forEach((arg, index) => {
      message = message.replace(`{${index}}`, String(arg))
    })

    return message
  }

  return {
    currentLanguage,
    isZh,
    isEn,
    t,
    setLanguage,
    toggleLanguage,
    getNotification,
  }
}

// Export translations for backward compatibility (if needed)
export const translations = {} // Can be removed after full migration
```

### Phase 5: Update UI Store

#### Step 5.1: Update `stores/ui.ts`

```typescript
import { setLocale, detectInitialLocale, type SupportedLocale } from '@/i18n'

// Update Language type to include all supported locales
export type Language = SupportedLocale

// In the store, update setLanguage function:
function setLanguage(newLanguage: Language): void {
  setLocale(newLanguage) // Use vue-i18n's setLocale
  // Remove localStorage.setItem - handled by i18n/browser.ts
  // Remove document.documentElement.lang - handled by i18n/index.ts
}

// Update initFromStorage:
function initFromStorage(): void {
  const storedTheme = localStorage.getItem(THEME_KEY) as Theme
  // Remove language loading - handled by i18n initialization
  
  if (storedTheme) theme.value = storedTheme
  // Language is now handled by vue-i18n initialization
  
  checkMobile()
  window.addEventListener('resize', checkMobile)
  applyTheme()
}
```

### Phase 6: Component Migration (Gradual)

#### Step 6.1: Update Components to Use New API

**Example migration for a component:**

```vue
<script setup lang="ts">
// OLD:
// import { useLanguage } from '@/composables/useLanguage'
// const { t, isZh } = useLanguage()

// NEW (same API, works immediately):
import { useLanguage } from '@/composables/useLanguage'
const { t, isZh } = useLanguage()

// Or use vue-i18n directly:
// import { useI18n } from 'vue-i18n'
// const { t } = useI18n()
</script>

<template>
  <!-- OLD: -->
  <!-- <button>{{ t('common.save') }}</button> -->
  
  <!-- NEW (same syntax): -->
  <button>{{ t('common.save') }}</button>
</template>
```

### Phase 7: Add Additional Languages

#### Step 7.1: Create New Language Files

1. Copy `locales/en.json` to `locales/[locale].json`
2. Translate all strings
3. Add locale to `SUPPORTED_LOCALES` in `i18n/browser.ts`
4. Language will be auto-detected if browser supports it

### Phase 8: Testing & Validation

#### Step 8.1: Test Checklist

- [ ] Browser language detection works
- [ ] Language switching persists in localStorage
- [ ] Fallback to English when translation missing
- [ ] Lazy loading works (check Network tab)
- [ ] All 147 files using translations still work
- [ ] Date/number formatting (if needed)
- [ ] RTL support (if Arabic/Hebrew added)

### Phase 9: Cleanup (After Full Migration)

#### Step 9.1: Remove Old Code

- Remove hardcoded translations from `useLanguage.ts`
- Remove `translations` export if no longer needed
- Update any direct localStorage language access
- Remove old language detection logic from `ui.ts`

## Migration Timeline Estimate

- **Phase 1-2**: Setup & Configuration (2-3 hours)
- **Phase 3**: Translation File Migration (1-2 hours)
- **Phase 4-5**: Wrapper & Store Updates (1 hour)
- **Phase 6**: Component Migration (can be gradual, 0 hours initially due to wrapper)
- **Phase 7**: Add New Languages (ongoing)
- **Phase 8**: Testing (2-3 hours)
- **Phase 9**: Cleanup (1 hour)

**Total Initial Setup**: ~7-10 hours

**Gradual Migration**: Can be done incrementally without breaking existing code

## Notes

- The wrapper approach (Phase 4) allows you to migrate gradually without breaking existing code
- Browser detection happens automatically on app load
- Lazy loading ensures only needed languages are loaded
- TypeScript support is maintained throughout
- All 147 files will continue working during migration