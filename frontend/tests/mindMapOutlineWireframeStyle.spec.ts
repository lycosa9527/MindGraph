import { describe, expect, it } from 'vitest'

import {
  OUTLINE_WIREFRAME_EDGE,
  OUTLINE_WIREFRAME_FILL,
  OUTLINE_WIREFRAME_INK,
  applyMindMapOutlineWireframeNodeStyle,
  applyMindMapOutlineWireframeUnderlineBar,
  resolveMindMapOutlineWireframeEdgeStroke,
} from '@/utils/mindMapOutlineWireframeStyle'

describe('mindMapOutlineWireframeStyle', () => {
  it('converts filled nodes to white boxes with black ink', () => {
    const styled = applyMindMapOutlineWireframeNodeStyle({
      backgroundColor: '#1976d2',
      color: '#ffffff',
      borderColor: '#0d47a1',
      borderWidth: '3px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
    })

    expect(styled.backgroundColor).toBe(OUTLINE_WIREFRAME_FILL)
    expect(styled.color).toBe(OUTLINE_WIREFRAME_INK)
    expect(styled.borderColor).toBe(OUTLINE_WIREFRAME_INK)
    expect(styled.boxShadow).toBe('none')
    expect(styled.backgroundImage).toBe('none')
  })

  it('keeps underline nodes transparent with black text only', () => {
    const styled = applyMindMapOutlineWireframeNodeStyle(
      {
        backgroundColor: '#dbeafe',
        color: '#1d4ed8',
      },
      { isUnderline: true }
    )

    expect(styled.backgroundColor).toBe('transparent')
    expect(styled.color).toBe(OUTLINE_WIREFRAME_INK)
    expect(styled.boxShadow).toBe('none')
  })

  it('renders underline bars as solid black', () => {
    const styled = applyMindMapOutlineWireframeUnderlineBar({
      backgroundColor: '#2563eb',
      opacity: 0.7,
    })

    expect(styled.backgroundColor).toBe(OUTLINE_WIREFRAME_INK)
    expect(styled.opacity).toBe(1)
  })

  it('resolves edge stroke color for outline export', () => {
    expect(resolveMindMapOutlineWireframeEdgeStroke()).toBe(OUTLINE_WIREFRAME_EDGE)
  })
})
