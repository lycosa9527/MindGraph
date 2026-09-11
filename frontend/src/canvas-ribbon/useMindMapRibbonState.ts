/**
 * Ribbon height + last tab. Account default in Postgres; no browser storage.
 * File is a destination tab and is never persisted as the landing tab.
 */
import { onUnmounted, ref, watch } from 'vue'

import { useAuthStore } from '@/stores'
import { authFetch } from '@/utils/api'

import {
  DEFAULT_MIND_MAP_RIBBON_TAB,
  type MindMapRibbonTabId,
  resolveLandingMindMapRibbonTab,
} from './mindMapRibbonTypes'

const API_PATH = '/api/auth/diagram-preferences'
const PERSIST_DEBOUNCE_MS = 400

export function useMindMapRibbonState() {
  const authStore = useAuthStore()
  const classic = ref(false)
  const activeTab = ref<MindMapRibbonTabId>(DEFAULT_MIND_MAP_RIBBON_TAB)
  let persistTimer = 0
  let persistInFlight = false

  function hydrateFromUser(): void {
    const user = authStore.user
    if (!user) {
      classic.value = false
      activeTab.value = DEFAULT_MIND_MAP_RIBBON_TAB
      return
    }
    classic.value = user.v3RibbonClassic === true
    activeTab.value = resolveLandingMindMapRibbonTab(user.v3RibbonTab)
  }

  hydrateFromUser()

  watch(
    () => [authStore.user?.id, authStore.user?.v3RibbonClassic, authStore.user?.v3RibbonTab],
    () => {
      if (persistInFlight || persistTimer !== 0) return
      hydrateFromUser()
    }
  )

  function tabToPersist(): MindMapRibbonTabId {
    if (activeTab.value !== 'file') return activeTab.value
    return resolveLandingMindMapRibbonTab(authStore.user?.v3RibbonTab)
  }

  function patchAuthUser(nextClassic: boolean, nextTab: MindMapRibbonTabId): void {
    if (!authStore.user) return
    authStore.patchPersistedUser({
      v3RibbonClassic: nextClassic,
      v3RibbonTab: nextTab,
    })
  }

  async function persistNow(): Promise<void> {
    if (!authStore.isAuthenticated) return
    persistInFlight = true
    const landingTab = tabToPersist()
    try {
      const response = await authFetch(API_PATH, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          v3_ribbon_classic: classic.value,
          v3_ribbon_tab: landingTab,
        }),
      })
      if (!response.ok) return
      const data = (await response.json().catch(() => ({}))) as {
        v3_ribbon_classic?: boolean
        v3_ribbon_tab?: string | null
      }
      const savedClassic = data.v3_ribbon_classic === true
      const savedTab = resolveLandingMindMapRibbonTab(data.v3_ribbon_tab)
      classic.value = savedClassic
      if (activeTab.value !== 'file') {
        activeTab.value = savedTab
      }
      patchAuthUser(savedClassic, savedTab)
    } finally {
      persistInFlight = false
    }
  }

  function schedulePersist(): void {
    if (!authStore.isAuthenticated) return
    if (persistTimer !== 0) {
      window.clearTimeout(persistTimer)
    }
    persistTimer = window.setTimeout(() => {
      persistTimer = 0
      void persistNow()
    }, PERSIST_DEBOUNCE_MS)
  }

  function setClassic(next: boolean): void {
    if (classic.value === next) return
    classic.value = next
    patchAuthUser(next, tabToPersist())
    schedulePersist()
  }

  function toggleClassic(): void {
    setClassic(!classic.value)
  }

  function setActiveTab(tab: MindMapRibbonTabId): void {
    if (activeTab.value === tab) return
    activeTab.value = tab
    if (tab === 'file') return
    patchAuthUser(classic.value, tab)
    schedulePersist()
  }

  onUnmounted(() => {
    if (persistTimer !== 0) {
      window.clearTimeout(persistTimer)
      persistTimer = 0
      void persistNow()
    }
  })

  return {
    classic,
    activeTab,
    setClassic,
    toggleClassic,
    setActiveTab,
  }
}
