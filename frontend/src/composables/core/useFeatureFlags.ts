/**
 * Feature Flags Composable
 *
 * Provides reactive access to feature flags using vue-query.
 * Use this in Vue components (setup functions).
 * For router guards, use useFeatureFlagsStore().fetchFlags() directly.
 *
 * Prefer Pinia `store.flags` over vue-query `data`: the store is updated by
 * markStale()+fetchFlags() immediately, while vue-query can keep a failed
 * default payload for staleTime and hide UI gated on hot toggles (e.g. auth
 * teacher/student tabs).
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
    staleTime: 60 * 1000, // 1 minute — align with store cache for hot toggles
    retry: 1,
  })

  const live = computed(() => store.flags ?? data.value ?? null)

  const featureRagChunkTest = computed(() => live.value?.feature_rag_chunk_test ?? false)
  const featureCourse = computed(() => live.value?.feature_course ?? false)
  const featureMateLearning = computed(() => live.value?.feature_mate_learning ?? false)
  const featureTemplate = computed(() => live.value?.feature_template ?? false)
  const featureCommunity = computed(() => live.value?.feature_community ?? false)
  const featureShowcase = computed(() => live.value?.feature_showcase ?? false)
  const featureZhihui = computed(() => live.value?.feature_zhihui ?? false)
  const featureAskOnce = computed(() => live.value?.feature_askonce ?? false)
  const featureDebateverse = computed(() => live.value?.feature_debateverse ?? false)
  const featureKnowledgeSpace = computed(() => live.value?.feature_knowledge_space ?? false)
  const featureMindmapV2Canvas = computed(() => live.value?.feature_mindmap_v2_canvas ?? true)
  const featureMindClassroomSlideDeck = computed(
    () => live.value?.feature_mind_classroom_slide_deck ?? false
  )
  const featureLibrary = computed(() => live.value?.feature_library ?? false)
  const featureGewe = computed(() => live.value?.feature_gewe ?? false)
  const featureSmartResponse = computed(() => live.value?.feature_smart_response ?? false)
  const featureTeacherUsage = computed(() => live.value?.feature_teacher_usage ?? false)
  const featureWorkshopChat = computed(() => live.value?.feature_workshop_chat ?? false)
  const featureMindmateCollab = computed(() => live.value?.feature_mindmate_collab ?? false)
  const featureTraining = computed(() => live.value?.feature_training ?? false)
  const featureVod = computed(() => live.value?.feature_vod ?? false)
  const featureStudentLearningSpace = computed(
    () => live.value?.feature_student_learning_space ?? false,
  )
  const featureMarkets = computed(() => live.value?.feature_markets ?? false)
  const featureMindbot = computed(() => live.value?.feature_mindbot ?? false)
  const featureWechatLogin = computed(() => live.value?.feature_wechat_login ?? false)
  const featureDingtalkLogin = computed(() => live.value?.feature_dingtalk_login ?? false)
  const featureWordAddin = computed(() => live.value?.feature_word_addin ?? false)
  const featureMindmateExport = computed(() => live.value?.feature_mindmate_export ?? false)
  const featureKittyAgent = computed(() => live.value?.feature_kitty_agent ?? false)
  const featureThinkingCoins = computed(() => live.value?.feature_thinking_coins ?? false)
  const workshopChatPreviewOrgIds = computed(() => live.value?.workshop_chat_preview_org_ids ?? [])
  const featureOrgAccess = computed(() => live.value?.feature_org_access ?? {})
  const captchaProvider = computed(() => live.value?.captcha_provider ?? 'legacy')
  const tencentCaptchaAppId = computed(() => live.value?.tencent_captcha_app_id ?? '')

  return {
    featureRagChunkTest,
    featureCourse,
    featureMateLearning,
    featureTemplate,
    featureCommunity,
    featureShowcase,
    featureZhihui,
    featureAskOnce,
    featureDebateverse,
    featureKnowledgeSpace,
    featureMindmapV2Canvas,
    featureMindClassroomSlideDeck,
    featureLibrary,
    featureGewe,
    featureSmartResponse,
    featureTeacherUsage,
    featureWorkshopChat,
    featureMindmateCollab,
    featureTraining,
    featureVod,
    featureStudentLearningSpace,
    featureMarkets,
    featureMindbot,
    featureWechatLogin,
    featureDingtalkLogin,
    featureWordAddin,
    featureMindmateExport,
    featureKittyAgent,
    featureThinkingCoins,
    workshopChatPreviewOrgIds,
    featureOrgAccess,
    captchaProvider,
    tencentCaptchaAppId,
    isLoading,
    error,
  }
}
