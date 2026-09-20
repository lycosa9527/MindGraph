import type {
  TencentCaptchaInstance,
  TencentCaptchaResult,
  TsecAidEncrypted,
  TsecSolvedCaptcha,
} from '@/types/tsecCaptcha'
import { loadTjCaptcha, tsecUserLanguage } from '@/utils/tsec/loadTjCaptcha'
import { mountTsecCaptchaOnLoginCard } from '@/utils/tsec/mountTsecCaptchaHost'
import {
  applyTsecCaptchaToLoginCard,
  bindTsecCaptchaToLoginCard,
} from '@/utils/tsec/positionTsecCaptcha'
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

function parseSolvedCaptcha(result: TencentCaptchaResult): TsecSolvedCaptcha {
  const solved: TsecSolvedCaptcha = {
    ticket: (result.ticket || '').trim(),
    randstr: (result.randstr || '').trim(),
  }
  if (result.sid) {
    solved.sid = result.sid
  }
  if (typeof result.verifyDuration === 'number') {
    solved.verifyDuration = result.verifyDuration
  }
  if (typeof result.actionDuration === 'number') {
    solved.actionDuration = result.actionDuration
  }
  return solved
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
    let captcha: TencentCaptchaInstance | null = null
    let settled = false
    let releaseHost = (): void => {}
    const releasePopup = bindTsecCaptchaToLoginCard()
    const finish = (next: () => void): void => {
      if (settled) {
        return
      }
      settled = true
      if (captcha) {
        captcha.destroy()
      }
      releasePopup()
      releaseHost()
      next()
    }
    const { host, release } = mountTsecCaptchaOnLoginCard(() => {
      finish(() => reject(new TsecCaptchaClosedError()))
    })
    releaseHost = release
    try {
      captcha = new TencentCaptcha(
        host,
        appId,
        (result: TencentCaptchaResult) => {
          if (result.ret === 2) {
            finish(() => reject(new TsecCaptchaClosedError()))
            return
          }
          const ticket = (result.ticket || '').trim()
          const randstr = (result.randstr || '').trim()
          if (result.ret !== 0 || !ticket || !randstr || result.errorCode || isDisasterTicket(ticket)) {
            finish(() =>
              reject(new TsecCaptchaFailedError(tsecFrontendErrorReason(result.errorCode, result.errorMessage)))
            )
            return
          }
          finish(() => resolve(parseSolvedCaptcha(result)))
        },
        {
          type: 'embed',
          userLanguage: tsecUserLanguage(uiLocale),
          enableDarkMode: true,
          aidEncrypted: aidAuth.aidEncrypted,
          aidEncryptedType: aidAuth.aidEncryptedType,
          ready: () => {
            applyTsecCaptchaToLoginCard()
          },
          showFn: () => {
            applyTsecCaptchaToLoginCard()
          },
        }
      )
      captcha.show()
    } catch {
      finish(() => reject(new TsecCaptchaFailedError('jsload_error')))
    }
  })
}
