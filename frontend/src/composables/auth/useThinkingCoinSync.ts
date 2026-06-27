/**
 * Apply thinking coin mutation payloads from API/SSE to auth store and event bus.
 */
import { eventBus } from '@/composables/core/useEventBus'
import { useAuthStore } from '@/stores/auth'
import type { ThinkingCoinEarnTask, ThinkingCoinMutationPayload } from '@/types/thinkingCoins'

export function patchEarnTasksFromMutation(
  tasks: ThinkingCoinEarnTask[],
  payload: ThinkingCoinMutationPayload
): ThinkingCoinEarnTask[] {
  const completedSlugs = payload.completed_slugs_today
  if (!completedSlugs?.length) {
    return tasks
  }
  const completed = new Set(completedSlugs)
  return tasks.map((task) => {
    if (!completed.has(task.slug)) {
      return task
    }
    return { ...task, completed_today: true }
  })
}

export function applyThinkingCoinMutation(payload: ThinkingCoinMutationPayload | null | undefined): void {
  if (!payload?.eligible) {
    return
  }

  const authStore = useAuthStore()
  authStore.patchThinkingCoinsSummary({
    balance: payload.balance,
    eligible: true,
  })

  eventBus.emit('thinking_coins:mutation', payload)
}

export function extractThinkingCoinsFooter(
  body: Record<string, unknown> | null | undefined
): ThinkingCoinMutationPayload | null {
  if (!body || typeof body !== 'object') {
    return null
  }
  const raw = body.thinking_coins
  if (!raw || typeof raw !== 'object') {
    return null
  }
  const footer = raw as Record<string, unknown>
  if (footer.eligible !== true) {
    return null
  }
  return {
    eligible: true,
    balance: Number(footer.balance ?? 0),
    credited: Number(footer.credited ?? 0),
    debited: Number(footer.debited ?? 0),
    task_slug: typeof footer.task_slug === 'string' ? footer.task_slug : null,
    earn_events: Array.isArray(footer.earn_events)
      ? (footer.earn_events as Array<{ slug: string; amount: number }>)
      : [],
    completed_slugs_today: Array.isArray(footer.completed_slugs_today)
      ? (footer.completed_slugs_today as string[])
      : [],
  }
}

export function useThinkingCoinSync(): {
  applyThinkingCoinMutation: typeof applyThinkingCoinMutation
} {
  return {
    applyThinkingCoinMutation,
  }
}
