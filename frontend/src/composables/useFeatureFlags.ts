/**
 * Feature Flags Composable
 *
 * Provides access to feature flags from the backend.
 */
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { apiRequest } from '@/utils/apiClient'

interface FeatureFlagsResponse {
  feature_rag_chunk_test: boolean
}

async function fetchFeatureFlags(): Promise<FeatureFlagsResponse> {
  const response = await apiRequest('/api/config/features')

  if (!response.ok) {
    // Default to all features disabled if endpoint is not available
    return {
      feature_rag_chunk_test: false,
    }
  }

  return await response.json()
}

export function useFeatureFlags() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['featureFlags'],
    queryFn: fetchFeatureFlags,
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
