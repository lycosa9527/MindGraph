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

  it('coerces BCP 47 aliases such as zh-CN to the enabled UI locale', () => {
    const user = normalizeAuthUser({
      ...loginPayload,
      ui_language: 'zh-CN',
    })
    expect(user.uiLanguage).toBe('zh')
  })
})
