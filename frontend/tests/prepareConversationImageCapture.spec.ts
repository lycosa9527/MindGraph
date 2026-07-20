/**
 * Conversation image capture validates type/size for desktop + mobile.
 */
import { describe, expect, it } from 'vitest'

import { prepareConversationImageCapture } from '@/composables/kitty/prepareConversationImageCapture'
import { CONVERSATION_IMAGE_MAX_UPLOAD_BYTES } from '@/config/conversationImageApi'

describe('prepareConversationImageCapture', () => {
  it('accepts a jpeg under the upload gate', () => {
    const file = new File(['x'], 'shot.jpg', { type: 'image/jpeg' })
    expect(prepareConversationImageCapture(file)).toEqual({ ok: true, file })
  })

  it('returns no_file when input is empty', () => {
    expect(prepareConversationImageCapture(null)).toEqual({
      ok: false,
      reason: 'no_file',
    })
  })

  it('rejects non-image types', () => {
    const file = new File(['x'], 'notes.pdf', { type: 'application/pdf' })
    expect(prepareConversationImageCapture(file)).toEqual({
      ok: false,
      reason: 'invalid_type',
    })
  })

  it('rejects files over the conversation image upload gate', () => {
    const big = new File(
      [new Uint8Array(CONVERSATION_IMAGE_MAX_UPLOAD_BYTES + 1)],
      'huge.jpg',
      { type: 'image/jpeg' }
    )
    expect(prepareConversationImageCapture(big)).toEqual({
      ok: false,
      reason: 'too_large',
    })
  })
})
