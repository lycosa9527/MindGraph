/**
 * Canvas AI content audience level (UI preference).
 * Persisted locally; not yet sent to generation APIs.
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import {
  type AiContentLevelId,
  DEFAULT_AI_CONTENT_LEVEL,
  loadAiContentLevelGuideSeen,
  loadAiContentLevelPreference,
  loadGeneratedLevelsByDiagram,
  saveAiContentLevelGuideSeen,
  saveAiContentLevelPreference,
  saveGeneratedLevelsByDiagram,
} from '@/config/aiContentLevels'

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

  function setLevel(next: AiContentLevelId): void {
    level.value = next
    userSet.value = true
    dismissGuide()
  }

  function reset(): void {
    level.value = DEFAULT_AI_CONTENT_LEVEL
    userSet.value = false
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
