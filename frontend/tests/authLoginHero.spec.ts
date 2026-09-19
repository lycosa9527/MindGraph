import { beforeEach, describe, expect, it } from 'vitest'

import {
  AUTH_LOGIN_HERO_IDS,
  AUTH_LOGIN_HERO_STILL_SRC,
  AUTH_LOGIN_HERO_STORAGE_KEY,
  authLoginHeroSrc,
  pickAuthLoginHeroId,
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
  let storage: Pick<Storage, 'getItem' | 'setItem'>

  beforeEach(() => {
    storage = memoryStorage()
  })

  it('starts on clip 01 and keeps that clip for the same calendar day', () => {
    const monday = new Date(2026, 8, 21, 9, 0, 0)
    expect(pickAuthLoginHeroId(monday, storage)).toBe('01-awaken-cosmos')
    expect(pickAuthLoginHeroId(new Date(2026, 8, 21, 22, 0, 0), storage)).toBe(
      '01-awaken-cosmos'
    )
    expect(storage.getItem(AUTH_LOGIN_HERO_STORAGE_KEY)).toContain('2026-09-21')
  })

  it('advances one clip on the next calendar day and wraps after 04', () => {
    const monday = new Date(2026, 8, 21)
    expect(pickAuthLoginHeroId(monday, storage)).toBe('01-awaken-cosmos')
    expect(pickAuthLoginHeroId(new Date(2026, 8, 22), storage)).toBe('02-mind-leap')
    expect(pickAuthLoginHeroId(new Date(2026, 8, 23), storage)).toBe('03-study-light')
    expect(pickAuthLoginHeroId(new Date(2026, 8, 24), storage)).toBe('04-ai-lab')
    expect(pickAuthLoginHeroId(new Date(2026, 8, 25), storage)).toBe('01-awaken-cosmos')
  })

  it('builds the local still and COS video paths', () => {
    expect(AUTH_LOGIN_HERO_IDS).toHaveLength(4)
    expect(authLoginHeroSrc('02-mind-leap', 'image')).toBe(AUTH_LOGIN_HERO_STILL_SRC)
    expect(AUTH_LOGIN_HERO_STILL_SRC).toBe('/auth-hero/login-hero.png')
    expect(authLoginHeroSrc('02-mind-leap', 'video')).toBe(
      '/api/auth/login-hero/02-mind-leap.mp4'
    )
  })
})
