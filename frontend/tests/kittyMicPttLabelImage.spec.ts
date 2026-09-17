import { describe, expect, it } from 'vitest'

import {
  escapeSvgText,
  kittyMicPttLabelImageSrc,
  resolveKittyMicPttLabelText,
} from '@/utils/kittyMicPttLabelImage'

describe('kittyMicPttLabelImage', () => {
  it('picks hold / release / auto copy', () => {
    const translate = (key: string, fallback: string) => fallback
    expect(resolveKittyMicPttLabelText('manual', false, false, translate)).toBe('按住说话')
    expect(resolveKittyMicPttLabelText('manual', false, true, translate)).toBe('松开发送')
    expect(resolveKittyMicPttLabelText('manual', true, false, translate)).toBe('松开发送')
    expect(resolveKittyMicPttLabelText('auto', false, false, translate)).toBe('点按开始听')
    expect(resolveKittyMicPttLabelText('auto', true, false, translate)).toBe('点按停止')
  })

  it('bakes the label into an SVG image, not a text node', () => {
    const src = kittyMicPttLabelImageSrc('按住说话')
    expect(src.startsWith('data:image/svg+xml;charset=utf-8,')).toBe(true)
    const svg = decodeURIComponent(src.slice('data:image/svg+xml;charset=utf-8,'.length))
    expect(svg).toContain('>按住说话</text>')
    expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"')
  })

  it('escapes markup so the image source stays valid', () => {
    expect(escapeSvgText(`<a&b>'"`)).toBe('&lt;a&amp;b&gt;&apos;&quot;')
    const src = kittyMicPttLabelImageSrc('A&B')
    const svg = decodeURIComponent(src.slice('data:image/svg+xml;charset=utf-8,'.length))
    expect(svg).toContain('>A&amp;B</text>')
  })
})
