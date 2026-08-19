export const TJ_CAPTCHA_SRC = 'https://turing.captcha.qcloud.com/TJCaptcha.js'

export interface TencentCaptchaResult {
  ret: number
  ticket?: string | null
  randstr?: string
  errorCode?: number
  errorMessage?: string
  CaptchaAppId?: string
  appid?: string
  bizState?: unknown
  sid?: string
  verifyDuration?: number
  actionDuration?: number
}

export interface TsecSolvedCaptcha {
  ticket: string
  randstr: string
  sid?: string
  verifyDuration?: number
  actionDuration?: number
}

export interface TencentCaptchaInstance {
  show: () => void
  destroy: () => void
  getTicket: () => { CaptchaAppId: string; ticket: string }
}

export type TsecAidEncryptedType = 'cbc'

export interface TsecAidEncrypted {
  aidEncrypted: string
  aidEncryptedType: TsecAidEncryptedType
}

export interface TencentCaptchaOptions {
  userLanguage?: string
  enableDarkMode?: boolean | 'force'
  aidEncrypted?: string
  aidEncryptedType?: TsecAidEncryptedType
}

export type TencentCaptchaConstructor = new (
  appId: string,
  callback: (result: TencentCaptchaResult) => void,
  options?: TencentCaptchaOptions
) => TencentCaptchaInstance

export interface TsecMintedCaptcha {
  captcha_id: string
  captcha: string
}

declare global {
  interface Window {
    TencentCaptcha?: TencentCaptchaConstructor
  }
}

export {}
