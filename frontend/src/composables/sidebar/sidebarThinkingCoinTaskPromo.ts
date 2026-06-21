/**
 * Pure helpers for sidebar thinking-coin task promo rotation.
 */
import type { ThinkingCoinEarnTask } from '@/types/thinkingCoins'

export const SIDEBAR_TASK_PROMO_ROTATE_MS = 5_000

export type SidebarPromoSlide =
  | { key: string; kind: 'task'; task: ThinkingCoinEarnTask }
  | { key: string; kind: 'invite' }

export function thinkingCoinPromoTaskPool(
  tasks: ThinkingCoinEarnTask[]
): ThinkingCoinEarnTask[] {
  if (tasks.length === 0) {
    return []
  }
  const pending = tasks.filter((task) => !task.completed_today)
  const completed = tasks.filter((task) => task.completed_today)
  if (pending.length > 0) {
    return [...pending, ...completed]
  }
  return tasks
}

export function taskIsReferralPromo(task: ThinkingCoinEarnTask): boolean {
  const slug = task.slug.toLowerCase()
  return slug.includes('referral') || slug.includes('invite')
}

/** Earn tasks plus a synthetic invite slide when no referral task exists. */
export function buildSidebarPromoSlides(tasks: ThinkingCoinEarnTask[]): SidebarPromoSlide[] {
  const pool = thinkingCoinPromoTaskPool(tasks)
  const slides: SidebarPromoSlide[] = pool.map((task) => ({
    key: `task-${task.id}`,
    kind: 'task',
    task,
  }))
  if (!pool.some(taskIsReferralPromo)) {
    slides.push({ key: 'invite', kind: 'invite' })
  }
  if (slides.length === 0) {
    return [{ key: 'invite', kind: 'invite' }]
  }
  return slides
}

export function nextThinkingCoinPromoIndex(current: number, length: number): number {
  if (length <= 0) {
    return 0
  }
  return (current + 1) % length
}

export function promoSlideSignatureCount(signature: string | undefined): number {
  if (!signature) {
    return 0
  }
  return signature.split('|').length
}

/** Pick a random starting slide after login, refresh, or when tasks first load. */
export function pickInitialThinkingCoinPromoIndex(
  slideCount: number,
  randomFn: () => number = Math.random
): number {
  if (slideCount <= 1) {
    return 0
  }
  return Math.floor(randomFn() * slideCount)
}

export function shouldPickFreshThinkingCoinPromoIndex(
  previousSignature: string | undefined,
  nextSlideCount: number
): boolean {
  if (nextSlideCount <= 1) {
    return false
  }
  return promoSlideSignatureCount(previousSignature) <= 1
}

export function resolveThinkingCoinPromoTask(
  tasks: ThinkingCoinEarnTask[],
  index: number
): ThinkingCoinEarnTask | null {
  if (tasks.length === 0) {
    return null
  }
  const safeIndex = ((index % tasks.length) + tasks.length) % tasks.length
  return tasks[safeIndex] ?? null
}

export function resolveSidebarPromoSlide(
  slides: SidebarPromoSlide[],
  index: number
): SidebarPromoSlide | null {
  if (slides.length === 0) {
    return null
  }
  const safeIndex = ((index % slides.length) + slides.length) % slides.length
  return slides[safeIndex] ?? null
}

export function formatThinkingCoinTaskPromoTitle(
  task: ThinkingCoinEarnTask,
  isZh: boolean
): string {
  if (!isZh && task.title_en) {
    return task.title_en
  }
  return task.title
}
