import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'

import { TJ_CAPTCHA_SRC } from '@/types/tsecCaptcha'
import { loadTjCaptcha, tsecUserLanguage } from '@/utils/tsec/loadTjCaptcha'
import {
  TsecCaptchaClosedError,
  TsecCaptchaFailedError,
  showTsecCaptcha,
} from '@/utils/tsec/showTsecCaptcha'

describe('tsecUserLanguage', () => {
  it('maps zh locales to zh-cn / zh-tw', () => {
    expect(tsecUserLanguage('zh')).toBe('zh-cn')
    expect(tsecUserLanguage('zh-CN')).toBe('zh-cn')
    expect(tsecUserLanguage('zh-TW')).toBe('zh-tw')
    expect(tsecUserLanguage('en')).toBe('en')
  })
})

describe('loadTjCaptcha', () => {
  beforeEach(() => {
    delete window.TencentCaptcha
    document.head.querySelectorAll(`script[src="${TJ_CAPTCHA_SRC}"]`).forEach((node) => node.remove())
  })

  afterEach(() => {
    delete window.TencentCaptcha
  })

  it('resolves the constructor after the script loads', async () => {
    const ctor = vi.fn()
    const pending = loadTjCaptcha()
    const script = document.querySelector(`script[src="${TJ_CAPTCHA_SRC}"]`) as HTMLScriptElement
    expect(script).toBeTruthy()
    window.TencentCaptcha = ctor as unknown as typeof window.TencentCaptcha
    script.dispatchEvent(new Event('load'))
    await expect(pending).resolves.toBe(ctor)
  })
})

const aidAuth = { aidEncrypted: 'dGVzdC1haWQ=', aidEncryptedType: 'cbc' as const }

describe('showTsecCaptcha', () => {
  afterEach(() => {
    delete window.TencentCaptcha
  })

  it('returns ticket and randstr on a real pass', async () => {
    window.TencentCaptcha = class {
      constructor(
        _appId: string,
        callback: (result: { ret: number; ticket: string; randstr: string }) => void
      ) {
        queueMicrotask(() => callback({ ret: 0, ticket: 'tr03ok', randstr: '@Vki' }))
      }
      show() {}
      destroy() {}
      getTicket() {
        return { CaptchaAppId: '1', ticket: 'tr03ok' }
      }
    } as unknown as typeof window.TencentCaptcha

    await expect(showTsecCaptcha('199999164', 'zh', aidAuth)).resolves.toEqual({
      ticket: 'tr03ok',
      randstr: '@Vki',
    })
  })

  it('passes aidEncrypted and cbc type into TencentCaptcha options', async () => {
    let captured: { aidEncrypted?: string; aidEncryptedType?: string } | undefined
    window.TencentCaptcha = class {
      constructor(
        _appId: string,
        callback: (result: { ret: number; ticket: string; randstr: string }) => void,
        options?: { aidEncrypted?: string; aidEncryptedType?: string }
      ) {
        captured = options
        queueMicrotask(() => callback({ ret: 0, ticket: 'tr03ok', randstr: '@Vki' }))
      }
      show() {}
      destroy() {}
      getTicket() {
        return { CaptchaAppId: '1', ticket: 'tr03ok' }
      }
    } as unknown as typeof window.TencentCaptcha

    await showTsecCaptcha('199999164', 'zh', aidAuth)
    expect(captured).toMatchObject({
      aidEncrypted: aidAuth.aidEncrypted,
      aidEncryptedType: 'cbc',
      enableDarkMode: true,
    })
  })

  it('rejects a missing aidEncrypted before loading the widget', async () => {
    await expect(
      showTsecCaptcha('199999164', 'zh', { aidEncrypted: '', aidEncryptedType: 'cbc' })
    ).rejects.toBeInstanceOf(TsecCaptchaFailedError)
  })

  it('treats user close as TsecCaptchaClosedError', async () => {
    window.TencentCaptcha = class {
      constructor(_appId: string, callback: (result: { ret: number; ticket: null }) => void) {
        queueMicrotask(() => callback({ ret: 2, ticket: null }))
      }
      show() {}
      destroy() {}
      getTicket() {
        return { CaptchaAppId: '', ticket: '' }
      }
    } as unknown as typeof window.TencentCaptcha

    await expect(showTsecCaptcha('199999164', 'en', aidAuth)).rejects.toBeInstanceOf(
      TsecCaptchaClosedError
    )
  })

  it('rejects disaster tickets even when ret is 0', async () => {
    window.TencentCaptcha = class {
      constructor(
        _appId: string,
        callback: (result: {
          ret: number
          ticket: string
          randstr: string
          errorCode: number
        }) => void
      ) {
        queueMicrotask(() =>
          callback({
            ret: 0,
            ticket: 'trerror_1001_199999164_1',
            randstr: '@x',
            errorCode: 1001,
          })
        )
      }
      show() {}
      destroy() {}
      getTicket() {
        return { CaptchaAppId: '', ticket: '' }
      }
    } as unknown as typeof window.TencentCaptcha

    await expect(showTsecCaptcha('199999164', 'en', aidAuth)).rejects.toBeInstanceOf(
      TsecCaptchaFailedError
    )
  })
})
