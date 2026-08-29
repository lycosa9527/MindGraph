import { describe, expect, it } from 'vitest'

import {
  resolveOAuthInviteCode,
  resolveOAuthError,
  isOAuthRedirectError,
  notifyOAuthError,
  oauthErrorFromRouteQuery,
  oauthBindFromRouteQuery,
  oauthLoginFromRouteQuery,
  persistOAuthLoginError,
  persistedOAuthLoginError,
  clearPersistedOAuthLoginError,
  hydratePersistedOAuthLoginError,
  shouldShowAccountBindingsSection,
  shouldShowWechatLoginLink,
  shouldShowWechatBindRow,
  canStartWechatBind,
  sizeWechatLoginIframe,
  wechatLoginStyleHref,
  wechatQrModalMaxWidthPx,
  OAUTH_NOT_LINKED_TOAST_MS,
  WX_LOGIN_QR_SIZE_PX,
  WX_LOGIN_SELF_REDIRECT,
  WX_LOGIN_STYLE_HREF_PATH,
} from '@/utils/oauthLoginUi'

describe('oauthLoginUi', () => {
  it('resolveOAuthInviteCode prefers route invite', () => {
    expect(resolveOAuthInviteCode('SCHOOL1', 'other')).toBe('SCHOOL1')
  })

  it('resolveOAuthInviteCode falls back to register invitation code', () => {
    expect(resolveOAuthInviteCode(undefined, ' REG99 ')).toBe('REG99')
  })

  it('WxLogin jumps the top window so callback cookies apply', () => {
    expect(WX_LOGIN_SELF_REDIRECT).toBe(false)
  })

  it('WxLogin href is the public /static stylesheet WeChat can fetch', () => {
    expect(WX_LOGIN_STYLE_HREF_PATH).toBe('/oauth-wx-login.css')
    expect(wechatLoginStyleHref('https://test.mindspringedu.com')).toBe(
      encodeURIComponent('https://test.mindspringedu.com/oauth-wx-login.css?v=2')
    )
    expect(WX_LOGIN_QR_SIZE_PX).toBe(248)
    expect(wechatQrModalMaxWidthPx()).toBe(288)
  })

  it('sizeWechatLoginIframe sets the official iframe to the modal QR size', () => {
    const container = document.createElement('div')
    const iframe = document.createElement('iframe')
    iframe.setAttribute('width', '300')
    iframe.setAttribute('height', '400')
    container.appendChild(iframe)
    sizeWechatLoginIframe(container, WX_LOGIN_QR_SIZE_PX)
    expect(iframe.getAttribute('width')).toBe('248')
    expect(iframe.getAttribute('height')).toBe('248')
    expect(iframe.style.width).toBe('248px')
    expect(iframe.style.height).toBe('248px')
    expect(iframe.style.display).toBe('block')
    expect(iframe.style.marginLeft).toBe('auto')
    expect(iframe.style.marginRight).toBe('auto')
  })

  it('shouldShowWechatBindRow hides when WeChat flag is off or unavailable', () => {
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureWechatLogin: true,
        wechatAvailable: true,
      })
    ).toBe(true)
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureWechatLogin: false,
        wechatAvailable: true,
      })
    ).toBe(false)
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureWechatLogin: true,
        wechatAvailable: false,
      })
    ).toBe(false)
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureWechatLogin: true,
        wechatAvailable: false,
        wechatLinked: true,
      })
    ).toBe(true)
  })

  it('canStartWechatBind needs FEATURE_WECHAT_LOGIN and credentials', () => {
    expect(
      canStartWechatBind({ featureWechatLogin: true, wechatAvailable: true })
    ).toBe(true)
    expect(
      canStartWechatBind({ featureWechatLogin: true, wechatAvailable: false })
    ).toBe(false)
    expect(
      canStartWechatBind({ featureWechatLogin: false, wechatAvailable: true })
    ).toBe(false)
  })

  it('shouldShowWechatLoginLink follows FEATURE_WECHAT_LOGIN', () => {
    expect(shouldShowWechatLoginLink(true)).toBe(true)
    expect(shouldShowWechatLoginLink(false)).toBe(false)
  })

  it('shouldShowAccountBindingsSection when mindbot enabled', () => {
    expect(
      shouldShowAccountBindingsSection({
        schoolId: '1',
        featureMindbot: true,
        featureDingtalkLogin: false,
        featureWechatLogin: false,
        wechatAvailable: false,
        dingtalkLoginEnabled: false,
      })
    ).toBe(true)
  })

  it('shouldShowAccountBindingsSection when WeChat is on', () => {
    expect(
      shouldShowAccountBindingsSection({
        schoolId: '1',
        featureMindbot: false,
        featureDingtalkLogin: false,
        featureWechatLogin: true,
        wechatAvailable: true,
        dingtalkLoginEnabled: false,
      })
    ).toBe(true)
  })

  it('hides account bindings without school or providers', () => {
    expect(
      shouldShowAccountBindingsSection({
        schoolId: null,
        featureMindbot: false,
        featureDingtalkLogin: true,
        featureWechatLogin: true,
        wechatAvailable: true,
        dingtalkLoginEnabled: false,
      })
    ).toBe(false)
    expect(
      shouldShowAccountBindingsSection({
        schoolId: '2',
        featureMindbot: false,
        featureDingtalkLogin: true,
        featureWechatLogin: false,
        wechatAvailable: false,
        dingtalkLoginEnabled: false,
      })
    ).toBe(false)
  })

  it('resolveOAuthError maps backend codes to i18n keys', () => {
    expect(resolveOAuthError('oauth_not_linked')).toEqual({
      level: 'error',
      messageKey: 'auth.qrLoginNotLinked',
      durationMs: OAUTH_NOT_LINKED_TOAST_MS,
    })
    expect(resolveOAuthError('oauth_external_taken')).toEqual({
      level: 'warning',
      messageKey: 'auth.oauthExternalTaken',
    })
    expect(resolveOAuthError('wechat_exchange_failed')).toEqual({
      level: 'error',
      messageKey: 'auth.qrLoginExchangeFailed',
    })
    expect(resolveOAuthError('oauth_already_bound')).toEqual({
      level: 'warning',
      messageKey: 'auth.oauthAlreadyBound',
    })
    expect(resolveOAuthError('oauth_invalid_code')).toEqual({
      level: 'error',
      messageKey: 'auth.qrLoginInvalidCode',
    })
    expect(resolveOAuthError('oauth_rate_limited')).toEqual({
      level: 'error',
      messageKey: 'auth.qrLoginRateLimited',
    })
    expect(resolveOAuthError('oauth_misconfigured')).toEqual({
      level: 'error',
      messageKey: 'auth.qrLoginMisconfigured',
    })
  })

  it('isOAuthRedirectError recognizes oauth query codes', () => {
    expect(isOAuthRedirectError('oauth_invalid_state')).toBe(true)
    expect(isOAuthRedirectError('wechat_exchange_failed')).toBe(true)
    expect(isOAuthRedirectError('login_failed')).toBe(false)
  })

  it('oauthErrorFromRouteQuery normalizes array query values', () => {
    expect(oauthErrorFromRouteQuery('oauth_corp_mismatch')).toBe('oauth_corp_mismatch')
    expect(oauthErrorFromRouteQuery(['oauth_not_linked'])).toBe('oauth_not_linked')
  })

  it('oauthBindFromRouteQuery accepts wechat and dingtalk', () => {
    expect(oauthBindFromRouteQuery('wechat')).toBe('wechat')
    expect(oauthBindFromRouteQuery(['dingtalk'])).toBe('dingtalk')
    expect(oauthBindFromRouteQuery('other')).toBe('')
  })

  it('oauthLoginFromRouteQuery accepts oauth_login=1', () => {
    expect(oauthLoginFromRouteQuery('1')).toBe(true)
    expect(oauthLoginFromRouteQuery('true')).toBe(true)
    expect(oauthLoginFromRouteQuery(['1'])).toBe(true)
    expect(oauthLoginFromRouteQuery('0')).toBe(false)
    expect(oauthLoginFromRouteQuery(undefined)).toBe(false)
  })

  it('persistOAuthLoginError keeps only oauth_not_linked for the login banner', () => {
    clearPersistedOAuthLoginError()
    persistOAuthLoginError('oauth_exchange_failed')
    expect(persistedOAuthLoginError.value).toBe('')
    persistOAuthLoginError('oauth_not_linked')
    expect(persistedOAuthLoginError.value).toBe('oauth_not_linked')
    clearPersistedOAuthLoginError()
    persistOAuthLoginError('oauth_not_linked')
    persistedOAuthLoginError.value = ''
    hydratePersistedOAuthLoginError()
    expect(persistedOAuthLoginError.value).toBe('oauth_not_linked')
    clearPersistedOAuthLoginError()
  })

  it('notifyOAuthError toasts bind-first as an error and persists it', () => {
    clearPersistedOAuthLoginError()
    const calls: { level: string; message: string; duration?: number }[] = []
    const notify = {
      warning: (message: string, duration?: number) => {
        calls.push({ level: 'warning', message, duration })
      },
      error: (message: string, duration?: number) => {
        calls.push({ level: 'error', message, duration })
      },
    }
    notifyOAuthError('oauth_not_linked', notify, (key) => key)
    expect(calls).toEqual([
      {
        level: 'error',
        message: 'auth.qrLoginNotLinked',
        duration: OAUTH_NOT_LINKED_TOAST_MS,
      },
    ])
    expect(persistedOAuthLoginError.value).toBe('oauth_not_linked')
    clearPersistedOAuthLoginError()
  })
})
