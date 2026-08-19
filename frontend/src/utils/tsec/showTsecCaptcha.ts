import type { TencentCaptchaResult, TsecAidEncrypted, TsecSolvedCaptcha } from '@/types/tsecCaptcha'
import { loadTjCaptcha, tsecUserLanguage } from '@/utils/tsec/loadTjCaptcha'
import { tsecFrontendErrorReason } from '@/utils/tsec/tsecErrorCodes'

export class TsecCaptchaClosedError extends Error {
  constructor() {
    super('tsec_closed')
    this.name = 'TsecCaptchaClosedError'
  }
}

export class TsecCaptchaFailedError extends Error {
  constructor(message = 'tsec_failed') {
    super(message)
    this.name = 'TsecCaptchaFailedError'
  }
}

function isDisasterTicket(ticket: string): boolean {
  return ticket.startsWith('trerror_') || ticket.startsWith('terror_')
}

export async function showTsecCaptcha(
  appId: string,
  uiLocale: string,
  aidAuth: TsecAidEncrypted
): Promise<TsecSolvedCaptcha> {
  if (!aidAuth.aidEncrypted || aidAuth.aidEncryptedType !== 'cbc') {
    throw new TsecCaptchaFailedError('aid_encrypted_missing')
  }
  const TencentCaptcha = await loadTjCaptcha()
  return new Promise((resolve, reject) => {
    try {
      const captcha = new TencentCaptcha(
        appId,
        (result: TencentCaptchaResult) => {
          if (result.ret === 2) {
            reject(new TsecCaptchaClosedError())
            return
          }
          const ticket = (result.ticket || '').trim()
          const randstr = (result.randstr || '').trim()
          if (result.ret !== 0 || !ticket || !randstr || result.errorCode || isDisasterTicket(ticket)) {
            reject(new TsecCaptchaFailedError(tsecFrontendErrorReason(result.errorCode, result.errorMessage)))
            return
          }
          const solved: TsecSolvedCaptcha = { ticket, randstr }
          if (result.sid) {
            solved.sid = result.sid
          }
          if (typeof result.verifyDuration === 'number') {
            solved.verifyDuration = result.verifyDuration
          }
          if (typeof result.actionDuration === 'number') {
            solved.actionDuration = result.actionDuration
          }
          resolve(solved)
        },
        {
          userLanguage: tsecUserLanguage(uiLocale),
          enableDarkMode: true,
          aidEncrypted: aidAuth.aidEncrypted,
          aidEncryptedType: aidAuth.aidEncryptedType,
        }
      )
      captcha.show()
    } catch {
      reject(new TsecCaptchaFailedError('jsload_error'))
    }
  })
}
