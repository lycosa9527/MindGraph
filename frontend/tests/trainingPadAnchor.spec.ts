import { describe, expect, it } from 'vitest'

import { trainingPadBox } from '@/composables/training/trainingPadAnchor'

describe('trainingPadBox', () => {
  it('pins the pad inside the visual viewport and clears the friends rail', () => {
    const full = trainingPadBox({
      innerWidth: 1440,
      innerHeight: 900,
      viewOffsetLeft: 0,
      viewOffsetTop: 0,
      viewWidth: 1440,
      viewHeight: 900,
      railOpen: false,
    })
    expect(full.right).toBe(16)
    expect(full.bottom).toBe(16)
    expect(full.maxHeight).toBe(868)

    const chrome = trainingPadBox({
      innerWidth: 1440,
      innerHeight: 900,
      viewOffsetLeft: 0,
      viewOffsetTop: 0,
      viewWidth: 1440,
      viewHeight: 700,
      railOpen: true,
    })
    expect(chrome.right).toBe(16 + 16 * 16 + 12)
    expect(chrome.bottom).toBe(16 + 200)
    expect(chrome.maxHeight).toBe(668)
  })
})
