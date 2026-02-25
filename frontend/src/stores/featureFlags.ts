/**
 * Feature Flags Store
 * Provides feature flags that can be accessed from router guards and components
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

import { apiRequest } from '@/utils/apiClient'

interface FeatureFlagsResponse {
  feature_rag_chunk_test: boolean
  feature_course: boolean
  feature_template: boolean
  feature_community: boolean
  feature_askonce: boolean
  feature_school_zone: boolean
  feature_debateverse: boolean
  feature_knowledge_space: boolean
  feature_library: boolean
  feature_smart_response: boolean
  feature_teacher_usage: boolean
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
          feature_course: false,
          feature_template: false,
          feature_community: false,
          feature_askonce: true,
          feature_school_zone: false,
          feature_debateverse: false,
          feature_knowledge_space: false,
          feature_library: false,
          feature_smart_response: false,
          feature_teacher_usage: false,
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
        feature_course: false,
        feature_template: false,
        feature_community: false,
        feature_askonce: true,
        feature_school_zone: false,
        feature_debateverse: false,
        feature_knowledge_space: false,
        feature_library: false,
        feature_smart_response: false,
        feature_teacher_usage: false,
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

  function getFeatureCourse(): boolean {
    return flags.value?.feature_course ?? false
  }

  function getFeatureTemplate(): boolean {
    return flags.value?.feature_template ?? true
  }

  function getFeatureCommunity(): boolean {
    return flags.value?.feature_community ?? true
  }

  function getFeatureAskOnce(): boolean {
    return flags.value?.feature_askonce ?? true
  }

  function getFeatureSchoolZone(): boolean {
    return flags.value?.feature_school_zone ?? true
  }

  function getFeatureDebateverse(): boolean {
    return flags.value?.feature_debateverse ?? false
  }

  function getFeatureKnowledgeSpace(): boolean {
    return flags.value?.feature_knowledge_space ?? false
  }

  function getFeatureLibrary(): boolean {
    return flags.value?.feature_library ?? false
  }

  function getFeatureSmartResponse(): boolean {
    return flags.value?.feature_smart_response ?? false
  }

  function getFeatureTeacherUsage(): boolean {
    return flags.value?.feature_teacher_usage ?? false
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
    getFeatureCourse,
    getFeatureTemplate,
    getFeatureCommunity,
    getFeatureAskOnce,
    getFeatureSchoolZone,
    getFeatureDebateverse,
    getFeatureKnowledgeSpace,
    getFeatureLibrary,
    getFeatureSmartResponse,
    getFeatureTeacherUsage,
    init,
  }
})
