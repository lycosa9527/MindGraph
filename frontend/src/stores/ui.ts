/**
 * UI Store - Pinia store for UI state management
 * Migrated from StateManager.ui
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { htmlLangForLocale, loadLocaleMessages, setI18nLocale } from '@/i18n'
import type { LocaleCode, PromptOutputLanguageCode } from '@/i18n/locales'
import {
  UI_LOCALE_CODES,
  detectBrowserLocale,
  isPromptOutputLanguageCode,
  isUiLocale,
  matchedPromptLanguageForUiLocale,
} from '@/i18n/locales'
import { translateForUiLocale } from '@/i18n/translateForUiLocale'
import { computeIsMobileClient } from '@/utils/isMobileClient'
import { isOfficeEmbedDesktop } from '@/utils/officeEmbed'

export type Theme = 'light' | 'dark' | 'system'
export type Language = LocaleCode
export type PromptLanguage = PromptOutputLanguageCode

export type AppMode = 'mindmate' | 'mindgraph' | 'template' | 'course' | 'community'
export type UiVersion = 'chinese' | 'international'
export type MindMapCanvasMode = 'legacy' | 'v2'

const THEME_KEY = 'mindgraph_theme'
const LANGUAGE_KEY = 'language'
const PROMPT_LANGUAGE_KEY = 'mindgraph_prompt_language'
const MATCH_PROMPT_TO_UI_KEY = 'mindgraph_match_prompt_to_ui'
const UI_LANGUAGE_EXPLICIT_KEY = 'mindgraph_ui_language_explicit'
const BROWSER_LOCALE_HINT_KEY = 'mindgraph_browser_locale_hint_dismissed'
const UI_VERSION_KEY = 'mindgraph_ui_version'
export const MINDMAP_CANVAS_MODE_KEY = 'mindgraph_mindmap_canvas_mode'
/**
 * One-time stamp: browsers that still had Classic stored (pre–v2-default era, or
 * early defaults) are moved onto New canvas. After this runs, Classic is honored
 * only when the user explicitly selects it in Language settings.
 */
export const MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY =
  'mindgraph_mindmap_canvas_v2_default_migrated'
export const E_BLACKBOARD_OPTIMIZE_KEY = 'mindgraph_e_blackboard_optimize'
export const SIDEBAR_POEM_ENABLED_KEY = 'mindgraph_sidebar_poem_enabled'

const VALID_MINDMAP_CANVAS_MODES: ReadonlySet<string> = new Set(['legacy', 'v2'])

function isValidMindMapCanvasMode(value: string | null): value is MindMapCanvasMode {
  return value !== null && VALID_MINDMAP_CANVAS_MODES.has(value)
}

type CanvasModeStorage = Pick<Storage, 'getItem' | 'setItem'>

/**
 * Force New (v2) canvas once per browser so Classic is opt-in, not sticky from
 * older defaults. Idempotent via {@link MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY}.
 */
export function ensureMindMapCanvasV2DefaultMigration(
  storage: CanvasModeStorage = localStorage
): void {
  if (storage.getItem(MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY) === '1') {
    return
  }
  storage.setItem(MINDMAP_CANVAS_MODE_KEY, 'v2')
  storage.setItem(MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY, '1')
}

const VALID_UI_VERSIONS: ReadonlySet<string> = new Set(['chinese', 'international'])

function isValidUiVersion(value: string | null): value is UiVersion {
  return value !== null && VALID_UI_VERSIONS.has(value)
}

function detectDefaultUiVersion(): UiVersion {
  return 'international'
}

function isValidLanguage(value: string | null): value is Language {
  return isUiLocale(value)
}

function isValidPromptLanguage(value: string | null): value is PromptLanguage {
  return isPromptOutputLanguageCode(value)
}

/** Diagram template slot specs; copy lives in i18n (`diagramTemplates.*`). */
export interface DiagramTemplate {
  i18nKey: string
  slots: string[]
}

export const DIAGRAM_TEMPLATES: Record<string, DiagramTemplate> = {
  圆圈图: { i18nKey: 'diagramTemplates.circle_map', slots: ['topic'] },
  气泡图: { i18nKey: 'diagramTemplates.bubble_map', slots: ['topic'] },
  双气泡图: { i18nKey: 'diagramTemplates.double_bubble_map', slots: ['itemA', 'itemB'] },
  树形图: { i18nKey: 'diagramTemplates.tree_map', slots: ['criterion', 'subject'] },
  括号图: { i18nKey: 'diagramTemplates.brace_map', slots: ['subject'] },
  流程图: { i18nKey: 'diagramTemplates.flow_map', slots: ['process'] },
  复流程图: { i18nKey: 'diagramTemplates.multi_flow_map', slots: ['event'] },
  桥形图: { i18nKey: 'diagramTemplates.bridge_map', slots: ['relation'] },
  思维导图: { i18nKey: 'diagramTemplates.mindmap', slots: ['theme'] },
}

/** Body text for the selected diagram template in the given UI language */
export function getDiagramTemplateBody(def: DiagramTemplate, lang: Language): string {
  return translateForUiLocale(def.i18nKey, lang)
}

function listJoinSeparator(lang: Language): string {
  return translateForUiLocale('common.listJoin.separator', lang)
}

export const useUIStore = defineStore('ui', () => {
  // State
  const theme = ref<Theme>('light')
  const language = ref<Language>('zh')
  const promptLanguage = ref<PromptLanguage>('zh')
  /** When true, interface language changes also update generation / prompt language. */
  const matchPromptToUi = ref(true)
  const uiLanguageExplicit = ref(false)
  const browserLocaleHintDismissed = ref(false)
  const uiVersion = ref<UiVersion>(detectDefaultUiVersion())
  /** Mind map canvas chrome: legacy (Option 1) or v2 side-toolbar layout (Option 2). Default: v2. */
  const mindMapCanvasMode = ref<MindMapCanvasMode>('v2')
  /**
   * Classroom e-blackboard: enlarge V2 +/- and collapse chrome; desktop touch uses
   * tap=select, double-tap=edit, two-finger pan/zoom. Default off; scale in
   * `mindMapEBlackboard.ts`.
   */
  const eBlackboardOptimize = ref(false)
  /** Sidebar poem under the user name. When off, daily token usage is shown instead. */
  const sidebarPoemEnabled = ref(true)
  const isMobile = ref(false)
  // Word task panes are narrow — start collapsed; user can expand.
  const sidebarCollapsed = ref(isOfficeEmbedDesktop())

  // New: App mode state (MindMate chat vs MindGraph diagram)
  const currentMode = ref<AppMode>('mindmate')

  /** Wireframe mode: black & white / line sketch view for diagram canvas */
  const wireframeMode = ref(false)
  /** Temporary outline-only styling while a mind-map export capture runs. */
  const exportWireframeOutline = ref(false)
  /** Hide canvas chrome (dot grid, pane fill) during raster export capture. */
  const exportRasterCapture = ref(false)
  const selectedChartType = ref<string>('选择具体图示')
  const templateSlots = ref<Record<string, string>>({})
  const freeInputValue = ref<string>('')
  /**
   * When false, Simplified Chinese (`zh`) is omitted from locale cycling (set from auth on login).
   * Guests default to true.
   */
  const languagePolicyAllowZh = ref(true)

  /** Guards async locale loads when the user toggles language rapidly. */
  let languageSwitchSeq = 0

  // Getters
  const effectiveTheme = computed(() => {
    if (theme.value === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return theme.value
  })

  const isDark = computed(() => effectiveTheme.value === 'dark')

  // Stored for cleanup on reset (avoids leak if reset called in full-teardown)
  let mediaQuery: MediaQueryList | null = null
  let mediaQueryHandler: (() => void) | null = null

  // Actions
  function setupMediaQueryListener(): void {
    if (typeof window === 'undefined' || mediaQuery) return
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQueryHandler = () => {
      if (theme.value === 'system') {
        applyTheme()
      }
    }
    mediaQuery.addEventListener('change', mediaQueryHandler)
  }

  /**
   * Apply locale from signed-in user profile (server). Missing server fields keep the current
   * client values (guest localStorage / browser) instead of re-detecting the browser.
   */
  function applyLanguageFromServerProfile(
    ui: string | null | undefined,
    prompt: string | null | undefined,
    options?: { matchPromptToUi?: boolean | null }
  ): void {
    if (options?.matchPromptToUi !== undefined && options.matchPromptToUi !== null) {
      setMatchPromptToUi(options.matchPromptToUi)
    }
    const nextUi: Language = isValidLanguage(ui ?? null) ? (ui as Language) : language.value
    let nextPrompt: PromptLanguage
    if (isValidPromptLanguage(prompt ?? null)) {
      nextPrompt = prompt as PromptLanguage
    } else if (matchPromptToUi.value) {
      const matched = matchedPromptLanguageForUiLocale(nextUi)
      nextPrompt = matched !== null ? matched : promptLanguage.value
    } else {
      nextPrompt = promptLanguage.value
    }

    setLanguage(nextUi)
    if (!matchPromptToUi.value) {
      setPromptLanguage(nextPrompt)
    }
  }

  /**
   * Guest: align with navigator only when there is no saved interface language yet
   * (first visit or cleared storage). Does not override explicit user choices.
   */
  function applyGuestLocaleFromBrowser(): void {
    if (uiLanguageExplicit.value) {
      return
    }
    const stored = localStorage.getItem(LANGUAGE_KEY)
    if (isValidLanguage(stored)) {
      return
    }
    const loc = detectBrowserLocale()
    setLanguage(loc)
    if (!matchPromptToUi.value) {
      const matched = matchedPromptLanguageForUiLocale(loc)
      const pr: PromptLanguage = matched !== null ? matched : 'en'
      setPromptLanguage(pr)
    }
  }

  /**
   * Login modal and /auth: while the user is not signed in, align UI and prompt
   * languages with the browser on every open (guest experience).
   */
  function syncGuestLocaleFromBrowser(): void {
    const loc = detectBrowserLocale()
    if (!matchPromptToUi.value) {
      const matched = matchedPromptLanguageForUiLocale(loc)
      const pr: PromptLanguage = matched !== null ? matched : 'en'
      if (language.value === loc && promptLanguage.value === pr) {
        return
      }
      if (language.value === loc) {
        setPromptLanguage(pr)
        return
      }
    } else if (language.value === loc) {
      return
    }
    setLanguage(loc)
    if (!matchPromptToUi.value) {
      const matched = matchedPromptLanguageForUiLocale(loc)
      const pr: PromptLanguage = matched !== null ? matched : 'en'
      setPromptLanguage(pr)
    }
  }

  function initFromStorage(): void {
    const storedTheme = localStorage.getItem(THEME_KEY) as Theme
    const storedLanguage = localStorage.getItem(LANGUAGE_KEY)
    const storedPrompt = localStorage.getItem(PROMPT_LANGUAGE_KEY)

    if (storedTheme) theme.value = storedTheme

    uiLanguageExplicit.value = localStorage.getItem(UI_LANGUAGE_EXPLICIT_KEY) === '1'
    browserLocaleHintDismissed.value = localStorage.getItem(BROWSER_LOCALE_HINT_KEY) === '1'
    matchPromptToUi.value = localStorage.getItem(MATCH_PROMPT_TO_UI_KEY) !== '0'

    const storedVersion = localStorage.getItem(UI_VERSION_KEY)
    if (isValidUiVersion(storedVersion)) {
      uiVersion.value = storedVersion
    } else {
      uiVersion.value = detectDefaultUiVersion()
    }

    // Move every browser onto New canvas once; Classic only after an explicit choice.
    ensureMindMapCanvasV2DefaultMigration()
    const storedMindMapCanvasMode = localStorage.getItem(MINDMAP_CANVAS_MODE_KEY)
    // Restore post-migration choice; otherwise default to new (v2) layout.
    // Flag sync may force Classic in-memory only when FEATURE_MINDMAP_V2_CANVAS is off.
    if (isValidMindMapCanvasMode(storedMindMapCanvasMode)) {
      mindMapCanvasMode.value = storedMindMapCanvasMode
    } else {
      mindMapCanvasMode.value = 'v2'
    }

    eBlackboardOptimize.value = localStorage.getItem(E_BLACKBOARD_OPTIMIZE_KEY) === '1'
    sidebarPoemEnabled.value = localStorage.getItem(SIDEBAR_POEM_ENABLED_KEY) !== '0'

    if (isValidLanguage(storedLanguage)) {
      language.value = storedLanguage
    } else if (!uiLanguageExplicit.value) {
      const loc = detectBrowserLocale()
      language.value = loc
      localStorage.setItem(LANGUAGE_KEY, loc)
    }

    if (isValidPromptLanguage(storedPrompt)) {
      promptLanguage.value = storedPrompt
    } else if (!uiLanguageExplicit.value) {
      const loc = language.value
      const matched = matchedPromptLanguageForUiLocale(loc)
      const pr: PromptLanguage = matched !== null ? matched : 'en'
      promptLanguage.value = pr
      localStorage.setItem(PROMPT_LANGUAGE_KEY, pr)
    } else if (matchPromptToUi.value) {
      const matched = matchedPromptLanguageForUiLocale(language.value)
      if (matched !== null) {
        promptLanguage.value = matched
        localStorage.setItem(PROMPT_LANGUAGE_KEY, matched)
      }
    }

    if (typeof document !== 'undefined') {
      document.documentElement.lang = htmlLangForLocale(language.value)
    }

    // Check mobile
    checkMobile()
    window.addEventListener('resize', checkMobile)

    // Apply theme
    applyTheme()
    setupMediaQueryListener()
  }

  function removeListeners(): void {
    window.removeEventListener('resize', checkMobile)
    if (mediaQuery && mediaQueryHandler) {
      mediaQuery.removeEventListener('change', mediaQueryHandler)
      mediaQuery = null
      mediaQueryHandler = null
    }
  }

  function setTheme(newTheme: Theme): void {
    theme.value = newTheme
    localStorage.setItem(THEME_KEY, newTheme)
    applyTheme()
  }

  function toggleTheme(): void {
    setTheme(theme.value === 'light' ? 'dark' : 'light')
  }

  function applyTheme(): void {
    const html = document.documentElement
    if (effectiveTheme.value === 'dark') {
      html.classList.add('dark')
    } else {
      html.classList.remove('dark')
    }
  }

  function setLanguage(newLanguage: Language): void {
    if (matchPromptToUi.value) {
      const matched = matchedPromptLanguageForUiLocale(newLanguage)
      if (matched !== null && promptLanguage.value !== matched) {
        promptLanguage.value = matched
        localStorage.setItem(PROMPT_LANGUAGE_KEY, matched)
      }
    }
    if (language.value === newLanguage) {
      document.documentElement.lang = htmlLangForLocale(newLanguage)
      return
    }
    language.value = newLanguage
    localStorage.setItem(LANGUAGE_KEY, newLanguage)
    document.documentElement.lang = htmlLangForLocale(newLanguage)
    languageSwitchSeq += 1
    const seq = languageSwitchSeq
    void loadLocaleMessages(newLanguage).then(() => {
      if (seq !== languageSwitchSeq) {
        return
      }
      setI18nLocale(newLanguage)
    })
  }

  function setPromptLanguage(lang: PromptLanguage): void {
    if (promptLanguage.value === lang) {
      return
    }
    promptLanguage.value = lang
    localStorage.setItem(PROMPT_LANGUAGE_KEY, lang)
  }

  function setMatchPromptToUi(value: boolean): void {
    if (matchPromptToUi.value === value) {
      return
    }
    matchPromptToUi.value = value
    localStorage.setItem(MATCH_PROMPT_TO_UI_KEY, value ? '1' : '0')
  }

  function setUiLanguageExplicit(value: boolean): void {
    uiLanguageExplicit.value = value
    localStorage.setItem(UI_LANGUAGE_EXPLICIT_KEY, value ? '1' : '0')
  }

  function setBrowserLocaleHintDismissed(value: boolean): void {
    browserLocaleHintDismissed.value = value
    localStorage.setItem(BROWSER_LOCALE_HINT_KEY, value ? '1' : '0')
  }

  function setLanguagePolicyAllowZh(allow: boolean): void {
    languagePolicyAllowZh.value = allow
  }

  function toggleLanguage(): void {
    const order = languagePolicyAllowZh.value
      ? UI_LOCALE_CODES
      : UI_LOCALE_CODES.filter((c) => c !== 'zh')
    if (order.length === 0) {
      return
    }
    let idx = order.indexOf(language.value)
    if (idx < 0) {
      idx = 0
    }
    const next = order[(idx + 1) % order.length]
    setLanguage(next)
  }

  function setUiVersion(version: UiVersion): void {
    if (uiVersion.value === version) {
      return
    }
    uiVersion.value = version
    localStorage.setItem(UI_VERSION_KEY, version)
  }

  /**
   * @param persist - When false, update in-memory mode only (used when the v2
   * feature flag is off so Classic is forced at runtime without overwriting the
   * user's saved New-canvas preference).
   */
  function setMindMapCanvasMode(
    mode: MindMapCanvasMode,
    options: { persist?: boolean } = {}
  ): void {
    const persist = options.persist !== false
    const previousMode = mindMapCanvasMode.value
    if (previousMode === mode) {
      // Runtime-only Classic can leave storage on v2; still persist an explicit opt-in.
      if (persist && localStorage.getItem(MINDMAP_CANVAS_MODE_KEY) !== mode) {
        localStorage.setItem(MINDMAP_CANVAS_MODE_KEY, mode)
      }
      return
    }
    mindMapCanvasMode.value = mode
    if (persist) {
      localStorage.setItem(MINDMAP_CANVAS_MODE_KEY, mode)
    }
    eventBus.emit('mindmap:canvas_mode_changed', { previousMode, newMode: mode })
  }

  function setEBlackboardOptimize(value: boolean): void {
    eBlackboardOptimize.value = value
    localStorage.setItem(E_BLACKBOARD_OPTIMIZE_KEY, value ? '1' : '0')
  }

  function setSidebarPoemEnabled(value: boolean): void {
    sidebarPoemEnabled.value = value
    localStorage.setItem(SIDEBAR_POEM_ENABLED_KEY, value ? '1' : '0')
  }

  function applyUiVersionFromServerProfile(version: string | null | undefined): void {
    if (isValidUiVersion(version ?? null)) {
      setUiVersion(version as UiVersion)
    }
  }

  function checkMobile(): void {
    isMobile.value = computeIsMobileClient()
  }

  function setSidebarCollapsed(collapsed: boolean): void {
    sidebarCollapsed.value = collapsed
  }

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function toggleWireframe(): void {
    wireframeMode.value = !wireframeMode.value
  }

  function setExportWireframeOutline(active: boolean): void {
    exportWireframeOutline.value = active
  }

  function setExportRasterCapture(active: boolean): void {
    exportRasterCapture.value = active
  }

  // Mode management
  function setCurrentMode(mode: AppMode): void {
    currentMode.value = mode
  }

  function toggleMode(): void {
    currentMode.value = currentMode.value === 'mindmate' ? 'mindgraph' : 'mindmate'
  }

  // Chart type and template management
  function setSelectedChartType(type: string): void {
    selectedChartType.value = type
    templateSlots.value = {}
    if (type !== '选择具体图示') {
      freeInputValue.value = ''
    }
  }

  function setTemplateSlot(slotName: string, value: string): void {
    templateSlots.value = { ...templateSlots.value, [slotName]: value }
  }

  function clearTemplateSlots(): void {
    templateSlots.value = {}
  }

  function setFreeInputValue(value: string): void {
    freeInputValue.value = value
  }

  function hasValidSlots(): boolean {
    if (selectedChartType.value === '选择具体图示') {
      return freeInputValue.value.trim() !== ''
    }
    const template = DIAGRAM_TEMPLATES[selectedChartType.value]
    if (!template) return false
    return template.slots.every(
      (slot) => templateSlots.value[slot] && templateSlots.value[slot].trim() !== ''
    )
  }

  function getTemplateText(): string {
    if (selectedChartType.value === '选择具体图示') {
      return freeInputValue.value.trim()
    }
    const template = DIAGRAM_TEMPLATES[selectedChartType.value]
    if (!template) return ''

    let text = getDiagramTemplateBody(template, language.value)
    for (const slot of template.slots) {
      const value = templateSlots.value[slot]?.trim() ?? ''
      text = text.replace(`【${slot}】`, value)
    }
    return text
  }

  /**
   * Get topic-only prompt when a specific diagram is selected.
   * Returns user's slot values as the topic (no template wrapper).
   * Used when diagram_type is forced - topic is fixed from user input.
   */
  function getTemplateTopic(): string {
    if (selectedChartType.value === '选择具体图示') {
      return freeInputValue.value.trim()
    }
    const template = DIAGRAM_TEMPLATES[selectedChartType.value]
    if (!template) return ''

    const slots = template.slots
    const values = slots.map((s) => templateSlots.value[s]?.trim() || '').filter(Boolean)
    if (values.length === 0) return ''
    if (values.length === 1) return values[0]
    return values.join(listJoinSeparator(language.value))
  }

  /**
   * Get dimension_preference for tree/brace map when specific diagram selected.
   */
  function getTemplateDimensionPreference(): string | null {
    if (selectedChartType.value !== '树形图' && selectedChartType.value !== '括号图') {
      return null
    }
    const v = templateSlots.value['criterion']?.trim()
    return v || null
  }

  /**
   * Get fixed_dimension for bridge map when specific diagram selected.
   */
  function getTemplateFixedDimension(): string | null {
    if (selectedChartType.value !== '桥形图') return null
    const v = templateSlots.value['relation']?.trim()
    return v || null
  }

  function reset(): void {
    removeListeners()
    theme.value = 'light'
    language.value = 'zh'
    promptLanguage.value = 'zh'
    matchPromptToUi.value = true
    uiLanguageExplicit.value = false
    browserLocaleHintDismissed.value = false
    isMobile.value = false
    sidebarCollapsed.value = isOfficeEmbedDesktop()
    wireframeMode.value = false
    exportWireframeOutline.value = false
    exportRasterCapture.value = false
    currentMode.value = 'mindmate'
    selectedChartType.value = '选择具体图示'
    templateSlots.value = {}
    freeInputValue.value = ''
    languagePolicyAllowZh.value = true
    uiVersion.value = detectDefaultUiVersion()
    localStorage.removeItem(THEME_KEY)
    localStorage.removeItem(LANGUAGE_KEY)
    localStorage.removeItem(PROMPT_LANGUAGE_KEY)
    localStorage.removeItem(MATCH_PROMPT_TO_UI_KEY)
    localStorage.removeItem(UI_LANGUAGE_EXPLICIT_KEY)
    localStorage.removeItem(BROWSER_LOCALE_HINT_KEY)
    localStorage.removeItem(UI_VERSION_KEY)
    localStorage.removeItem(MINDMAP_CANVAS_MODE_KEY)
    localStorage.removeItem(MINDMAP_CANVAS_V2_DEFAULT_MIGRATION_KEY)
    localStorage.removeItem(E_BLACKBOARD_OPTIMIZE_KEY)
    localStorage.removeItem(SIDEBAR_POEM_ENABLED_KEY)
    applyTheme()
    initFromStorage()
  }

  // Initialize
  initFromStorage()

  return {
    // State
    theme,
    language,
    promptLanguage,
    matchPromptToUi,
    uiLanguageExplicit,
    browserLocaleHintDismissed,
    uiVersion,
    mindMapCanvasMode,
    eBlackboardOptimize,
    sidebarPoemEnabled,
    isMobile,
    sidebarCollapsed,
    wireframeMode,
    exportWireframeOutline,
    exportRasterCapture,
    currentMode,
    selectedChartType,
    templateSlots,
    freeInputValue,

    // Getters
    effectiveTheme,
    isDark,

    // Actions
    initFromStorage,
    setTheme,
    toggleTheme,
    setLanguage,
    setPromptLanguage,
    setMatchPromptToUi,
    setUiLanguageExplicit,
    setBrowserLocaleHintDismissed,
    toggleLanguage,
    languagePolicyAllowZh,
    setLanguagePolicyAllowZh,
    setUiVersion,
    setMindMapCanvasMode,
    setEBlackboardOptimize,
    setSidebarPoemEnabled,
    applyUiVersionFromServerProfile,
    applyLanguageFromServerProfile,
    applyGuestLocaleFromBrowser,
    syncGuestLocaleFromBrowser,
    checkMobile,
    setSidebarCollapsed,
    toggleSidebar,
    toggleWireframe,
    setExportWireframeOutline,
    setExportRasterCapture,
    setCurrentMode,
    toggleMode,
    setSelectedChartType,
    setTemplateSlot,
    clearTemplateSlots,
    setFreeInputValue,
    hasValidSlots,
    getTemplateText,
    getTemplateTopic,
    getTemplateDimensionPreference,
    getTemplateFixedDimension,
    reset,
  }
})
