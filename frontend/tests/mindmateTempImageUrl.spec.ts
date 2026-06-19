import { describe, expect, it } from 'vitest'

import {
  rewriteMindmateTempImageUrls,
  shouldProxyMindmateTempImageUrl,
  shouldRewriteMindmateTempImageUrl,
} from '@/utils/mindmateTempImageUrl'

describe('shouldRewriteMindmateTempImageUrl', () => {
  it('rewrites loopback hosts', () => {
    expect(shouldRewriteMindmateTempImageUrl(new URL('http://localhost:9527/x'))).toBe(true)
    expect(shouldRewriteMindmateTempImageUrl(new URL('http://127.0.0.1:9527/x'))).toBe(true)
  })

  it('does not rewrite remote deployment hosts', () => {
    expect(
      shouldRewriteMindmateTempImageUrl(new URL('https://mindgraph.example.com/x'), 'localhost:41732')
    ).toBe(false)
  })

  it('rewrites when host matches the page', () => {
    expect(
      shouldRewriteMindmateTempImageUrl(
        new URL('https://app.example.com/api/temp_images/a.png'),
        'app.example.com'
      )
    ).toBe(true)
  })
})

describe('shouldProxyMindmateTempImageUrl', () => {
  it('proxies known MindGraph deployment hosts', () => {
    const url = new URL('https://mg.mindspringedu.com/api/temp_images/a.png?sig=x')
    expect(shouldProxyMindmateTempImageUrl(url, 'localhost:41732')).toBe(true)
  })
})

describe('rewriteMindmateTempImageUrls', () => {
  it('rewrites loopback temp image urls to same-origin api path', () => {
    const content =
      '![](http://localhost:9527/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&exp=1)'
    expect(rewriteMindmateTempImageUrls(content)).toBe(
      '![](/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x&exp=1)'
    )
  })

  it('proxies whitelisted remote temp image urls', () => {
    const remote =
      'https://mg.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x'
    const content = `![](${remote})`
    expect(rewriteMindmateTempImageUrls(content, 'localhost:41732')).toBe(
      `![](/api/proxy-image?url=${encodeURIComponent(remote)})`
    )
  })

  it('proxies any remote temp image url when the page is local dev', () => {
    const remote =
      'https://other.example.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x'
    const content = `![](${remote})`
    expect(rewriteMindmateTempImageUrls(content, 'localhost:41732')).toBe(
      `![](/api/proxy-image?url=${encodeURIComponent(remote)})`
    )
  })

  it('leaves unknown remote temp image urls unchanged on production page host', () => {
    const content =
      '![](https://mindgraph.example.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(rewriteMindmateTempImageUrls(content, 'mg.mindspringedu.com')).toBe(content)
  })
})
