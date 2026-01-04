/**
 * UI Store - Pinia store for UI state management
 * Migrated from StateManager.ui
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

export type Theme = 'light' | 'dark' | 'system'
export type Language = 'en' | 'zh'
export type AppMode = 'mindmate' | 'mindgraph'

const THEME_KEY = 'mindgraph_theme'
const LANGUAGE_KEY = 'language'

// Diagram template definitions
export interface DiagramTemplate {
  template: string
  slots: string[]
}

export const DIAGRAM_TEMPLATES: Record<string, DiagramTemplate> = {
  圆圈图: { template: '用气泡图联想【中心词】。', slots: ['中心词'] },
  气泡图: { template: '用圆圈图描述【中心词】。', slots: ['中心词'] },
  双气泡图: { template: '对比【事物A】和【事物B】。', slots: ['事物A', '事物B'] },
  树形图: { template: '按照【分类标准】对【事物】分类。', slots: ['分类标准', '事物'] },
  括号图: { template: '用括号图拆分【事物】。', slots: ['事物'] },
  流程图: { template: '梳理【过程】的步骤。', slots: ['过程'] },
  复流程图: { template: '分析【事件】的原因和结果。', slots: ['事件'] },
  桥型图: { template: '绘制对应关系为【对应关系】的桥型图。', slots: ['对应关系'] },
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
  const selectedChartType = ref<string>('选择图示')
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

  // Actions
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
    if (type !== '选择图示') {
      freeInputValue.value = ''
    }
  }

  function setTemplateSlot(slotName: string, value: string): void {
    templateSlots.value[slotName] = value
  }

  function clearTemplateSlots(): void {
    templateSlots.value = {}
  }

  function setFreeInputValue(value: string): void {
    freeInputValue.value = value
  }

  function hasValidSlots(): boolean {
    if (selectedChartType.value === '选择图示') {
      return freeInputValue.value.trim() !== ''
    }
    const template = DIAGRAM_TEMPLATES[selectedChartType.value]
    if (!template) return false
    return template.slots.every(
      (slot) => templateSlots.value[slot] && templateSlots.value[slot].trim() !== ''
    )
  }

  function getTemplateText(): string {
    if (selectedChartType.value === '选择图示') {
      return freeInputValue.value.trim()
    }
    const template = DIAGRAM_TEMPLATES[selectedChartType.value]
    if (!template) return ''

    let text = template.template
    for (const slot of template.slots) {
      text = text.replace(`【${slot}】`, templateSlots.value[slot] || slot)
    }
    return text
  }

  function reset(): void {
    theme.value = 'light'
    language.value = 'zh'
    isMobile.value = false
    sidebarCollapsed.value = false
    currentMode.value = 'mindmate'
    selectedChartType.value = '选择图示'
    templateSlots.value = {}
    freeInputValue.value = ''
    localStorage.removeItem(THEME_KEY)
    localStorage.removeItem(LANGUAGE_KEY)
    applyTheme()
  }

  // Watch for system theme changes
  if (typeof window !== 'undefined') {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQuery.addEventListener('change', () => {
      if (theme.value === 'system') {
        applyTheme()
      }
    })
  }

  // Initialize
  initFromStorage()

  return {
    // State
    theme,
    language,
    isMobile,
    sidebarCollapsed,
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
    setCurrentMode,
    toggleMode,
    setSelectedChartType,
    setTemplateSlot,
    clearTemplateSlots,
    setFreeInputValue,
    hasValidSlots,
    getTemplateText,
    reset,
  }
})
