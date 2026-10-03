import { describe, expect, it } from 'vitest'

import {
  applySpecArrayText,
  padMirrorStringList,
  spliceMirrorList,
  writeMirrorScalar,
} from '@/composables/editor/diagramOperationGloss'
import { renderMindMapSvgText } from '@/utils/diagramMindMapVectorText'

describe('diagram operation gloss', () => {
  it('updates a string slot and the parallel secondary list', () => {
    const spec: Record<string, unknown> = {
      topic: '苹果',
      context: ['红色', '甜'],
      secondary: { topic: 'Apple', context: ['red', 'sweet'] },
    }
    writeMirrorScalar(spec, 'topic', 'Apple fruit')
    applySpecArrayText(spec, 'context', 1, '酸', 'sour')
    expect(spec.topic).toBe('苹果')
    expect(spec.context).toEqual(['红色', '酸'])
    expect(spec.secondary).toEqual({ topic: 'Apple fruit', context: ['red', 'sour'] })
  })

  it('leaves a mono spec unchanged when there is no mirror', () => {
    const spec: Record<string, unknown> = { topic: '苹果', context: ['红色'] }
    writeMirrorScalar(spec, 'topic', 'Apple')
    applySpecArrayText(spec, 'context', 0, '绿色', 'green')
    padMirrorStringList(spec, 'context')
    expect(spec).toEqual({ topic: '苹果', context: ['绿色'] })
  })

  it('keeps object nodes and splices the mirror with the primary list', () => {
    const spec: Record<string, unknown> = {
      children: [{ text: '动物', textSecondary: 'Animals' }],
      secondary: { children: [{ text: 'Animals' }] },
    }
    applySpecArrayText(spec, 'children', 0, '植物', 'Plants')
    expect(spec.children).toEqual([{ text: '植物', textSecondary: 'Plants' }])
    expect((spec.secondary as { children: unknown[] }).children).toEqual([{ text: 'Plants' }])
    padMirrorStringList(spec, 'children')
    expect((spec.secondary as { children: unknown[] }).children).toHaveLength(1)
    ;(spec.children as unknown[]).push('新')
    ;(spec.secondary as { children: unknown[] }).children.push({ text: 'New' })
    spliceMirrorList(spec, 'children', 0)
    expect((spec.secondary as { children: unknown[] }).children).toEqual([{ text: 'New' }])
  })

  it('pads a string mirror when a primary slot is added', () => {
    const spec: Record<string, unknown> = {
      attributes: ['圆'],
      secondary: { attributes: ['round'] },
    }
    ;(spec.attributes as string[]).push('红')
    padMirrorStringList(spec, 'attributes')
    expect(spec.secondary).toEqual({ attributes: ['round', ''] })
  })
})

describe('mind-map vector secondary line', () => {
  const box = {
    x: 0,
    y: 0,
    width: 160,
    height: 48,
    fontSize: 16,
    textColor: '#111',
    paddingX: 8,
    paddingY: 4,
  }

  it('omits the gloss element when the second line is empty', () => {
    const svg = renderMindMapSvgText({ ...box, rawText: '动物' })
    expect(svg).not.toContain('opacity="0.7"')
    expect(svg).toContain('动物')
  })

  it('draws the second line smaller and stacked under the primary line', () => {
    const mono = renderMindMapSvgText({ ...box, rawText: '动物' })
    const bilingual = renderMindMapSvgText({ ...box, rawText: '动物', rawSecondary: 'Animals' })
    expect(bilingual).toContain('opacity="0.7"')
    expect(bilingual).toContain('font-size="12"')
    expect(bilingual).toContain('Animals')
    expect(bilingual).not.toBe(mono)
  })

  it('wraps a long second line inside the node', () => {
    const svg = renderMindMapSvgText({
      ...box,
      width: 80,
      rawText: '动物',
      rawSecondary: 'photosynthesis process',
    })
    const gloss = svg.split('opacity="0.7"')[1] ?? ''
    expect(gloss.match(/<tspan/g)?.length ?? 0).toBeGreaterThan(1)
  })
})
