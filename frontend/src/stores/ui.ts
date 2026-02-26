/**
 * UI Store - Pinia store for UI state management
 * Migrated from StateManager.ui
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

export type Theme = 'light' | 'dark' | 'system'
export type Language = 'en' | 'zh'
export type AppMode = 'mindmate' | 'mindgraph' | 'template' | 'course' | 'community'

const THEME_KEY = 'mindgraph_theme'
const LANGUAGE_KEY = 'language'

// Diagram template definitions
export interface DiagramTemplate {
  template: string
  slots: string[]
}

export const DIAGRAM_TEMPLATES: Record<string, DiagramTemplate> = {
  圆圈图: { template: '用圆圈图联想【中心词】。', slots: ['中心词'] },
  气泡图: { template: '用气泡图描述【中心词】。', slots: ['中心词'] },
  双气泡图: { template: '对比【事物A】和【事物B】。', slots: ['事物A', '事物B'] },
  树形图: { template: '按照【分类标准】对【事物】分类。', slots: ['分类标准', '事物'] },
  括号图: { template: '用括号图拆分【事物】。', slots: ['事物'] },
  流程图: { template: '梳理【过程】的步骤。', slots: ['过程'] },
  复流程图: { template: '分析【事件】的原因和结果。', slots: ['事件'] },
  桥形图: { template: '绘制对应关系为【对应关系】的桥形图。', slots: ['对应关系'] },
  思维导图: { template: '以【主题】为主题，绘制一幅思维导图。', slots: ['主题'] },
}

export const useUIStore = defineStore('ui', () => {
  // State
  const theme = ref<Theme>('light')
  const language = ref<Language>('zh')
  const isMobile = ref(false)
  const sidebarCollapsed = ref(false)

  // New: App mode state (MindMate chat vs MindGraph diagram)
  const currentMode = ref<AppMode>('mindmate')

  /** Wireframe mode: black & white / line sketch view for diagram canvas */
  const wireframeMode = ref(false)
  const selectedChartType = ref<string>('选择具体图示')
  const templateSlots = ref<Record<string, string>>({})
  const freeInputValue = ref<string>('')

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

  function initFromStorage(): void {
    const storedTheme = localStorage.getItem(THEME_KEY) as Theme
    const storedLanguage = localStorage.getItem(LANGUAGE_KEY) as Language

    if (storedTheme) theme.value = storedTheme
    if (storedLanguage) language.value = storedLanguage

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
    document.documentElement.lang = newLanguage
  }

  function toggleLanguage(): void {
    setLanguage(language.value === 'en' ? 'zh' : 'en')
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

    let text = template.template
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
    return values.join(' 和 ')
  }

  /**
   * Get dimension_preference for tree/brace map when specific diagram selected.
   */
  function getTemplateDimensionPreference(): string | null {
    if (selectedChartType.value !== '树形图' && selectedChartType.value !== '括号图') {
      return null
    }
    const v = templateSlots.value['分类标准']?.trim()
    return v || null
  }

  /**
   * Get fixed_dimension for bridge map when specific diagram selected.
   */
  function getTemplateFixedDimension(): string | null {
    if (selectedChartType.value !== '桥形图') return null
    const v = templateSlots.value['对应关系']?.trim()
    return v || null
  }

  function reset(): void {
    removeListeners()
    theme.value = 'light'
    language.value = 'zh'
    isMobile.value = false
    sidebarCollapsed.value = false
    currentMode.value = 'mindmate'
    selectedChartType.value = '选择具体图示'
    templateSlots.value = {}
    freeInputValue.value = ''
    localStorage.removeItem(THEME_KEY)
    localStorage.removeItem(LANGUAGE_KEY)
    applyTheme()
    initFromStorage()
  }

  // Initialize
  initFromStorage()

  return {
    // State
    theme,
    language,
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
    toggleLanguage,
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
