/** Vitest — clipboard helper with Clipboard API + DOM fallback. */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { copyTextToClipboard } from '@/utils/copyTextToClipboard'

describe('copyTextToClipboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('uses navigator.clipboard.writeText when available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })

    await copyTextToClipboard('hello stacktrace')

    expect(writeText).toHaveBeenCalledWith('hello stacktrace')
  })

  it('falls back to execCommand when Clipboard API rejects', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const execCommand = vi.fn().mockReturnValue(true)
    Object.defineProperty(document, 'execCommand', {
      configurable: true,
      writable: true,
      value: execCommand,
    })

    await copyTextToClipboard('fallback text')

    expect(execCommand).toHaveBeenCalledWith('copy')
  })

  it('rejects empty payloads', async () => {
    await expect(copyTextToClipboard('   \n')).rejects.toThrow('Nothing to copy')
  })
})
