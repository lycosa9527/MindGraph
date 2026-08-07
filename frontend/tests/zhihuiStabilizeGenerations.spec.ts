import { describe, expect, it } from 'vitest'

import {
  stabilizeZhihuiGenerations,
  type ZhihuiGenerationItem,
} from '@/stores/zhihuiHistory'

function slide(id: string, imageUrl: string): ZhihuiGenerationItem {
  return {
    id,
    prompt: 'p',
    language: 'zh',
    image_url: imageUrl,
  }
}

describe('stabilizeZhihuiGenerations', () => {
  it('keeps prior image_url when rotating sig/exp on the same asset', () => {
    const previous = [slide('a', '/api/zhihui/assets/zhihui/generations/a.png?sig=1&exp=9')]
    const next = [slide('a', '/api/zhihui/assets/zhihui/generations/a.png?sig=2&exp=99')]
    const out = stabilizeZhihuiGenerations(previous, next)
    expect(out?.[0]?.image_url).toBe(previous[0].image_url)
  })

  it('takes fresh same-origin stable URLs (no sig/exp)', () => {
    const previous = [slide('a', '/api/zhihui/assets/zhihui/generations/a.png?retry=1')]
    const next = [slide('a', '/api/zhihui/assets/zhihui/generations/a.png')]
    const out = stabilizeZhihuiGenerations(previous, next)
    expect(out?.[0]?.image_url).toBe(next[0].image_url)
  })

  it('accepts new slides and new asset paths', () => {
    const previous = [slide('a', '/api/zhihui/assets/zhihui/generations/a.png')]
    const next = [
      slide('a', '/api/zhihui/assets/zhihui/generations/a.png'),
      slide('b', '/api/zhihui/assets/zhihui/generations/b.png'),
    ]
    const out = stabilizeZhihuiGenerations(previous, next)
    expect(out).toHaveLength(2)
    expect(out?.[1]?.id).toBe('b')
  })
})
