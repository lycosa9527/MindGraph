/** Vitest: voice command label formatting */
import { describe, expect, it } from 'vitest'

import { formatKittyVoiceCommandLabel } from '@/composables/kitty/kittyVoiceCommandLabels'

describe('formatKittyVoiceCommandLabel', () => {
  it('uses translation key when available', () => {
    const label = formatKittyVoiceCommandLabel('auto_complete', undefined, (key) => {
      if (key === 'kitty.voiceCommand.auto_complete') {
        return 'Run auto-complete'
      }
      return key
    })
    expect(label).toBe('Run auto-complete')
  })

  it('falls back to action and detail', () => {
    const label = formatKittyVoiceCommandLabel('custom_action', 'hello', (key) => key)
    expect(label).toBe('custom action: hello')
  })
})
