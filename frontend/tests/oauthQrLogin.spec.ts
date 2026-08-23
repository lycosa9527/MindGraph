import { describe, expect, it } from 'vitest'

import {
  resolveOAuthInviteCode,
  resolveOAuthError,
  isOAuthRedirectError,
  oauthErrorFromRouteQuery,
  oauthBindFromRouteQuery,
  oauthLoginFromRouteQuery,
  shouldShowAccountBindingsSection,
  shouldShowQrLoginLink,
  shouldShowWechatBindRow,
  canStartWechatBind,
  WX_LOGIN_SELF_REDIRECT,
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

  it('shouldShowWechatBindRow hides when OAuth is off or WeChat is unavailable', () => {
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureOauthLogin: true,
        wechatAvailable: true,
      })
    ).toBe(true)
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureOauthLogin: false,
        wechatAvailable: true,
      })
    ).toBe(false)
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureOauthLogin: true,
        wechatAvailable: false,
      })
    ).toBe(false)
    expect(
      shouldShowWechatBindRow({
        showBindingsSection: true,
        featureOauthLogin: true,
        wechatAvailable: false,
        wechatLinked: true,
      })
    ).toBe(true)
  })

  it('canStartWechatBind needs feature and configured WeChat credentials', () => {
    expect(
      canStartWechatBind({ featureOauthLogin: true, wechatAvailable: true })
    ).toBe(true)
    expect(
      canStartWechatBind({ featureOauthLogin: true, wechatAvailable: false })
    ).toBe(false)
    expect(
      canStartWechatBind({ featureOauthLogin: false, wechatAvailable: true })
    ).toBe(false)
  })

  it('shouldShowQrLoginLink follows feature flag', () => {
    expect(shouldShowQrLoginLink(true)).toBe(true)
    expect(shouldShowQrLoginLink(false)).toBe(false)
  })

  it('shouldShowAccountBindingsSection when mindbot enabled', () => {
    expect(
      shouldShowAccountBindingsSection({
        schoolId: '1',
        featureMindbot: true,
        featureOauthLogin: false,
        wechatLoginEnabled: false,
        dingtalkLoginEnabled: false,
      })
    ).toBe(true)
  })

  it('shouldShowAccountBindingsSection when oauth provider enabled', () => {
    expect(
      shouldShowAccountBindingsSection({
        schoolId: '1',
        featureMindbot: false,
        featureOauthLogin: true,
        wechatLoginEnabled: true,
        dingtalkLoginEnabled: false,
      })
    ).toBe(true)
  })

  it('hides account bindings without school or providers', () => {
    expect(
      shouldShowAccountBindingsSection({
        schoolId: null,
        featureMindbot: false,
        featureOauthLogin: true,
        wechatLoginEnabled: true,
        dingtalkLoginEnabled: false,
      })
    ).toBe(false)
    expect(
      shouldShowAccountBindingsSection({
        schoolId: '2',
        featureMindbot: false,
        featureOauthLogin: true,
        wechatLoginEnabled: false,
        dingtalkLoginEnabled: false,
      })
    ).toBe(false)
  })

  it('resolveOAuthError maps backend codes to i18n keys', () => {
    expect(resolveOAuthError('oauth_not_linked')).toEqual({
      level: 'warning',
      messageKey: 'auth.qrLoginNotLinked',
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
})
