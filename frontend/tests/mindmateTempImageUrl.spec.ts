import { describe, expect, it } from 'vitest'

import {
  rewriteMindmateTempImageUrls,
  sameOriginTempImageFetchUrl,
  shouldProxyMindmateTempImageUrl,
  shouldRewriteMindmateTempImageUrl,
  toPublicHttpsUrl,
} from '@/utils/mindmateTempImageUrl'

describe('shouldRewriteMindmateTempImageUrl', () => {
  it('rewrites loopback hosts', () => {
    expect(shouldRewriteMindmateTempImageUrl(new URL('http://localhost:9527/x'))).toBe(true)
    expect(shouldRewriteMindmateTempImageUrl(new URL('http://127.0.0.1:9527/x'))).toBe(true)
  })

  it('does not rewrite remote deployment hosts', () => {
    expect(
      shouldRewriteMindmateTempImageUrl(
        new URL('https://mindgraph.example.com/x'),
        'localhost:41732'
      )
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

describe('sameOriginTempImageFetchUrl', () => {
  it('rewrites a test-server temp url to the local api path', () => {
    const remote = 'https://test.mindspringedu.com/api/temp_images/diagram_abc.png?sig=x&exp=1'
    expect(sameOriginTempImageFetchUrl(remote)).toBe('/api/temp_images/diagram_abc.png?sig=x&exp=1')
  })

  it('keeps an already-relative temp path', () => {
    expect(sameOriginTempImageFetchUrl('/api/temp_images/diagram_abc.png?sig=x')).toBe(
      '/api/temp_images/diagram_abc.png?sig=x'
    )
  })
})

describe('toPublicHttpsUrl', () => {
  it('upgrades a public http url and keeps loopback', () => {
    expect(toPublicHttpsUrl('http://mg.mindspringedu.com/api/temp_images/a.png?sig=1')).toBe(
      'https://www.mindspringedu.com/api/temp_images/a.png?sig=1'
    )
    expect(toPublicHttpsUrl('http://localhost:9527/api/temp_images/a.png')).toBe(
      'http://localhost:9527/api/temp_images/a.png'
    )
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
    const canonical = remote.replace('mg.mindspringedu.com', 'www.mindspringedu.com')
    const content = `![](${remote})`
    expect(rewriteMindmateTempImageUrls(content, 'localhost:41732')).toBe(
      `![](/api/proxy-image?url=${encodeURIComponent(canonical)})`
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

  it('proxies an http deployment host as https', () => {
    const remote =
      'http://mg.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x'
    const secure = 'https://www.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x'
    const content = `![](${remote})`
    expect(rewriteMindmateTempImageUrls(content, 'localhost:41732')).toBe(
      `![](/api/proxy-image?url=${encodeURIComponent(secure)})`
    )
  })

  it('upgrades a public http preview that stays absolute', () => {
    const content =
      '![](http://mindgraph.example.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(rewriteMindmateTempImageUrls(content, 'mg.mindspringedu.com')).toBe(
      content.replace('http://', 'https://')
    )
  })

  it('rewrites a legacy mg temp image onto the www page origin', () => {
    const content =
      '![](https://mg.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(rewriteMindmateTempImageUrls(content, 'www.mindspringedu.com')).toBe(
      '![](/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    )
  })

  it('leaves unknown remote temp image urls unchanged on production page host', () => {
    const content =
      '![](https://mindgraph.example.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)'
    expect(rewriteMindmateTempImageUrls(content, 'mg.mindspringedu.com')).toBe(content)
  })
})
