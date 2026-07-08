/**
 * /privacy is bilingual (zh / en) from the browser language list, not the saved UI locale.
 */

export type PrivacyPageUiCode = 'zh' | 'en'

const PRIVACY_PAGE_CHROME: Record<
  PrivacyPageUiCode,
  { backToSignIn: string; updatedPrefix: string; pageTitle: string; brandName: string }
> = {
  zh: {
    backToSignIn: '返回登录',
    updatedPrefix: '更新日期：',
    pageTitle: '用户协议与隐私政策',
    brandName: '迈特教研',
  },
  en: {
    backToSignIn: 'Back to sign in',
    updatedPrefix: 'Last updated: ',
    pageTitle: 'Terms & Privacy',
    brandName: 'Mind Platform',
  },
}

/**
 * True when any preferred browser language is Chinese (zh, zh-CN, zh-TW, …).
 */
export function isBrowserLanguageChinese(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  const rawList =
    navigator.languages && navigator.languages.length > 0
      ? navigator.languages
      : [navigator.language]
  for (const raw of rawList) {
    if (!raw) {
      continue
    }
    const tag = raw.toLowerCase()
    if (tag === 'zh' || tag.startsWith('zh-')) {
      return true
    }
  }
  return false
}

/** Chinese browsers → zh; English and all other languages → en. */
export function detectPrivacyPageUiCode(): PrivacyPageUiCode {
  return isBrowserLanguageChinese() ? 'zh' : 'en'
}

export function privacyPageChrome(uiCode: PrivacyPageUiCode) {
  return PRIVACY_PAGE_CHROME[uiCode]
}

export function privacyPageUpdatedLabel(uiCode: PrivacyPageUiCode, date: string): string {
  return `${PRIVACY_PAGE_CHROME[uiCode].updatedPrefix}${date}`
}

export function privacyPageDocumentTitle(uiCode: PrivacyPageUiCode): string {
  const chrome = PRIVACY_PAGE_CHROME[uiCode]
  return `${chrome.pageTitle} · ${chrome.brandName}`
}

export function privacyPageHtmlLang(uiCode: PrivacyPageUiCode): string {
  return uiCode === 'zh' ? 'zh-CN' : 'en'
}
