/**
 * Map Showcase publish/upload failures to i18n message keys / strings.
 */
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'

export function mapShowcaseSubmitError(
  error: unknown,
  t: UseLanguageTranslate,
  isSessionExpiredMessage: (message: string) => boolean,
): string {
  const message = error instanceof Error ? error.message : ''
  if (isSessionExpiredMessage(message)) {
    return String(t('auth.sessionExpired'))
  }
  const rolledBackPrefix = 'SHOWCASE_UPLOAD_ROLLED_BACK:'
  const rolledBackCause = message.startsWith(rolledBackPrefix)
    ? message.slice(rolledBackPrefix.length)
    : message === 'SHOWCASE_UPLOAD_ROLLED_BACK'
      ? ''
      : null
  if (rolledBackCause !== null) {
    if (
      rolledBackCause === 'SHOWCASE_STORAGE_CORS_OR_NETWORK' ||
      /Failed to fetch|NETWORK_ERROR|network request failed/i.test(rolledBackCause)
    ) {
      return String(t('showcase.publishModal.uploadCorsFailed'))
    }
    if (rolledBackCause.startsWith('SHOWCASE_STORAGE_PUT_FAILED')) {
      return String(t('showcase.publishModal.uploadStorageRejected'))
    }
    return String(t('showcase.publishModal.uploadFailedRolledBack'))
  }
  if (message === 'SHOWCASE_STORAGE_CORS_OR_NETWORK') {
    return String(t('showcase.publishModal.uploadCorsFailed'))
  }
  if (
    message === 'NETWORK_ERROR' ||
    message === 'Failed to fetch' ||
    /network|fetch failed/i.test(message)
  ) {
    return String(t('showcase.publishModal.networkError'))
  }
  if (message.startsWith('SHOWCASE_STORAGE_PUT_FAILED')) {
    return String(t('showcase.publishModal.uploadStorageRejected'))
  }
  if (/Upload to storage failed|upload failed|presigned|COS|storage/i.test(message)) {
    return String(t('showcase.publishModal.uploadFailed'))
  }
  return message || String(t('showcase.publishModal.uploadFailed'))
}
