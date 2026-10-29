import { describe, expect, it } from 'vitest'

import { seminarMessagesUrl } from '@/composables/mindmate/pullMindmateSeminarHistory'

describe('seminarMessagesUrl', () => {
  it('points send and history at the messages collection', () => {
    expect(seminarMessagesUrl('sess/1')).toBe('/api/mindmate/seminar/sess%2F1/messages')
  })
})
