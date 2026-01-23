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

  return {
    featureRagChunkTest,
    isLoading,
    error,
  }
}
