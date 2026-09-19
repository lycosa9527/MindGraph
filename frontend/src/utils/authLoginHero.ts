/** Daily /auth video rotation. Local Vite uses one still (no COS). */

export const AUTH_LOGIN_HERO_IDS = [
  '01-awaken-cosmos',
  '02-mind-leap',
  '03-study-light',
  '04-ai-lab',
] as const

export type AuthLoginHeroId = (typeof AUTH_LOGIN_HERO_IDS)[number]
export type AuthLoginHeroKind = 'image' | 'video'

export const AUTH_LOGIN_HERO_STORAGE_KEY = 'mg.authLoginHero.v1'
export const AUTH_LOGIN_HERO_STILL_SRC = '/auth-hero/login-hero.png'

export function formatLocalDay(now: Date): string {
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function authLoginHeroKind(): AuthLoginHeroKind {
  return import.meta.env.DEV ? 'image' : 'video'
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

function wrapIndex(index: number, length: number): number {
  return ((index % length) + length) % length
}

export function pickAuthLoginHeroId(
  now: Date = new Date(),
  storage: Pick<Storage, 'getItem' | 'setItem'> = window.localStorage
): AuthLoginHeroId {
  const day = formatLocalDay(now)
  const length = AUTH_LOGIN_HERO_IDS.length
  let index = 0
  const raw = storage.getItem(AUTH_LOGIN_HERO_STORAGE_KEY)
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as { day?: string; index?: number }
      if (typeof parsed.index === 'number' && Number.isInteger(parsed.index)) {
        const wrapped = wrapIndex(parsed.index, length)
        if (parsed.day === day) {
          return AUTH_LOGIN_HERO_IDS[wrapped]
        }
        index = wrapIndex(wrapped + 1, length)
      }
    } catch {
      index = 0
    }
  }
  storage.setItem(AUTH_LOGIN_HERO_STORAGE_KEY, JSON.stringify({ day, index }))
  return AUTH_LOGIN_HERO_IDS[index]
}
