import { describe, expect, it } from 'vitest'

import {
  colorToHex,
  hexColorsEqual,
  nativeColorInputHex,
  parseAlphaFromColor,
} from '@/utils/colorFormat'

describe('colorToHex', () => {
  it('keeps a six-digit hex', () => {
    expect(colorToHex('#E7F6FD')).toBe('#E7F6FD')
  })

  it('expands a three-digit hex', () => {
    expect(colorToHex('#abc')).toBe('#aabbcc')
  })

  it('reads comma and space rgb()', () => {
    expect(colorToHex('rgb(231, 246, 253)')).toBe('#e7f6fd')
    expect(colorToHex('rgb(231 246 253)')).toBe('#e7f6fd')
  })
})

describe('nativeColorInputHex', () => {
  it('returns lowercase #rrggbb for a painted fill', () => {
    expect(nativeColorInputHex('#E7F6FD')).toBe('#e7f6fd')
  })

  it('does not send transparent to the native picker', () => {
    expect(nativeColorInputHex('transparent', '#0ba5ec')).toBe('#0ba5ec')
  })

  it('strips alpha from 8-digit hex and rgba', () => {
    expect(nativeColorInputHex('#E7F6FD99')).toBe('#e7f6fd')
    expect(nativeColorInputHex('rgba(231, 246, 253, 0.4)')).toBe('#e7f6fd')
  })

  it('falls back when the value is empty', () => {
    expect(nativeColorInputHex('', '#000000')).toBe('#000000')
    expect(nativeColorInputHex(undefined, '#ffffff')).toBe('#ffffff')
  })
})

describe('hexColorsEqual', () => {
  it('matches a palette swatch to the painted node color', () => {
    expect(hexColorsEqual('#E7F6FD', '#e7f6fd')).toBe(true)
    expect(hexColorsEqual('rgb(231, 246, 253)', '#E7F6FD')).toBe(true)
  })

  it('does not treat transparent as white or black', () => {
    expect(hexColorsEqual('transparent', '#ffffff')).toBe(false)
    expect(hexColorsEqual('transparent', '#000000')).toBe(false)
    expect(hexColorsEqual('transparent', 'transparent')).toBe(true)
  })
})

describe('parseAlphaFromColor', () => {
  it('reads rgba alpha and treats hex as opaque', () => {
    expect(parseAlphaFromColor('rgba(231, 246, 253, 0.4)')).toBe(40)
    expect(parseAlphaFromColor('#E7F6FD')).toBe(100)
  })
})
