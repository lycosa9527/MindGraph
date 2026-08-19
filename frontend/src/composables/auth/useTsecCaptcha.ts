import { computed } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { apiRequest } from '@/utils/apiClient'
import {
  TsecCaptchaClosedError,
  TsecCaptchaFailedError,
  showTsecCaptcha,
} from '@/utils/tsec/showTsecCaptcha'
import type { TsecAidEncrypted, TsecMintedCaptcha, TsecSolvedCaptcha } from '@/types/tsecCaptcha'

export function useTsecCaptcha() {
  const featureFlagsStore = useFeatureFlagsStore()
  const { t, currentLanguage } = useLanguage()
  const notify = useNotifications()

  const isTsecCaptcha = computed(() => {
    const flags = featureFlagsStore.flags
    if (!flags) {
      return false
    }
    return flags.captcha_provider === 'tsec' && Boolean(flags.tencent_captcha_app_id)
  })

  const showLegacyCaptcha = computed(() => {
    if (!featureFlagsStore.flags && featureFlagsStore.isLoading) {
      return false
    }
    return !isTsecCaptcha.value
  })

  async function ensureFlags(): Promise<void> {
    if (!featureFlagsStore.flags) {
      await featureFlagsStore.fetchFlags()
    }
  }

  async function fetchAidEncrypted(): Promise<TsecAidEncrypted> {
    const response = await apiRequest('/api/auth/tsec/aid-encrypted', { method: 'GET' })
    if (!response.ok) {
      throw new TsecCaptchaFailedError('aid_encrypted_failed')
    }
    const data = (await response.json()) as {
      aid_encrypted?: string
      aid_encrypted_type?: string
    }
    if (!data.aid_encrypted || data.aid_encrypted_type !== 'cbc') {
      throw new TsecCaptchaFailedError('aid_encrypted_invalid')
    }
    return { aidEncrypted: data.aid_encrypted, aidEncryptedType: 'cbc' }
  }

  async function exchangeTicket(solved: TsecSolvedCaptcha): Promise<TsecMintedCaptcha> {
    const response = await apiRequest('/api/auth/tsec/exchange', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticket: solved.ticket,
        randstr: solved.randstr,
        sid: solved.sid,
        verify_duration: solved.verifyDuration,
        action_duration: solved.actionDuration,
      }),
    })
    if (!response.ok) {
      throw new TsecCaptchaFailedError('exchange_failed')
    }
    const data = (await response.json()) as Partial<TsecMintedCaptcha>
    if (!data.captcha_id || !data.captcha) {
      throw new TsecCaptchaFailedError('exchange_invalid')
    }
    return { captcha_id: data.captcha_id, captcha: data.captcha }
  }

  async function solveTsecCaptcha(): Promise<TsecMintedCaptcha | null> {
    await ensureFlags()
    const appId = featureFlagsStore.flags?.tencent_captcha_app_id || ''
    if (!appId) {
      notify.error(t('auth.tsecUnavailable'))
      return null
    }
    try {
      const aidAuth = await fetchAidEncrypted()
      const solved = await showTsecCaptcha(appId, currentLanguage.value, aidAuth)
      return await exchangeTicket(solved)
    } catch (error) {
      if (error instanceof TsecCaptchaClosedError) {
        return null
      }
      console.error('T-Sec captcha error:', error)
      notify.error(t('auth.tsecFailed'))
      return null
    }
  }

  async function resolveCaptchaProof(
    formCaptcha: string,
    captchaId: string
  ): Promise<TsecMintedCaptcha | null> {
    await ensureFlags()
    if (isTsecCaptcha.value) {
      return solveTsecCaptcha()
    }
    if (!formCaptcha || formCaptcha.length !== 4) {
      notify.warning(t('auth.modal.enter4DigitCaptcha'))
      return null
    }
    if (!captchaId) {
      notify.warning(t('auth.modal.waitCaptchaLoad'))
      return null
    }
    return { captcha: formCaptcha, captcha_id: captchaId }
  }

  return {
    isTsecCaptcha,
    showLegacyCaptcha,
    solveTsecCaptcha,
    resolveCaptchaProof,
  }
}
