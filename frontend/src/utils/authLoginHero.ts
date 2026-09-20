/** /auth video rotation. Local Vite uses one still (no COS). */

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
export const AUTH_LOGIN_HERO_NARROW_QUERY = '(max-width: 899px)'

export function authLoginHeroKind(): AuthLoginHeroKind {
  return import.meta.env.DEV ? 'image' : 'video'
}

export function authLoginHeroShouldAnimate(options: {
  reduceMotion?: boolean
  narrowViewport?: boolean
} = {}): boolean {
  if (options.reduceMotion || options.narrowViewport) {
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
