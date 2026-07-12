import { describe, expect, it } from 'vitest'

import { isWireframeExport } from '@/utils/canvasExportVisualMode'

describe('canvasExportVisualMode', () => {
  it('detects wireframe export from colorMode', () => {
    expect(isWireframeExport({ colorMode: 'wireframe', layout: 'landscape', answerMode: 'exclude' })).toBe(
      true
    )
    expect(isWireframeExport({ colorMode: 'color', layout: 'portrait', answerMode: 'exclude' })).toBe(
      false
    )
    expect(isWireframeExport(undefined)).toBe(false)
  })
})
