import { afterEach, describe, expect, it, vi } from 'vitest'

import { deliverExportFile } from '@/utils/deliverExportFile'

const IPHONE_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

const DESKTOP_UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

function stubClient(width: number, userAgent: string, extras: Record<string, unknown> = {}): void {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width })
  vi.stubGlobal('navigator', { userAgent, ...extras })
}

describe('deliverExportFile', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('downloads on desktop without opening the share sheet', async () => {
    const share = vi.fn()
    stubClient(1280, DESKTOP_UA, { share })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    const result = await deliverExportFile(new Blob(['png'], { type: 'image/png' }), 'map.png')

    expect(result).toBe('downloaded')
    expect(share).not.toHaveBeenCalled()
    expect(click).toHaveBeenCalledOnce()
  })

  it('opens the system share sheet on a phone', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    const canShare = vi.fn().mockReturnValue(true)
    stubClient(390, IPHONE_UA, { share, canShare })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    const result = await deliverExportFile(new Blob(['png'], { type: 'image/png' }), 'map.png')

    expect(result).toBe('shared')
    expect(share).toHaveBeenCalledOnce()
    const payload = share.mock.calls[0][0] as { files: File[]; title: string }
    expect(payload.title).toBe('map.png')
    expect(payload.files[0]).toBeInstanceOf(File)
    expect(payload.files[0].name).toBe('map.png')
    expect(payload.files[0].type).toBe('image/png')
    expect(click).not.toHaveBeenCalled()
  })

  it('does not download when the share sheet is dismissed', async () => {
    const abort = new DOMException('cancelled', 'AbortError')
    const share = vi.fn().mockRejectedValue(abort)
    const canShare = vi.fn().mockReturnValue(true)
    stubClient(390, IPHONE_UA, { share, canShare })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    const result = await deliverExportFile(
      new Blob(['pdf'], { type: 'application/pdf' }),
      'map.pdf'
    )

    expect(result).toBe('cancelled')
    expect(click).not.toHaveBeenCalled()
  })

  it('downloads when the phone cannot share that file type', async () => {
    const share = vi.fn()
    const canShare = vi.fn().mockReturnValue(false)
    stubClient(390, IPHONE_UA, { share, canShare })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    const result = await deliverExportFile(
      new Blob(['mg'], { type: 'application/octet-stream' }),
      'map.mg'
    )

    expect(result).toBe('downloaded')
    expect(share).not.toHaveBeenCalled()
    expect(click).toHaveBeenCalledOnce()
  })
})
