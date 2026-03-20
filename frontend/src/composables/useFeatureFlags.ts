/**
 * Feature Flags Composable
 *
 * Provides reactive access to feature flags using vue-query.
 * Use this in Vue components (setup functions).
 * For router guards, use useFeatureFlagsStore().fetchFlags() directly.
 */
import { computed } from 'vue'

import { useQuery } from '@tanstack/vue-query'

import { useFeatureFlagsStore } from '@/stores/featureFlags'

export function useFeatureFlags() {
  const store = useFeatureFlagsStore()

  // Use vue-query for reactivity in components
  // The query function uses the store's fetchFlags to share cache
  const { data, isLoading, error } = useQuery({
    queryKey: ['featureFlags'],
    queryFn: () => store.fetchFlags(),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    retry: 1,
  })

  const featureRagChunkTest = computed(() => data.value?.feature_rag_chunk_test ?? false)
  const featureCourse = computed(() => data.value?.feature_course ?? false)
  const featureTemplate = computed(() => data.value?.feature_template ?? false)
  const featureCommunity = computed(() => data.value?.feature_community ?? false)
  const featureAskOnce = computed(() => data.value?.feature_askonce ?? true)
  const featureSchoolZone = computed(() => data.value?.feature_school_zone ?? false)
  const featureDebateverse = computed(() => data.value?.feature_debateverse ?? false)
  const featureKnowledgeSpace = computed(() => data.value?.feature_knowledge_space ?? false)
  const featureLibrary = computed(() => data.value?.feature_library ?? false)
  const featureGewe = computed(() => data.value?.feature_gewe ?? false)
  const featureSmartResponse = computed(() => data.value?.feature_smart_response ?? false)
  const featureTeacherUsage = computed(() => data.value?.feature_teacher_usage ?? false)
  const featureWorkshopChat = computed(() => data.value?.feature_workshop_chat ?? false)
  const workshopChatPreviewOrgIds = computed(
    () => data.value?.workshop_chat_preview_org_ids ?? [],
  )

  return {
    featureRagChunkTest,
    featureCourse,
    featureTemplate,
    featureCommunity,
    featureAskOnce,
    featureSchoolZone,
    featureDebateverse,
    featureKnowledgeSpace,
    featureLibrary,
    featureGewe,
    featureSmartResponse,
    featureTeacherUsage,
    featureWorkshopChat,
    workshopChatPreviewOrgIds,
    isLoading,
    error,
  }
}
