/**
 * Feature Flags Store
 * Provides feature flags that can be accessed from router guards and components
 */
import { ref } from 'vue'

import { defineStore } from 'pinia'

import { apiRequest } from '@/utils/apiClient'
import { maybeReloadForVodCsp } from '@/utils/vodCspDocument'

export interface FeatureOrgAccessEntry {
  restrict: boolean
  organization_ids: number[]
  user_ids: number[]
}

interface FeatureFlagsResponse {
  external_base_url: string
  feature_rag_chunk_test: boolean
  feature_showcase: boolean
  feature_zhihui: boolean
  feature_knowledge_space: boolean
  feature_mind_classroom_slide_deck?: boolean
  feature_library: boolean
  feature_smart_response: boolean
  feature_teacher_usage: boolean
  feature_workshop_chat: boolean
  feature_mindmate_collab: boolean
  feature_training?: boolean
  feature_vod?: boolean
  feature_student_learning_space?: boolean
  feature_markets: boolean
  feature_mindbot: boolean
  feature_mindmate_export: boolean
  feature_kitty_agent: boolean
  feature_auth_pixel_battle: boolean
  feature_test_server_banner: boolean
  feature_wechat_login: boolean
  feature_dingtalk_login: boolean
  feature_word_addin: boolean
  feature_thinking_coins: boolean
  captcha_provider?: 'legacy' | 'tsec'
  tencent_captcha_app_id?: string
  workshop_chat_preview_org_ids: number[]
  feature_org_access: Record<string, FeatureOrgAccessEntry>
}

export const useFeatureFlagsStore = defineStore('featureFlags', () => {
  // Cached feature flags (can be accessed synchronously)
  const flags = ref<FeatureFlagsResponse | null>(null)
  const isLoading = ref(false)
  const lastFetchTime = ref<number>(0)
  const CACHE_DURATION = 60 * 1000 // 1 minute — keep nav close to admin hot toggles
  let fetchFlagsPromise: Promise<FeatureFlagsResponse> | null = null
  /** Bumped by markStale so in-flight completions cannot re-mark a stale cache as fresh. */
  let staleEpoch = 0

  function defaultFeatureFlags(): FeatureFlagsResponse {
    return {
      external_base_url: '',
      feature_rag_chunk_test: false,
      feature_showcase: false,
      feature_zhihui: false,
      feature_knowledge_space: false,
      feature_mind_classroom_slide_deck: true,
      feature_library: false,
      feature_smart_response: false,
      feature_teacher_usage: false,
      feature_workshop_chat: false,
      feature_mindmate_collab: false,
      feature_training: false,
      feature_vod: false,
      feature_student_learning_space: true,
      feature_markets: false,
      feature_mindbot: false,
      feature_mindmate_export: false,
      feature_kitty_agent: true,
      feature_auth_pixel_battle: false,
      feature_test_server_banner: false,
      feature_wechat_login: false,
      feature_dingtalk_login: false,
      feature_word_addin: false,
      feature_thinking_coins: false,
      captcha_provider: 'legacy',
      tencent_captcha_app_id: '',
      workshop_chat_preview_org_ids: [],
      feature_org_access: {},
    }
  }

  function isFlagsCacheFresh(now: number = Date.now()): boolean {
    return Boolean(flags.value && now - lastFetchTime.value < CACHE_DURATION)
  }

  /**
   * Fetch feature flags directly (for use in router guards)
   * Uses cache if available and not stale; concurrent callers share one in-flight request.
   * If markStale() runs during an in-flight fetch, waiters re-fetch after it settles.
   */
  async function fetchFlags(): Promise<FeatureFlagsResponse> {
    if (isFlagsCacheFresh()) {
      const cached = flags.value as FeatureFlagsResponse
      return cached
    }

    if (fetchFlagsPromise) {
      const shared = await fetchFlagsPromise
      // markStale during the shared fetch leaves lastFetchTime at 0 — refetch below.
      if (isFlagsCacheFresh()) {
        return flags.value ?? shared
      }
    }

    if (fetchFlagsPromise) {
      return fetchFlagsPromise
    }

    const epochAtStart = staleEpoch
    fetchFlagsPromise = (async () => {
      isLoading.value = true
      try {
        const response = await apiRequest('/api/config/features')
        const fetchedAt = Date.now()

        if (!response.ok) {
          // Default to all features disabled if endpoint is not available.
          // Do not mark cache fresh — a backend restart must not hide toggles for 60s.
          const defaultFlags = defaultFeatureFlags()
          flags.value = defaultFlags
          lastFetchTime.value = 0
          return defaultFlags
        }

        const raw = (await response.json()) as FeatureFlagsResponse
        const data: FeatureFlagsResponse = {
          ...raw,
          feature_org_access: raw.feature_org_access ?? {},
          feature_mindmate_collab: raw.feature_mindmate_collab ?? false,
          feature_training: raw.feature_training ?? false,
          feature_vod: raw.feature_vod ?? false,
          feature_student_learning_space: raw.feature_student_learning_space ?? true,
          feature_markets: raw.feature_markets ?? false,
          feature_mindbot: raw.feature_mindbot ?? false,
          feature_mindmate_export: raw.feature_mindmate_export ?? false,
          feature_kitty_agent: true,
          feature_auth_pixel_battle: raw.feature_auth_pixel_battle ?? false,
          feature_test_server_banner: raw.feature_test_server_banner ?? false,
          feature_wechat_login: raw.feature_wechat_login ?? false,
          feature_dingtalk_login: raw.feature_dingtalk_login ?? false,
          feature_word_addin: raw.feature_word_addin ?? false,
          feature_thinking_coins: raw.feature_thinking_coins ?? false,
          captcha_provider: raw.captcha_provider === 'tsec' ? 'tsec' : 'legacy',
          tencent_captcha_app_id: raw.tencent_captcha_app_id ?? '',
          feature_mind_classroom_slide_deck: true,
        }
        flags.value = data
        lastFetchTime.value = epochAtStart === staleEpoch ? fetchedAt : 0
        maybeReloadForVodCsp(data.feature_vod ?? false)
        return data
      } catch (error) {
        console.error('[FeatureFlags] Fetch error:', error)
        // Return cached flags or defaults on error
        if (flags.value) {
          return flags.value
        }
        const defaultFlags = defaultFeatureFlags()
        flags.value = defaultFlags
        return defaultFlags
      } finally {
        isLoading.value = false
        fetchFlagsPromise = null
      }
    })()

    const result = await fetchFlagsPromise
    if (isFlagsCacheFresh()) {
      return flags.value ?? result
    }
    // Own fetch was invalidated by markStale — one follow-up fetch.
    if (epochAtStart !== staleEpoch) {
      return fetchFlags()
    }
    return flags.value ?? result
  }

  /**
   * Get feature flag value synchronously (returns cached value or default)
   * For router guards - call fetchFlags() first if you need fresh data
   */
  function getFeatureRagChunkTest(): boolean {
    return flags.value?.feature_rag_chunk_test ?? false
  }

  function getFeatureShowcase(): boolean {
    return flags.value?.feature_showcase ?? false
  }

  function getFeatureZhihui(): boolean {
    return flags.value?.feature_zhihui ?? false
  }

  function getFeatureKnowledgeSpace(): boolean {
    return flags.value?.feature_knowledge_space ?? false
  }

  function getFeatureMindClassroomSlideDeck(): boolean {
    return true
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

  function getFeatureWorkshopChat(): boolean {
    return flags.value?.feature_workshop_chat ?? false
  }

  function getFeatureMindmateCollab(): boolean {
    return flags.value?.feature_mindmate_collab ?? false
  }

  function getFeatureTraining(): boolean {
    return flags.value?.feature_training ?? false
  }

  function getFeatureVod(): boolean {
    return flags.value?.feature_vod ?? false
  }

  function getFeatureStudentLearningSpace(): boolean {
    return flags.value?.feature_student_learning_space ?? true
  }

  /** True after a successful /api/config/features response (not the all-off fallback). */
  function hasLiveFeatureFlags(): boolean {
    return lastFetchTime.value > 0
  }

  function getFeatureMarkets(): boolean {
    return flags.value?.feature_markets ?? false
  }

  function getFeatureMindbot(): boolean {
    return flags.value?.feature_mindbot ?? false
  }

  function getWorkshopChatPreviewOrgIds(): number[] {
    return flags.value?.workshop_chat_preview_org_ids ?? []
  }

  function getFeatureKittyAgent(): boolean {
    return true
  }

  function getFeatureAuthPixelBattle(): boolean {
    return flags.value?.feature_auth_pixel_battle ?? false
  }

  function getFeatureTestServerBanner(): boolean {
    return flags.value?.feature_test_server_banner ?? false
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
    staleEpoch += 1
  }

  return {
    flags,
    isLoading,
    fetchFlags,
    getFeatureRagChunkTest,
    getFeatureShowcase,
    getFeatureZhihui,
    getFeatureKnowledgeSpace,
    getFeatureMindClassroomSlideDeck,
    getFeatureLibrary,
    getFeatureSmartResponse,
    getFeatureTeacherUsage,
    getFeatureWorkshopChat,
    getFeatureMindmateCollab,
    getFeatureTraining,
    getFeatureVod,
    getFeatureStudentLearningSpace,
    hasLiveFeatureFlags,
    getFeatureMarkets,
    getFeatureMindbot,
    getFeatureKittyAgent,
    getFeatureAuthPixelBattle,
    getFeatureTestServerBanner,
    getWorkshopChatPreviewOrgIds,
    init,
    markStale,
  }
})
