/**
 * Canvas AI content audience level (UI preference).
 * Guests use localStorage; signed-in users persist to Postgres via
 * ``PATCH /api/auth/diagram-preferences`` (``ai_content_level``).
 * Mind-map generate reads this via ``resolveMindMapAudienceInstructions``.
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import { notify } from '@/composables/core/notifications'
import {
  type AiContentLevelId,
  DEFAULT_AI_CONTENT_LEVEL,
  isAiContentLevelId,
  loadAiContentLevelGuideSeen,
  loadAiContentLevelPreference,
  loadGeneratedLevelsByDiagram,
  saveAiContentLevelGuideSeen,
  saveAiContentLevelPreference,
  saveGeneratedLevelsByDiagram,
} from '@/config/aiContentLevels'
import {
  isAiContentLevelAuthAuthenticated,
  patchAuthPersistedAiContentLevel,
} from '@/utils/aiContentLevelAuthBridge'

const API_PATH = '/api/auth/diagram-preferences'

export const useAiContentLevelStore = defineStore('aiContentLevel', () => {
  const initial = loadAiContentLevelPreference()
  const level = ref<AiContentLevelId>(initial.level)
  const userSet = ref(initial.userSet)
  const guideSeen = ref(loadAiContentLevelGuideSeen())
  const generatedLevelByDiagram = ref<Record<string, AiContentLevelId>>(
    loadGeneratedLevelsByDiagram()
  )
  const unsavedDiagramKey = ref(createUnsavedDiagramKey())

  /** Non-general levels are treated as an active audience constraint. */
  const activeLevel = computed(() =>
    level.value === DEFAULT_AI_CONTENT_LEVEL ? null : level.value
  )

  const isConstrained = computed(() => activeLevel.value !== null)

  /** Show first-run coach tip until the user dismisses it or picks a level. */
  const showFirstRunGuide = computed(() => !userSet.value && !guideSeen.value)

  watch([level, userSet], () => {
    saveAiContentLevelPreference({
      level: level.value,
      userSet: userSet.value,
    })
  })

  watch(
    generatedLevelByDiagram,
    (value) => {
      saveGeneratedLevelsByDiagram(value)
    },
    { deep: true }
  )

  function dismissGuide(): void {
    if (guideSeen.value) return
    guideSeen.value = true
    saveAiContentLevelGuideSeen(true)
  }

  function applyPreference(next: AiContentLevelId, explicit: boolean): void {
    level.value = next
    userSet.value = explicit
    if (explicit) {
      dismissGuide()
    }
  }

  function hydrateFromProfile(saved: string | null): void {
    if (isAiContentLevelId(saved)) {
      applyPreference(saved, true)
      return
    }
    applyPreference(DEFAULT_AI_CONTENT_LEVEL, false)
  }

  function hydrateFromLocal(): void {
    const stored = loadAiContentLevelPreference()
    applyPreference(stored.level, stored.userSet)
  }

  async function persistToServer(next: AiContentLevelId): Promise<boolean> {
    if (!isAiContentLevelAuthAuthenticated()) {
      return true
    }
    try {
      const response = await fetch(API_PATH, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ ai_content_level: next }),
      })
      const data = (await response.json().catch(() => ({}))) as {
        detail?: string
        ai_content_level?: string | null
      }
      if (!response.ok) {
        notify.error(typeof data.detail === 'string' ? data.detail : 'Failed to save preferences')
        return false
      }
      const saved = isAiContentLevelId(data.ai_content_level)
        ? data.ai_content_level
        : next
      patchAuthPersistedAiContentLevel(saved)
      return true
    } catch {
      notify.error('Failed to save preferences')
      return false
    }
  }

  async function setLevel(next: AiContentLevelId): Promise<boolean> {
    const previousLevel = level.value
    const previousUserSet = userSet.value
    applyPreference(next, true)
    const ok = await persistToServer(next)
    if (!ok && level.value === next) {
      applyPreference(previousLevel, previousUserSet)
      return false
    }
    return ok
  }

  function reset(): void {
    applyPreference(DEFAULT_AI_CONTENT_LEVEL, false)
  }

  function getGeneratedLevel(diagramKey: string): AiContentLevelId | null {
    return generatedLevelByDiagram.value[diagramKey] ?? null
  }

  function diagramKey(diagramId: string | null | undefined): string {
    return diagramId ? `diagram:${diagramId}` : unsavedDiagramKey.value
  }

  /** Record which audience level was active when AI last generated for this diagram. */
  function markDiagramGenerated(diagramKey: string, atLevel: AiContentLevelId = level.value): void {
    if (!diagramKey) return
    generatedLevelByDiagram.value = {
      ...generatedLevelByDiagram.value,
      [diagramKey]: atLevel,
    }
  }

  function migrateGeneratedLevel(fromKey: string, diagramId: string | null | undefined): void {
    if (!diagramId) return
    const levelAtGeneration = generatedLevelByDiagram.value[fromKey]
    const destinationKey = diagramKey(diagramId)
    if (!levelAtGeneration || fromKey === destinationKey) return
    const next = { ...generatedLevelByDiagram.value }
    delete next[fromKey]
    next[destinationKey] = levelAtGeneration
    generatedLevelByDiagram.value = next
  }

  function resetGeneratedLevelSession(): void {
    const next = { ...generatedLevelByDiagram.value }
    delete next[unsavedDiagramKey.value]
    generatedLevelByDiagram.value = next
    unsavedDiagramKey.value = createUnsavedDiagramKey()
  }

  return {
    level,
    userSet,
    guideSeen,
    showFirstRunGuide,
    activeLevel,
    isConstrained,
    setLevel,
    hydrateFromProfile,
    hydrateFromLocal,
    reset,
    dismissGuide,
    diagramKey,
    getGeneratedLevel,
    markDiagramGenerated,
    migrateGeneratedLevel,
    resetGeneratedLevelSession,
  }
})

function createUnsavedDiagramKey(): string {
  return `unsaved:${Date.now()}:${Math.random().toString(36).slice(2, 10)}`
}
