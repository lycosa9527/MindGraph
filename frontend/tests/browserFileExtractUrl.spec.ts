import { describe, expect, it } from 'vitest'

import { urlRequiresBrowserFileExtract } from '@/utils/browserFileExtractUrl'

describe('urlRequiresBrowserFileExtract', () => {
  it('flags lesson and paper hosts and leaves ordinary pages alone', () => {
    expect(
      urlRequiresBrowserFileExtract('https://basic.smartedu.cn/syncClassroom/classActivity?activityId=abc'),
    ).toBe(true)
    expect(urlRequiresBrowserFileExtract('https://kns.cnki.net/kcms2/article/abstract?v=abc')).toBe(true)
    expect(urlRequiresBrowserFileExtract('https://wenku.baidu.com/view/abc.html')).toBe(true)
    expect(urlRequiresBrowserFileExtract('https://example.com/article')).toBe(false)
    expect(urlRequiresBrowserFileExtract('not a url')).toBe(false)
  })
})
