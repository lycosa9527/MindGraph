/**
 * UI Store - Pinia store for UI state management
 * Migrated from StateManager.ui
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

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

export type Theme = 'light' | 'dark' | 'system'
export type Language = LocaleCode
export type PromptLanguage = PromptOutputLanguageCode

export type AppMode = 'mindmate' | 'mindgraph' | 'template' | 'course' | 'community'
export type UiVersion = 'chinese' | 'international'

const THEME_KEY = 'mindgraph_theme'
const LANGUAGE_KEY = 'language'
const PROMPT_LANGUAGE_KEY = 'mindgraph_prompt_language'
const MATCH_PROMPT_TO_UI_KEY = 'mindgraph_match_prompt_to_ui'
const UI_LANGUAGE_EXPLICIT_KEY = 'mindgraph_ui_language_explicit'
const BROWSER_LOCALE_HINT_KEY = 'mindgraph_browser_locale_hint_dismissed'
const UI_VERSION_KEY = 'mindgraph_ui_version'

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
  const isMobile = ref(false)
  const sidebarCollapsed = ref(false)

  // New: App mode state (MindMate chat vs MindGraph diagram)
  const currentMode = ref<AppMode>('mindmate')

  /** Wireframe mode: black & white / line sketch view for diagram canvas */
  const wireframeMode = ref(false)
  const selectedChartType = ref<string>('选择具体图示')
  const templateSlots = ref<Record<string, string>>({})
  const freeInputValue = ref<string>('')
  /**
   * When false, Simplified Chinese (`zh`) is omitted from locale cycling (set from auth on login).
   * Guests default to true.
   */
  const languagePolicyAllowZh = ref(true)

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
    language.value = newLanguage
    localStorage.setItem(LANGUAGE_KEY, newLanguage)
    document.documentElement.lang = htmlLangForLocale(newLanguage)
    if (matchPromptToUi.value) {
      const matched = matchedPromptLanguageForUiLocale(newLanguage)
      if (matched !== null) {
        promptLanguage.value = matched
        localStorage.setItem(PROMPT_LANGUAGE_KEY, matched)
      }
    }
    void loadLocaleMessages(newLanguage).then(() => {
      setI18nLocale(newLanguage)
    })
  }

  function setPromptLanguage(lang: PromptLanguage): void {
    promptLanguage.value = lang
    localStorage.setItem(PROMPT_LANGUAGE_KEY, lang)
  }

  function setMatchPromptToUi(value: boolean): void {
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
    uiVersion.value = version
    localStorage.setItem(UI_VERSION_KEY, version)
  }

  function applyUiVersionFromServerProfile(version: string | null | undefined): void {
    if (isValidUiVersion(version ?? null)) {
      setUiVersion(version as UiVersion)
    } else {
      setUiVersion('international')
    }
  }

  function checkMobile(): void {
    isMobile.value = window.innerWidth < 768
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
    sidebarCollapsed.value = false
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
    isMobile,
    sidebarCollapsed,
    wireframeMode,
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
    applyUiVersionFromServerProfile,
    applyLanguageFromServerProfile,
    applyGuestLocaleFromBrowser,
    syncGuestLocaleFromBrowser,
    checkMobile,
    setSidebarCollapsed,
    toggleSidebar,
    toggleWireframe,
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
