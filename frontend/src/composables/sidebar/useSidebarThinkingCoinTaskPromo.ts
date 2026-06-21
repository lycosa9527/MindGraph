/**
 * Rotates earn-task promos in the sidebar thinking-coin widget.
 */
import {
  type MaybeRefOrGetter,
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  toValue,
  watch,
} from 'vue'

import { formatThinkingCoinBalance } from '@/composables/auth/useThinkingCoins'
import { useLanguage } from '@/composables/core/useLanguage'

import {
  SIDEBAR_TASK_PROMO_ROTATE_MS,
  buildSidebarPromoSlides,
  formatThinkingCoinTaskPromoTitle,
  nextThinkingCoinPromoIndex,
  pickInitialThinkingCoinPromoIndex,
  resolveSidebarPromoSlide,
  shouldPickFreshThinkingCoinPromoIndex,
} from './sidebarThinkingCoinTaskPromo'
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

export function useSidebarThinkingCoinTaskPromo(
  tasksSource: MaybeRefOrGetter<ThinkingCoinEarnTask[]>,
  inviteLabel: MaybeRefOrGetter<string>
) {
  const { isZh } = useLanguage()

  const taskIndex = ref(0)
  let rotateInterval: ReturnType<typeof setInterval> | null = null

  const promoSlides = computed(() => buildSidebarPromoSlides(toValue(tasksSource)))

  const promoSlideSignature = computed(() =>
    promoSlides.value.map((slide) => slide.key).join('|')
  )

  const currentSlide = computed(() =>
    resolveSidebarPromoSlide(promoSlides.value, taskIndex.value)
  )

  const promoTitle = computed(() => {
    const slide = currentSlide.value
    if (!slide) {
      return ''
    }
    if (slide.kind === 'invite') {
      return toValue(inviteLabel)
    }
    return formatThinkingCoinTaskPromoTitle(slide.task, isZh.value)
  })

  const promoReward = computed(() => {
    const slide = currentSlide.value
    if (!slide || slide.kind === 'invite') {
      return ''
    }
    return formatThinkingCoinBalance(slide.task.reward_amount)
  })

  const showInviteAccent = computed(() => currentSlide.value?.kind === 'invite')

  const taskPromoKey = computed(() => currentSlide.value?.key ?? 'empty')

  const hasPromo = computed(() => promoSlides.value.length > 0)

  function clearRotateInterval(): void {
    if (rotateInterval != null) {
      clearInterval(rotateInterval)
      rotateInterval = null
    }
  }

  function advanceTaskPromo(): void {
    if (promoSlides.value.length <= 1) {
      return
    }
    taskIndex.value = nextThinkingCoinPromoIndex(taskIndex.value, promoSlides.value.length)
  }

  function startRotateInterval(): void {
    clearRotateInterval()
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
      return
    }
    if (promoSlides.value.length <= 1) {
      return
    }
    rotateInterval = setInterval(() => {
      advanceTaskPromo()
    }, SIDEBAR_TASK_PROMO_ROTATE_MS)
  }

  function handleVisibilityChange(): void {
    if (typeof document === 'undefined') {
      return
    }
    if (document.visibilityState === 'hidden') {
      clearRotateInterval()
      return
    }
    startRotateInterval()
  }

  watch(
    promoSlideSignature,
    (signature, previousSignature) => {
      const slides = promoSlides.value
      if (slides.length <= 1) {
        taskIndex.value = 0
        clearRotateInterval()
        return
      }
      if (
        shouldPickFreshThinkingCoinPromoIndex(previousSignature, slides.length) ||
        taskIndex.value >= slides.length
      ) {
        taskIndex.value = pickInitialThinkingCoinPromoIndex(slides.length)
      }
      startRotateInterval()
    },
    { immediate: true }
  )

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange)
    clearRotateInterval()
  })

  return {
    promoTitle,
    promoReward,
    taskPromoKey,
    showInviteAccent,
    hasPromo,
  }
}
