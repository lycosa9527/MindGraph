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
} from '@/utils/oauthLoginUi'

describe('oauthLoginUi', () => {
  it('resolveOAuthInviteCode prefers route invite', () => {
    expect(resolveOAuthInviteCode('SCHOOL1', 'other')).toBe('SCHOOL1')
  })

  it('resolveOAuthInviteCode falls back to register invitation code', () => {
    expect(resolveOAuthInviteCode(undefined, ' REG99 ')).toBe('REG99')
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
