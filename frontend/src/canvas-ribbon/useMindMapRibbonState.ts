/**
 * Ribbon height + last tab. Account default in Postgres; no browser storage.
 */
import { onUnmounted, ref, watch } from 'vue'

import { useAuthStore } from '@/stores'
import { authFetch } from '@/utils/api'

import {
  DEFAULT_MIND_MAP_RIBBON_TAB,
  type MindMapRibbonTabId,
  normalizeMindMapRibbonTabId,
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
    activeTab.value = normalizeMindMapRibbonTabId(user.v3RibbonTab) ?? DEFAULT_MIND_MAP_RIBBON_TAB
  }

  hydrateFromUser()

  watch(
    () => [authStore.user?.id, authStore.user?.v3RibbonClassic, authStore.user?.v3RibbonTab],
    () => {
      if (persistInFlight || persistTimer !== 0) return
      hydrateFromUser()
    }
  )

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
    try {
      const response = await authFetch(API_PATH, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          v3_ribbon_classic: classic.value,
          v3_ribbon_tab: activeTab.value,
        }),
      })
      if (!response.ok) return
      const data = (await response.json().catch(() => ({}))) as {
        v3_ribbon_classic?: boolean
        v3_ribbon_tab?: string | null
      }
      const savedClassic = data.v3_ribbon_classic === true
      const savedTab = normalizeMindMapRibbonTabId(data.v3_ribbon_tab) ?? activeTab.value
      classic.value = savedClassic
      activeTab.value = savedTab
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
    patchAuthUser(next, activeTab.value)
    schedulePersist()
  }

  function toggleClassic(): void {
    setClassic(!classic.value)
  }

  function setActiveTab(tab: MindMapRibbonTabId): void {
    if (activeTab.value === tab) return
    activeTab.value = tab
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
