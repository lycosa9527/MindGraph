/**
 * Feature Flags Store
 * Provides feature flags that can be accessed from router guards and components
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

import { apiRequest } from '@/utils/apiClient'

export interface FeatureOrgAccessEntry {
  restrict: boolean
  organization_ids: number[]
  user_ids: number[]
}

interface FeatureFlagsResponse {
  external_base_url: string
  feature_rag_chunk_test: boolean
  feature_course: boolean
  feature_template: boolean
  feature_community: boolean
  feature_askonce: boolean
  feature_school_zone: boolean
  feature_debateverse: boolean
  feature_knowledge_space: boolean
  feature_library: boolean
  feature_gewe: boolean
  feature_smart_response: boolean
  feature_teacher_usage: boolean
  feature_workshop_chat: boolean
  workshop_chat_preview_org_ids: number[]
  feature_org_access: Record<string, FeatureOrgAccessEntry>
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
          external_base_url: '',
          feature_rag_chunk_test: false,
          feature_course: false,
          feature_template: false,
          feature_community: false,
          feature_askonce: true,
          feature_school_zone: false,
          feature_debateverse: false,
          feature_knowledge_space: false,
          feature_library: false,
          feature_gewe: false,
          feature_smart_response: false,
          feature_teacher_usage: false,
          feature_workshop_chat: false,
          workshop_chat_preview_org_ids: [],
          feature_org_access: {},
        }
        flags.value = defaultFlags
        lastFetchTime.value = now
        return defaultFlags
      }

      const raw = (await response.json()) as FeatureFlagsResponse
      const data: FeatureFlagsResponse = {
        ...raw,
        feature_org_access: raw.feature_org_access ?? {},
      }
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
        external_base_url: '',
        feature_rag_chunk_test: false,
        feature_course: false,
        feature_template: false,
        feature_community: false,
        feature_askonce: true,
        feature_school_zone: false,
        feature_debateverse: false,
        feature_knowledge_space: false,
        feature_library: false,
        feature_gewe: false,
        feature_smart_response: false,
        feature_teacher_usage: false,
        feature_workshop_chat: false,
        workshop_chat_preview_org_ids: [],
        feature_org_access: {},
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

  function getFeatureGewe(): boolean {
    return flags.value?.feature_gewe ?? false
  }

  function getFeatureSmartResponse(): boolean {
    return flags.value?.feature_smart_response ?? false
  }

  function getFeatureTeacherUsage(): boolean {
    return flags.value?.feature_teacher_usage ?? false
  }

  function getFeatureWorkshopChat(): boolean {
    return flags.value?.feature_workshop_chat ?? false
  }

  function getWorkshopChatPreviewOrgIds(): number[] {
    return flags.value?.workshop_chat_preview_org_ids ?? []
  }

  /**
   * Initialize flags (call this early in app lifecycle)
   */
  async function init(): Promise<void> {
    if (!flags.value) {
      await fetchFlags()
    }
  }

  function markStale(): void {
    lastFetchTime.value = 0
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
    getFeatureGewe,
    getFeatureSmartResponse,
    getFeatureTeacherUsage,
    getFeatureWorkshopChat,
    getWorkshopChatPreviewOrgIds,
    init,
    markStale,
  }
})
