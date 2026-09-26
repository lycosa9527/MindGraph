/** /auth video rotation. Local Vite uses one still (no COS). */

import { isTouchDeviceUserAgent } from '@/utils/isMobileClient'

export const AUTH_LOGIN_HERO_IDS = [
  '01-awaken-cosmos',
  '02-mind-leap',
  '03-study-light',
  '04-ai-lab',
] as const

export type AuthLoginHeroId = (typeof AUTH_LOGIN_HERO_IDS)[number]
export type AuthLoginHeroKind = 'image' | 'video'

export const AUTH_LOGIN_HERO_STORAGE_KEY = 'mg.authLoginHero.v2'
export const AUTH_LOGIN_HERO_SESSION_KEY = 'mg.authLoginHero.session.v2'
export const AUTH_LOGIN_HERO_STILL_SRC = '/auth-hero/login-hero.webp'

export type AuthLoginHeroPickOptions = {
  durable?: Pick<Storage, 'getItem' | 'setItem'>
  session?: Pick<Storage, 'getItem' | 'setItem'>
  random?: () => number
}

type HeroBagState = {
  bag: AuthLoginHeroId[]
  last: AuthLoginHeroId | null
}

/** Same breakpoint as `/auth` mobile layout (`AuthPage` / `AuthLandingBrand`). */
export const AUTH_LOGIN_HERO_NARROW_MAX_PX = 899
export const AUTH_LOGIN_HERO_NARROW_QUERY = `(max-width: ${AUTH_LOGIN_HERO_NARROW_MAX_PX}px)`
/**
 * `<source media>` complement of the narrow layout.
 * A viewport at or below 899px must not fetch the mp4.
 */
export const AUTH_LOGIN_HERO_WIDE_MEDIA = '(min-width: 900px)'
/** Largest phone short side. Tablets and laptops stay above this. */
export const AUTH_LOGIN_HERO_PHONE_SHORT_SIDE_MAX_PX = 520

export function authLoginHeroKind(): AuthLoginHeroKind {
  return import.meta.env.DEV ? 'image' : 'video'
}

export function authLoginHeroViewportNarrow(width: number): boolean {
  return width <= AUTH_LOGIN_HERO_NARROW_MAX_PX
}

/**
 * Phone or tablet, including iOS desktop-site mode (Mac UA, phone-sized screen).
 * Those clients cover the hero with the login card, so the COS clip is wasted.
 */
export function authLoginHeroHandheld(input: {
  userAgent?: string
  platform?: string
  maxTouchPoints?: number
  pointerCoarse?: boolean
  hoverNone?: boolean
  screenWidth?: number
  screenHeight?: number
} = {}): boolean {
  if (isTouchDeviceUserAgent(input.userAgent)) {
    return true
  }
  // iPhone/iPad "Request Desktop Website": Mac UA, MacIntel platform, touch points.
  const touchPoints = input.maxTouchPoints ?? 0
  if (input.platform === 'MacIntel' && touchPoints > 1) {
    return true
  }
  const shortSide = Math.min(input.screenWidth ?? 0, input.screenHeight ?? 0)
  return Boolean(
    input.pointerCoarse &&
      input.hoverNone &&
      shortSide > 0 &&
      shortSide <= AUTH_LOGIN_HERO_PHONE_SHORT_SIDE_MAX_PX
  )
}

export function authLoginHeroShouldAnimate(options: {
  reduceMotion?: boolean
  narrowViewport?: boolean
  handheld?: boolean
} = {}): boolean {
  if (options.reduceMotion || options.narrowViewport || options.handheld) {
    return false
  }
  return authLoginHeroKind() === 'video'
}

export function authLoginHeroSrc(
  clipId: string,
  kind: AuthLoginHeroKind = authLoginHeroKind()
): string {
  if (kind === 'image') {
    return AUTH_LOGIN_HERO_STILL_SRC
  }
  return `/api/auth/login-hero/${clipId}.mp4`
}

function isHeroId(value: unknown): value is AuthLoginHeroId {
  return (
    typeof value === 'string' &&
    (AUTH_LOGIN_HERO_IDS as readonly string[]).includes(value)
  )
}

export function shuffleAuthLoginHeroIds(
  avoid: AuthLoginHeroId | null = null,
  random: () => number = Math.random
): AuthLoginHeroId[] {
  const items = [...AUTH_LOGIN_HERO_IDS]
  for (let index = items.length - 1; index > 0; index -= 1) {
    const swapWith = Math.floor(random() * (index + 1))
    const current = items[index]
    items[index] = items[swapWith]
    items[swapWith] = current
  }
  if (avoid && items.length > 1 && items[0] === avoid) {
    items.push(items.shift() as AuthLoginHeroId)
  }
  return items
}

function readBag(durable: Pick<Storage, 'getItem' | 'setItem'>): HeroBagState {
  const raw = durable.getItem(AUTH_LOGIN_HERO_STORAGE_KEY)
  if (!raw) {
    return { bag: [], last: null }
  }
  try {
    const parsed = JSON.parse(raw) as { bag?: unknown; last?: unknown }
    const bag = Array.isArray(parsed.bag) ? parsed.bag.filter(isHeroId) : []
    const last = isHeroId(parsed.last) ? parsed.last : null
    return { bag, last }
  } catch {
    return { bag: [], last: null }
  }
}

export function pickAuthLoginHeroId(
  options: AuthLoginHeroPickOptions = {}
): AuthLoginHeroId {
  const durable = options.durable ?? window.localStorage
  const session = options.session ?? window.sessionStorage
  const random = options.random ?? Math.random
  const sessionClip = session.getItem(AUTH_LOGIN_HERO_SESSION_KEY)
  if (isHeroId(sessionClip)) {
    return sessionClip
  }
  const state = readBag(durable)
  const bag =
    state.bag.length > 0 ? state.bag : shuffleAuthLoginHeroIds(state.last, random)
  const next = bag[0]
  durable.setItem(
    AUTH_LOGIN_HERO_STORAGE_KEY,
    JSON.stringify({ bag: bag.slice(1), last: next })
  )
  session.setItem(AUTH_LOGIN_HERO_SESSION_KEY, next)
  return next
}
