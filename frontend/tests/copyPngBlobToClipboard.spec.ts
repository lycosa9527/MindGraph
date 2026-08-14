/** Vitest — Async Clipboard API helper (Excalidraw PNG pattern). */
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  canWriteImageToClipboard,
  copyPngBlobToClipboard,
  copyPngBlobWithFallback,
} from '@/utils/copyPngBlobToClipboard'

function stubClipboardWrite(): ReturnType<typeof vi.fn> {
  const write = vi
    .fn()
    .mockImplementation(async (items: { items: Record<string, Blob | Promise<Blob>> }[]) => {
      for (const item of items) {
        const value = item.items['image/png']
        await (value instanceof Promise ? value : Promise.resolve(value))
      }
    })
  vi.stubGlobal('navigator', { clipboard: { write } })
  vi.stubGlobal(
    'ClipboardItem',
    class {
      readonly items: Record<string, Blob | Promise<Blob>>
      constructor(items: Record<string, Blob | Promise<Blob>>) {
        this.items = items
      }
    }
  )
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
  return write
}

describe('copyPngBlobToClipboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('calls clipboard.write before the capture promise settles', async () => {
    const write = stubClipboardWrite()
    let resolveBlob: (blob: Blob) => void = () => undefined
    const source = new Promise<Blob>((resolve) => {
      resolveBlob = resolve
    })
    const pending = copyPngBlobToClipboard(source)
    expect(write).toHaveBeenCalledTimes(1)
    resolveBlob(new Blob(['png-bytes'], { type: 'image/png' }))
    await pending
  })

  it('passes the capture Promise through ClipboardItem image/png', async () => {
    const write = stubClipboardWrite()
    const blob = new Blob(['png-bytes'], { type: 'image/png' })
    const source = Promise.resolve(blob)

    await copyPngBlobToClipboard(source)

    expect(write).toHaveBeenCalledTimes(1)
    const [items] = write.mock.calls[0] as [{ items: Record<string, Promise<Blob>> }[]]
    expect(items[0].items['image/png']).toBe(source)
  })

  it('retries with the resolved Blob when Promise ClipboardItem is rejected', async () => {
    const write = stubClipboardWrite()
    const blob = new Blob(['png-bytes'], { type: 'image/png' })
    const source = Promise.resolve(blob)
    write.mockRejectedValueOnce(new Error('Type image/png not supported'))

    await copyPngBlobToClipboard(source)

    expect(write).toHaveBeenCalledTimes(2)
    const [secondItems] = write.mock.calls[1] as [{ items: Record<string, Blob> }[]]
    expect(secondItems[0].items['image/png']).toBe(blob)
  })

  it('rejects when ClipboardItem is unavailable', async () => {
    vi.stubGlobal('navigator', { clipboard: { write: vi.fn() } })
    vi.stubGlobal('ClipboardItem', undefined)
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })

    await expect(copyPngBlobToClipboard(new Blob(['x'], { type: 'image/png' }))).rejects.toThrow(
      'Clipboard image write is not supported'
    )
  })

  it('requires a secure context', () => {
    vi.stubGlobal('navigator', { clipboard: { write: vi.fn() } })
    vi.stubGlobal('ClipboardItem', class {})
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false })
    expect(canWriteImageToClipboard()).toBe(false)
  })
})

describe('copyPngBlobWithFallback', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('downloads when clipboard write is unsupported', async () => {
    vi.stubGlobal('navigator', { clipboard: {} })
    vi.stubGlobal('ClipboardItem', undefined)
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
    const download = vi.fn()
    const blob = new Blob(['png-bytes'], { type: 'image/png' })

    await expect(copyPngBlobWithFallback(Promise.resolve(blob), download)).resolves.toBe(
      'downloaded'
    )
    expect(download).toHaveBeenCalledWith(blob)
  })

  it('does not download when capture itself fails', async () => {
    stubClipboardWrite()
    const download = vi.fn()
    const source = Promise.reject(new Error('capture failed'))

    await expect(copyPngBlobWithFallback(source, download)).rejects.toThrow()
    expect(download).not.toHaveBeenCalled()
  })
})
