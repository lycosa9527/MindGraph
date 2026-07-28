/**
 * Map Showcase publish/upload failures to i18n message keys / strings.
 */
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'

function isCorsOrNetworkCause(message: string): boolean {
  return (
    message === 'SHOWCASE_STORAGE_CORS_OR_NETWORK' ||
    /Failed to fetch|NETWORK_ERROR|network request failed/i.test(message)
  )
}

function isCoverTooLargeCause(message: string): boolean {
  return (
    /thumbnail too large/i.test(message) ||
    (/file too large/i.test(message) && /max\s*2\s*mb/i.test(message))
  )
}

function isAttachmentTooLargeCause(message: string): boolean {
  return (
    /file too large/i.test(message) &&
    (/max\s*20\s*mb/i.test(message) || /max\s*100\s*mb/i.test(message))
  )
}

function isGenericTooLargeCause(message: string): boolean {
  return (
    /file too large|request.?entity.?too.?large|content.?too.?large|\b413\b/i.test(
      message,
    ) || message.includes('SHOWCASE_STORAGE_PUT_FAILED:413')
  )
}

function mapSizeOrStorageMessage(
  message: string,
  t: UseLanguageTranslate,
  options: { rolledBack: boolean },
): string | null {
  if (isCoverTooLargeCause(message)) {
    return String(t('showcase.publishModal.uploadCoverTooLarge'))
  }
  if (isAttachmentTooLargeCause(message)) {
    return String(
      t(
        options.rolledBack
          ? 'showcase.publishModal.uploadAttachmentTooLargeRolledBack'
          : 'showcase.publishModal.uploadAttachmentTooLarge',
      ),
    )
  }
  if (isGenericTooLargeCause(message)) {
    return String(
      t(
        options.rolledBack
          ? 'showcase.publishModal.uploadFileTooLargeRolledBack'
          : 'showcase.publishModal.uploadFileTooLarge',
      ),
    )
  }
  return null
}

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
    if (isCorsOrNetworkCause(rolledBackCause)) {
      return String(t('showcase.publishModal.uploadCorsFailed'))
    }
    const sizeMsg = mapSizeOrStorageMessage(rolledBackCause, t, { rolledBack: true })
    if (sizeMsg) return sizeMsg
    if (rolledBackCause.startsWith('SHOWCASE_STORAGE_PUT_FAILED')) {
      return String(t('showcase.publishModal.uploadStorageRejected'))
    }
    return String(t('showcase.publishModal.uploadFailedRolledBack'))
  }
  if (isCorsOrNetworkCause(message)) {
    return String(t('showcase.publishModal.uploadCorsFailed'))
  }
  if (
    message === 'NETWORK_ERROR' ||
    message === 'Failed to fetch' ||
    /network|fetch failed/i.test(message)
  ) {
    return String(t('showcase.publishModal.networkError'))
  }
  const sizeMsg = mapSizeOrStorageMessage(message, t, { rolledBack: false })
  if (sizeMsg) return sizeMsg
  if (message.startsWith('SHOWCASE_STORAGE_PUT_FAILED')) {
    return String(t('showcase.publishModal.uploadStorageRejected'))
  }
  if (/Upload to storage failed|upload failed|presigned|COS|storage/i.test(message)) {
    return String(t('showcase.publishModal.uploadFailed'))
  }
  return message || String(t('showcase.publishModal.uploadFailed'))
}
