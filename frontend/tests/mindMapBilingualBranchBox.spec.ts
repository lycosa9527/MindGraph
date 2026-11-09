import { describe, expect, it } from 'vitest'

import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { BILINGUAL_SECONDARY_LINE_HEIGHT, secondaryFontSize } from '@/diagramBilingual/measure'
import { withMindMapBranchSecondaryBox } from '@/stores/specLoader/mindMapMeasurements'
import { resolveMindMapBranchBodyMaxWidthPx } from '@/utils/mindMapTextWrap'

const fontSize = MIND_MAP_GEOMETRY.fontSize
const glossLine = Math.ceil(secondaryFontSize(fontSize) * BILINGUAL_SECONDARY_LINE_HEIGHT)

describe('withMindMapBranchSecondaryBox', () => {
  it('returns the primary box when there is no gloss', () => {
    const box = { width: 120, height: 40 }
    expect(withMindMapBranchSecondaryBox(box, '记忆', '', '  ', { shape: 'underline' })).toBe(box)
  })

  it('widens a short CJK label to fit a longer English line', () => {
    const box = { width: 100, height: 40 }
    const out = withMindMapBranchSecondaryBox(
      box,
      '记忆：数据基础与术语',
      '',
      'Remember: Data Fundamentals and Terminology',
      { shape: 'rounded', font: { fontSize } }
    )
    expect(out.width).toBeGreaterThan(box.width)
    expect(out.height).toBe(box.height + glossLine)
  })

  it('reserves every wrapped gloss line and caps width at the label column', () => {
    const label = '识别常见游戏数据指标（DAU、ARPU、留存率等）以及更多的补充说明文字'
    const gloss =
      'Identify common game data metrics (DAU, ARPU, retention rate, etc.) and much more supporting text'
    const column = resolveMindMapBranchBodyMaxWidthPx(label, '', fontSize)
    const out = withMindMapBranchSecondaryBox({ width: 50, height: 40 }, label, '', gloss, {
      shape: 'underline',
      font: { fontSize },
    })
    expect(out.height).toBeGreaterThanOrEqual(40 + 2 * glossLine)
    expect(out.width).toBeLessThanOrEqual(Math.ceil(column) + 40)
  })
})
