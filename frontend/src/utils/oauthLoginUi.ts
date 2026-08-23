/** Official WxLogin default: jump the top window so callback Set-Cookie is visible. */
export const WX_LOGIN_SELF_REDIRECT = false

/**
 * Resolve school invitation code for OAuth QR login from route or register form.
 */
export function resolveOAuthInviteCode(
  routeInvite: unknown,
  registerInvitationCode: string
): string {
  const fromQuery = typeof routeInvite === 'string' ? routeInvite.trim() : ''
  if (fromQuery) {
    return fromQuery
  }
  return (registerInvitationCode || '').trim()
}

/**
 * Whether AccountInfoModal should show the account bindings section.
 */
export function shouldShowAccountBindingsSection(input: {
  schoolId: string | null | undefined
  featureMindbot: boolean
  featureOauthLogin: boolean
  wechatLoginEnabled: boolean
  dingtalkLoginEnabled: boolean
}): boolean {
  if (!input.schoolId) {
    return false
  }
  if (input.featureMindbot) {
    return true
  }
  if (!input.featureOauthLogin) {
    return false
  }
  return input.wechatLoginEnabled || input.dingtalkLoginEnabled
}

/**
 * WeChat bind pill is platform-wide. Hide it unless OAuth is on and WeChat
 * is actually available (or already linked, so the user can unbind).
 */
export function shouldShowWechatBindRow(input: {
  showBindingsSection: boolean
  featureOauthLogin: boolean
  wechatAvailable: boolean
  wechatLinked?: boolean
}): boolean {
  if (!input.showBindingsSection || !input.featureOauthLogin) {
    return false
  }
  return input.wechatAvailable || input.wechatLinked === true
}

/**
 * Bind WeChat when the platform flag is on and credentials are configured.
 */
export function canStartWechatBind(input: {
  featureOauthLogin: boolean
  wechatAvailable: boolean
}): boolean {
  return input.featureOauthLogin && input.wechatAvailable
}

/**
 * Whether LoginModal should show the QR login link.
 */
export function shouldShowQrLoginLink(featureOauthLogin: boolean): boolean {
  return featureOauthLogin
}

export type OAuthErrorLevel = 'warning' | 'error'

export interface OAuthErrorPresentation {
  level: OAuthErrorLevel
  messageKey: string
}

/** Map backend OAuth error codes to i18n keys and toast severity. */
export function resolveOAuthError(detail: string): OAuthErrorPresentation {
  switch (detail) {
    case 'oauth_not_linked':
      return { level: 'warning', messageKey: 'auth.qrLoginNotLinked' }
    case 'oauth_external_taken':
      return { level: 'warning', messageKey: 'auth.oauthExternalTaken' }
    case 'oauth_already_bound':
      return { level: 'warning', messageKey: 'auth.oauthAlreadyBound' }
    case 'oauth_corp_mismatch':
      return { level: 'error', messageKey: 'auth.qrLoginCorpMismatch' }
    case 'oauth_invalid_state':
      return { level: 'error', messageKey: 'auth.qrLoginInvalidState' }
    case 'oauth_invalid_code':
      return { level: 'error', messageKey: 'auth.qrLoginInvalidCode' }
    case 'oauth_rate_limited':
      return { level: 'error', messageKey: 'auth.qrLoginRateLimited' }
    case 'oauth_misconfigured':
      return { level: 'error', messageKey: 'auth.qrLoginMisconfigured' }
    case 'oauth_disabled':
      return { level: 'error', messageKey: 'auth.qrLoginDisabled' }
    case 'oauth_exchange_failed':
    case 'wechat_exchange_failed':
    case 'dingtalk_exchange_failed':
      return { level: 'error', messageKey: 'auth.qrLoginExchangeFailed' }
    default:
      return { level: 'error', messageKey: 'auth.qrLoginExchangeFailed' }
  }
}

/** Whether a query `error` param likely came from an OAuth redirect. */
export function isOAuthRedirectError(detail: string): boolean {
  if (!detail) {
    return false
  }
  return (
    detail.startsWith('oauth_') ||
    detail === 'wechat_exchange_failed' ||
    detail === 'dingtalk_exchange_failed'
  )
}

export function notifyOAuthError(
  detail: string,
  notify: { warning: (message: string) => void; error: (message: string) => void },
  t: (key: string) => string
): void {
  const { level, messageKey } = resolveOAuthError(detail)
  const message = t(messageKey)
  if (level === 'warning') {
    notify.warning(message)
  } else {
    notify.error(message)
  }
}

/** Normalize route query.oauth_bind to a provider id. */
export function oauthBindFromRouteQuery(oauthBind: unknown): 'wechat' | 'dingtalk' | '' {
  const raw = typeof oauthBind === 'string' ? oauthBind.trim() : ''
  if (raw === 'wechat' || raw === 'dingtalk') {
    return raw
  }
  if (Array.isArray(oauthBind) && typeof oauthBind[0] === 'string') {
    const first = oauthBind[0].trim()
    if (first === 'wechat' || first === 'dingtalk') {
      return first
    }
  }
  return ''
}

/** True when OAuth redirect login completed (`/?oauth_login=1`). */
export function oauthLoginFromRouteQuery(oauthLogin: unknown): boolean {
  if (oauthLogin === '1' || oauthLogin === 'true') {
    return true
  }
  if (Array.isArray(oauthLogin) && (oauthLogin[0] === '1' || oauthLogin[0] === 'true')) {
    return true
  }
  return false
}

/** Normalize route query.error to a single string code. */
export function oauthErrorFromRouteQuery(error: unknown): string {
  if (typeof error === 'string') {
    return error.trim()
  }
  if (Array.isArray(error) && typeof error[0] === 'string') {
    return error[0].trim()
  }
  return ''
}
