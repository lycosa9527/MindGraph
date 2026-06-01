import { describe, expect, it } from 'vitest'

import {
  DIAGRAM_SAVE_LIMIT_UNLIMITED,
  formatDiagramCountLabel,
  hasDiagramSaveLimit,
} from '@/utils/diagramLimit'

describe('diagramLimit utils', () => {
  it('treats zero as unlimited', () => {
    expect(DIAGRAM_SAVE_LIMIT_UNLIMITED).toBe(0)
    expect(hasDiagramSaveLimit(0)).toBe(false)
    expect(hasDiagramSaveLimit(20)).toBe(true)
  })

  it('formats capped and unlimited counts', () => {
    expect(formatDiagramCountLabel(5, 20)).toBe('5/20')
    expect(formatDiagramCountLabel(42, 0)).toBe('42')
  })
})
