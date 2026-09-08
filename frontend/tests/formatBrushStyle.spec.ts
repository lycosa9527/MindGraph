import { describe, expect, it } from 'vitest'

import {
  collectFormatBrushStyle,
  formatBrushTargetsFromSelection,
  pickFormatBrushStyle,
  resolveFormatPainterClick,
} from '@/composables/canvasToolbar/formatBrushStyle'

describe('formatBrushStyle', () => {
  it('copies persisted _node_styles over empty inline style', () => {
    const copied = collectFormatBrushStyle(
      undefined,
      { backgroundColor: '#ebf3fe', textColor: '#175cd3', borderColor: '#2e90fa' },
      { backgroundColor: '#ffffff', fontSize: 14 }
    )
    expect(copied.backgroundColor).toBe('#ebf3fe')
    expect(copied.textColor).toBe('#175cd3')
    expect(copied.borderColor).toBe('#2e90fa')
    expect(copied.fontSize).toBe(14)
  })

  it('lets inline node.style win over persisted and theme fallbacks', () => {
    const copied = collectFormatBrushStyle(
      { backgroundColor: '#ff0000', fontWeight: 'bold' },
      { backgroundColor: '#00ff00', textColor: '#111111' },
      { backgroundColor: '#0000ff', textColor: '#222222', fontSize: 16 }
    )
    expect(copied.backgroundColor).toBe('#ff0000')
    expect(copied.textColor).toBe('#111111')
    expect(copied.fontWeight).toBe('bold')
    expect(copied.fontSize).toBe(16)
  })

  it('keeps accentBarWidth 0 so a painted node can clear a rainbow bar', () => {
    const copied = pickFormatBrushStyle({ accentBarWidth: 0, accentBarColor: '#2e90fa' })
    expect(copied.accentBarWidth).toBe(0)
    expect(copied.accentBarColor).toBe('#2e90fa')
  })

  it('does not paint layout size keys', () => {
    const copied = pickFormatBrushStyle({
      backgroundColor: '#fff',
      width: 400,
      height: 80,
      size: 40,
    })
    expect(copied.backgroundColor).toBe('#fff')
    expect(copied.width).toBeUndefined()
    expect(copied.height).toBeUndefined()
    expect(copied.size).toBeUndefined()
  })

  it('applies to newly selected nodes and skips the source', () => {
    expect(formatBrushTargetsFromSelection(['a'], ['a'])).toEqual([])
    expect(formatBrushTargetsFromSelection(['b'], ['a'])).toEqual(['b'])
    expect(formatBrushTargetsFromSelection(['a', 'b'], ['a'])).toEqual(['b'])
  })

  it('uses theme fallbacks when neither inline nor persisted style is set', () => {
    const copied = collectFormatBrushStyle(undefined, undefined, {
      backgroundColor: '#e3f2fd',
      fontSize: 14,
      nodeShape: 'rounded',
    })
    expect(copied.backgroundColor).toBe('#e3f2fd')
    expect(copied.fontSize).toBe(14)
    expect(copied.nodeShape).toBe('rounded')
  })

  it('skips empty selection and keeps source nodes unpainted', () => {
    expect(formatBrushTargetsFromSelection([], ['a'])).toEqual([])
    expect(formatBrushTargetsFromSelection([''], ['a'])).toEqual([''])
  })

  it('locks immediately when the painter requests lock from idle', () => {
    expect(
      resolveFormatPainterClick({
        active: false,
        locked: false,
        lockRequested: true,
        elapsedMs: 0,
      })
    ).toBe('lock')
  })

  it('locks on the double-click window boundary and cancels just after it', () => {
    expect(
      resolveFormatPainterClick({
        active: true,
        locked: false,
        lockRequested: false,
        elapsedMs: 500,
      })
    ).toBe('lock')
    expect(
      resolveFormatPainterClick({
        active: true,
        locked: false,
        lockRequested: false,
        elapsedMs: 501,
      })
    ).toBe('cancel')
  })

  it('treats a second painter click in the double-click window as lock, not cancel', () => {
    expect(
      resolveFormatPainterClick({
        active: false,
        locked: false,
        lockRequested: false,
        elapsedMs: 10_000,
      })
    ).toBe('activate')
    expect(
      resolveFormatPainterClick({
        active: true,
        locked: false,
        lockRequested: false,
        elapsedMs: 120,
      })
    ).toBe('lock')
    expect(
      resolveFormatPainterClick({
        active: true,
        locked: false,
        lockRequested: false,
        elapsedMs: 800,
      })
    ).toBe('cancel')
    expect(
      resolveFormatPainterClick({
        active: true,
        locked: true,
        lockRequested: true,
        elapsedMs: 50,
      })
    ).toBe('noop')
    expect(
      resolveFormatPainterClick({
        active: true,
        locked: true,
        lockRequested: false,
        elapsedMs: 800,
      })
    ).toBe('cancel')
  })
})
