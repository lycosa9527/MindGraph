/**
 * Feature Flags Store
 * Provides feature flags that can be accessed from router guards and components
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

import { apiRequest } from '@/utils/apiClient'

interface FeatureFlagsResponse {
  feature_rag_chunk_test: boolean
}

export const useFeatureFlagsStore = defineStore('featureFlags', () => {
  // Cached feature flags (can be accessed synchronously)
  const flags = ref<FeatureFlagsResponse | null>(null)
  const isLoading = ref(false)
  const lastFetchTime = ref<number>(0)
  const CACHE_DURATION = 5 * 60 * 1000 // 5 minutes

  /**
   * Fetch feature flags directly (for use in router guards)
   * Uses cache if available and not stale
   */
  async function fetchFlags(): Promise<FeatureFlagsResponse> {
    const now = Date.now()

    // Return cached flags if still fresh
    if (flags.value && now - lastFetchTime.value < CACHE_DURATION) {
      return flags.value
    }

    isLoading.value = true
    try {
      const response = await apiRequest('/api/config/features')

      if (!response.ok) {
        // Default to all features disabled if endpoint is not available
        const defaultFlags: FeatureFlagsResponse = {
          feature_rag_chunk_test: false,
        }
        flags.value = defaultFlags
        lastFetchTime.value = now
        return defaultFlags
      }

      const data: FeatureFlagsResponse = await response.json()
      flags.value = data
      lastFetchTime.value = now
      return data
    } catch (error) {
      console.error('[FeatureFlags] Fetch error:', error)
      // Return cached flags or defaults on error
      if (flags.value) {
        return flags.value
      }
      const defaultFlags: FeatureFlagsResponse = {
        feature_rag_chunk_test: false,
      }
      flags.value = defaultFlags
      return defaultFlags
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Get feature flag value synchronously (returns cached value or default)
   * For router guards - call fetchFlags() first if you need fresh data
   */
  function getFeatureRagChunkTest(): boolean {
    return flags.value?.feature_rag_chunk_test ?? false
  }

  /**
   * Initialize flags (call this early in app lifecycle)
   */
  async function init(): Promise<void> {
    if (!flags.value) {
      await fetchFlags()
    }
  }

  return {
    flags,
    isLoading,
    fetchFlags,
    getFeatureRagChunkTest,
    init,
  }
})
