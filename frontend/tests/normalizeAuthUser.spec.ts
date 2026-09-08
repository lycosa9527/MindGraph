import { describe, expect, it } from 'vitest'

import { normalizeAuthUser } from '@/utils/normalizeAuthUser'

const loginPayload = {
  id: 42,
  name: 'Ada',
  phone: '13800000000',
  role: 'teacher' as const,
  ui_language: 'zh',
  prompt_language: 'zh',
  match_prompt_to_ui: true,
  ui_version: 'international',
  allows_simplified_chinese: true,
  daily_tokens: {
    cap: 5000000,
    used_today: 12345,
    remaining_today: 4987655,
  },
}

describe('normalizeAuthUser', () => {
  it('keeps persisted UI language when mapping a login payload', () => {
    const user = normalizeAuthUser(loginPayload)
    expect(user.uiLanguage).toBe('zh')
    expect(user.promptLanguage).toBe('zh')
    expect(user.matchPromptToUi).toBe(true)
  })

  it('is idempotent so login + setUser does not drop camelCase language fields', () => {
    const once = normalizeAuthUser(loginPayload)
    const twice = normalizeAuthUser(once)
    expect(twice.uiLanguage).toBe('zh')
    expect(twice.promptLanguage).toBe('zh')
    expect(twice.matchPromptToUi).toBe(true)
    expect(twice.allowsSimplifiedChinese).toBe(true)
    expect(twice.uiVersion).toBe('international')
    expect(twice.dailyTokens).toEqual({
      cap: 5000000,
      usedToday: 12345,
      remainingToday: 4987655,
    })
  })

  it('maps daily token usage from /me', () => {
    const user = normalizeAuthUser(loginPayload)
    expect(user.dailyTokens).toEqual({
      cap: 5000000,
      usedToday: 12345,
      remainingToday: 4987655,
    })
  })

  it('maps thinking coins from a login payload so the sidebar can show without /me', () => {
    const user = normalizeAuthUser({
      ...loginPayload,
      thinking_coins: { balance: 42, eligible: true },
    })
    expect(user.thinkingCoins).toEqual({ balance: 42, eligible: true })
  })

  it('leaves thinking coins unset when login omits the field', () => {
    const user = normalizeAuthUser(loginPayload)
    expect(user.thinkingCoins).toBeUndefined()
  })

  it('hydrates ribbon height and last tab from /me', () => {
    const user = normalizeAuthUser({
      ...loginPayload,
      v3_ribbon_classic: true,
      v3_ribbon_tab: 'Review',
    })
    expect(user.v3RibbonClassic).toBe(true)
    expect(user.v3RibbonTab).toBe('teaching')
  })

  it('maps retired draw and learn ribbon tabs onto edit and teaching', () => {
    expect(normalizeAuthUser({ ...loginPayload, v3_ribbon_tab: 'draw' }).v3RibbonTab).toBe('edit')
    expect(normalizeAuthUser({ ...loginPayload, v3_ribbon_tab: 'learn' }).v3RibbonTab).toBe(
      'teaching'
    )
    expect(normalizeAuthUser({ ...loginPayload, v3_ribbon_tab: 'ai' }).v3RibbonTab).toBe('ai')
  })

  it('drops unknown ribbon tabs', () => {
    const user = normalizeAuthUser({
      ...loginPayload,
      v3RibbonClassic: false,
      v3RibbonTab: 'favorites',
    })
    expect(user.v3RibbonClassic).toBe(false)
    expect(user.v3RibbonTab).toBeNull()
  })

  it('coerces BCP 47 aliases such as zh-CN to the enabled UI locale', () => {
    const user = normalizeAuthUser({
      ...loginPayload,
      ui_language: 'zh-CN',
    })
    expect(user.uiLanguage).toBe('zh')
  })
})
