import { defineAsyncComponent, type Component } from 'vue'

import type { TrainingPageKey } from '@/config/trainingPages'

const LIVE_PAGES: Partial<Record<TrainingPageKey, Component>> = {
  auth: defineAsyncComponent(() => import('@/pages/AuthPage.vue')),
  mindgraph: defineAsyncComponent(
    () => import('@/components/mindgraph/MindGraphContainer.vue')
  ),
  mindmate: defineAsyncComponent(() => import('@/pages/MindMatePage.vue')),
  askonce: defineAsyncComponent(() => import('@/pages/AskOncePage.vue')),
  maite: defineAsyncComponent(() => import('@/pages/MaiteLearningPage.vue')),
  debateverse: defineAsyncComponent(() => import('@/pages/DebateVersePage.vue')),
  zhihui: defineAsyncComponent(() => import('@/pages/ZhiHuiPage.vue')),
  library: defineAsyncComponent(() => import('@/pages/LibraryPage.vue')),
  template: defineAsyncComponent(() => import('@/pages/TemplatePage.vue')),
  course: defineAsyncComponent(() => import('@/pages/CoursePage.vue')),
  knowledge: defineAsyncComponent(() => import('@/pages/KnowledgeSpacePage.vue')),
  showcase: defineAsyncComponent(() => import('@/pages/ShowcasePage.vue')),
  community: defineAsyncComponent(() => import('@/pages/CommunityPage.vue')),
  'voice-notes': defineAsyncComponent(() => import('@/pages/VoiceNotesPage.vue')),
  'thinking-coins': defineAsyncComponent(
    () => import('@/pages/ThinkingCoinsUpgradePage.vue')
  ),
}

export function trainingLivePage(key: string | null | undefined): Component | null {
  if (!key) return null
  return LIVE_PAGES[key as TrainingPageKey] ?? null
}

export function hasTrainingLivePreview(key: string | null | undefined): boolean {
  return Boolean(trainingLivePage(key)) || key === 'canvas'
}
