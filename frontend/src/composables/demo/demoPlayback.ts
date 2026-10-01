/**
 * Library-demo timing and login-film rotation.
 * Pure so the deck clock can be tested without mounting the stage.
 */
import { AUTH_LOGIN_HERO_IDS, type AuthLoginHeroId } from '@/utils/authLoginHero'

export const DEMO_TEMPLATE_MS = 1000
export const DEMO_HOLD_MS = 8000

export type DemoPhase = 'template' | 'revealed'

export function demoHeroIdForSlide(index: number): AuthLoginHeroId {
  const length = AUTH_LOGIN_HERO_IDS.length
  const wrapped = ((index % length) + length) % length
  return AUTH_LOGIN_HERO_IDS[wrapped]
}

export function demoHeroSrc(slideIndex: number): string {
  return `/api/auth/login-hero/${demoHeroIdForSlide(slideIndex)}.mp4`
}

/** Template beat for the first second, unless motion is reduced. */
export function demoPhaseAfter(elapsedMs: number, reduceMotion: boolean): DemoPhase {
  if (reduceMotion) return 'revealed'
  return elapsedMs >= DEMO_TEMPLATE_MS ? 'revealed' : 'template'
}

/** Advance only after the finished diagram has held, and not while paused. */
export function demoShouldAdvance(
  phase: DemoPhase,
  revealedForMs: number,
  paused: boolean
): boolean {
  if (paused || phase !== 'revealed') return false
  return revealedForMs >= DEMO_HOLD_MS
}
