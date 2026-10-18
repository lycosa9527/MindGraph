import { describe, expect, it } from 'vitest'

import { diagramTextDecorationStyle } from '@/utils/diagramTextDecorationStyle'
import { createToolbarPointerAction } from '@/utils/toolbarPointerAction'

describe('diagramTextDecorationStyle', () => {
  it('clears a missing decoration', () => {
    expect(diagramTextDecorationStyle(undefined)).toEqual({ textDecoration: 'none' })
    expect(diagramTextDecorationStyle('none')).toEqual({ textDecoration: 'none' })
  })

  it('paints underline and strikethrough together as a line, not a shorthand', () => {
    expect(diagramTextDecorationStyle('underline line-through')).toMatchObject({
      textDecorationLine: 'underline line-through',
      textDecorationThickness: '1px',
      textDecorationSkipInk: 'none',
    })
  })
})

describe('createToolbarPointerAction', () => {
  it('applies a touch on pointerup and ignores the following click', () => {
    const gate = createToolbarPointerAction()
    const applied: string[] = []
    const touch = { pointerType: 'touch' } as PointerEvent
    gate.onPointerUp(touch, () => applied.push('up'))
    gate.onClick(() => applied.push('click'))
    expect(applied).toEqual(['up'])
  })

  it('applies a mouse click and skips pointerup', () => {
    const gate = createToolbarPointerAction()
    const applied: string[] = []
    const mouse = { pointerType: 'mouse' } as PointerEvent
    gate.onPointerUp(mouse, () => applied.push('up'))
    gate.onClick(() => applied.push('click'))
    expect(applied).toEqual(['click'])
  })
})
