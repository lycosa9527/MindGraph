/**
 * Canvas AI content audience level (UI preference).
 * Persisted locally; not yet sent to generation APIs.
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import {
  DEFAULT_AI_CONTENT_LEVEL,
  loadAiContentLevelGuideSeen,
  loadAiContentLevelPreference,
  loadGeneratedLevelsByDiagram,
  saveAiContentLevelGuideSeen,
  saveAiContentLevelPreference,
  saveGeneratedLevelsByDiagram,
  type AiContentLevelId,
} from '@/config/aiContentLevels'

export const useAiContentLevelStore = defineStore('aiContentLevel', () => {
  const initial = loadAiContentLevelPreference()
  const level = ref<AiContentLevelId>(initial.level)
  const userSet = ref(initial.userSet)
  const guideSeen = ref(loadAiContentLevelGuideSeen())
  const generatedLevelByDiagram = ref<Record<string, AiContentLevelId>>(loadGeneratedLevelsByDiagram())

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

  /** Record which audience level was active when AI last generated for this diagram. */
  function markDiagramGenerated(diagramKey: string, atLevel: AiContentLevelId = level.value): void {
    if (!diagramKey) return
    generatedLevelByDiagram.value = {
      ...generatedLevelByDiagram.value,
      [diagramKey]: atLevel,
    }
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
    getGeneratedLevel,
    markDiagramGenerated,
  }
})
