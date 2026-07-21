import { describe, expect, it } from 'vitest'

import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import { mapShowcaseSubmitError } from '@/composables/showcase/mapShowcaseSubmitError'

const messages: Record<string, string> = {
  'auth.sessionExpired': 'session-expired',
  'showcase.publishModal.uploadCorsFailed': 'cors-failed',
  'showcase.publishModal.uploadStorageRejected': 'storage-rejected',
  'showcase.publishModal.uploadFailedRolledBack': 'rolled-back',
  'showcase.publishModal.networkError': 'network',
  'showcase.publishModal.uploadFailed': 'upload-failed',
}

const t = ((key: string) => messages[key] ?? key) as UseLanguageTranslate

describe('mapShowcaseSubmitError', () => {
  it('maps CORS rollback cause', () => {
    expect(
      mapShowcaseSubmitError(
        new Error('SHOWCASE_UPLOAD_ROLLED_BACK:SHOWCASE_STORAGE_CORS_OR_NETWORK'),
        t,
        () => false,
      ),
    ).toBe('cors-failed')
  })

  it('maps storage HTTP rejection after rollback', () => {
    expect(
      mapShowcaseSubmitError(
        new Error('SHOWCASE_UPLOAD_ROLLED_BACK:SHOWCASE_STORAGE_PUT_FAILED:403'),
        t,
        () => false,
      ),
    ).toBe('storage-rejected')
  })

  it('maps generic rollback', () => {
    expect(
      mapShowcaseSubmitError(new Error('SHOWCASE_UPLOAD_ROLLED_BACK:other'), t, () => false),
    ).toBe('rolled-back')
  })

  it('maps session expiry', () => {
    expect(
      mapShowcaseSubmitError(new Error('SESSION_EXPIRED'), t, (m) => m === 'SESSION_EXPIRED'),
    ).toBe('session-expired')
  })
})
