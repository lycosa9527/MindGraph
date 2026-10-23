import { describe, expect, it } from 'vitest'

import { diagramFontTokensInUse, diagramPaintFontFamily } from '@/fonts/diagramCanvasFonts'
import type { DiagramData } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

describe('diagramPaintFontFamily', () => {
  it('keeps the default stack and unknown families', () => {
    expect(diagramPaintFontFamily(undefined)).toBe(DIAGRAM_NODE_FONT_STACK)
    expect(diagramPaintFontFamily('  ')).toBe(DIAGRAM_NODE_FONT_STACK)
    expect(diagramPaintFontFamily(DIAGRAM_NODE_FONT_STACK)).toBe(DIAGRAM_NODE_FONT_STACK)
    expect(diagramPaintFontFamily('Comic Sans MS')).toBe('Comic Sans MS')
  })

  it('maps desktop face names to stacks phones can paint', () => {
    const song = diagramPaintFontFamily('SimSun')
    expect(song.startsWith('SimSun,')).toBe(true)
    expect(song).toContain('Songti SC')
    expect(song).toContain('Noto Serif SC')

    const kai = diagramPaintFontFamily('KaiTi')
    expect(kai.startsWith('KaiTi,')).toBe(true)
    expect(kai).toContain('Kaiti SC')
    expect(kai).toContain('LXGW WenKai Screen')

    expect(diagramPaintFontFamily('Space Grotesk')).toContain('Space Grotesk')
    expect(diagramPaintFontFamily('Inter')).toContain('Noto Sans SC')
    expect(diagramPaintFontFamily('Microsoft YaHei')).toContain('PingFang SC')
    expect(diagramPaintFontFamily('Arial')).toContain('Noto Sans')
  })

  it('leaves an already-resolved stack unchanged', () => {
    const song = diagramPaintFontFamily('SimSun')
    expect(diagramPaintFontFamily(song)).toBe(song)
  })
})

describe('diagramFontTokensInUse', () => {
  it('collects webfont tokens from nodes and mind-map style maps', () => {
    const data = {
      nodes: [
        { id: 'topic', text: '主题', type: 'topic', style: { fontFamily: 'SimSun' } },
        { id: 'b1', text: '枝', type: 'branch', style: { fontFamily: DIAGRAM_NODE_FONT_STACK } },
      ],
      connections: [],
      _node_styles: {
        b2: { fontFamily: 'KaiTi' },
        b3: { fontFamily: 'SimSun' },
        b4: { fontFamily: 'Comic Sans MS' },
      },
    } as unknown as DiagramData

    expect(diagramFontTokensInUse(data)).toEqual(['SimSun', 'KaiTi'])
    expect(diagramFontTokensInUse(null)).toEqual([])
  })
})
