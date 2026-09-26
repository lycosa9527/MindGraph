import { beforeEach, describe, expect, it } from 'vitest'

import {
  AUTH_LOGIN_HERO_IDS,
  AUTH_LOGIN_HERO_NARROW_QUERY,
  AUTH_LOGIN_HERO_PHONE_SHORT_SIDE_MAX_PX,
  AUTH_LOGIN_HERO_SESSION_KEY,
  AUTH_LOGIN_HERO_STILL_SRC,
  AUTH_LOGIN_HERO_STORAGE_KEY,
  AUTH_LOGIN_HERO_WIDE_MEDIA,
  authLoginHeroHandheld,
  authLoginHeroShouldAnimate,
  authLoginHeroSrc,
  authLoginHeroViewportNarrow,
  pickAuthLoginHeroId,
  shuffleAuthLoginHeroIds,
} from '@/utils/authLoginHero'

function memoryStorage(): Pick<Storage, 'getItem' | 'setItem'> {
  const map = new Map<string, string>()
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => {
      map.set(key, value)
    },
  }
}

describe('authLoginHero', () => {
  let durable: Pick<Storage, 'getItem' | 'setItem'>

  beforeEach(() => {
    durable = memoryStorage()
  })

  it('keeps the same clip for one browser session', () => {
    const session = memoryStorage()
    const first = pickAuthLoginHeroId({ durable, session, random: () => 0 })
    expect(pickAuthLoginHeroId({ durable, session, random: () => 0.9 })).toBe(first)
    expect(session.getItem(AUTH_LOGIN_HERO_SESSION_KEY)).toBe(first)
  })

  it('draws a shuffle bag across visits and does not repeat the last clip', () => {
    const seen: string[] = []
    for (let visit = 0; visit < AUTH_LOGIN_HERO_IDS.length; visit += 1) {
      seen.push(
        pickAuthLoginHeroId({
          durable,
          session: memoryStorage(),
          random: () => 0,
        })
      )
    }
    expect(new Set(seen).size).toBe(AUTH_LOGIN_HERO_IDS.length)
    const fifth = pickAuthLoginHeroId({
      durable,
      session: memoryStorage(),
      random: () => 0,
    })
    expect(fifth).not.toBe(seen[seen.length - 1])
    expect(durable.getItem(AUTH_LOGIN_HERO_STORAGE_KEY)).toContain('"bag"')
  })

  it('reshuffles so the next bag does not start with the last clip', () => {
    const bag = shuffleAuthLoginHeroIds('01-awaken-cosmos', () => 0)
    expect(bag).toHaveLength(4)
    expect(bag[0]).not.toBe('01-awaken-cosmos')
    expect(new Set(bag).size).toBe(4)
  })

  it('ignores a leftover calendar-day payload and starts a new bag', () => {
    durable.setItem(
      AUTH_LOGIN_HERO_STORAGE_KEY,
      JSON.stringify({ day: '2026-09-21', index: 2 })
    )
    const clip = pickAuthLoginHeroId({
      durable,
      session: memoryStorage(),
      random: () => 0,
    })
    expect(AUTH_LOGIN_HERO_IDS).toContain(clip)
  })

  it('builds the local still and COS video paths', () => {
    expect(AUTH_LOGIN_HERO_IDS).toHaveLength(4)
    expect(authLoginHeroSrc('02-mind-leap', 'image')).toBe(AUTH_LOGIN_HERO_STILL_SRC)
    expect(AUTH_LOGIN_HERO_STILL_SRC).toBe('/auth-hero/login-hero.webp')
    expect(authLoginHeroSrc('02-mind-leap', 'video')).toBe(
      '/api/auth/login-hero/02-mind-leap.mp4'
    )
  })

  it('does not animate on mobile, handheld, or reduced-motion viewports', () => {
    expect(AUTH_LOGIN_HERO_NARROW_QUERY).toBe('(max-width: 899px)')
    expect(AUTH_LOGIN_HERO_WIDE_MEDIA).toBe('(min-width: 900px)')
    expect(authLoginHeroViewportNarrow(899)).toBe(true)
    expect(authLoginHeroViewportNarrow(900)).toBe(false)
    expect(authLoginHeroShouldAnimate({ narrowViewport: true })).toBe(false)
    expect(authLoginHeroShouldAnimate({ handheld: true })).toBe(false)
    expect(authLoginHeroShouldAnimate({ reduceMotion: true })).toBe(false)
  })

  it('treats phones and tablets as handheld, including iOS desktop-site mode', () => {
    expect(
      authLoginHeroHandheld({
        userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
      })
    ).toBe(true)
    expect(
      authLoginHeroHandheld({
        userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8)',
      })
    ).toBe(true)
    expect(
      authLoginHeroHandheld({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        platform: 'MacIntel',
        maxTouchPoints: 5,
      })
    ).toBe(true)
    expect(
      authLoginHeroHandheld({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        pointerCoarse: true,
        hoverNone: true,
        screenWidth: 390,
        screenHeight: 844,
      })
    ).toBe(true)
    expect(AUTH_LOGIN_HERO_PHONE_SHORT_SIDE_MAX_PX).toBe(520)
    expect(
      authLoginHeroHandheld({
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        pointerCoarse: true,
        hoverNone: true,
        screenWidth: 1440,
        screenHeight: 900,
      })
    ).toBe(false)
  })
})
