import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import {
  DOC_SUMMARY_WEB_URL_MAX_CHARS,
  isValidDocSummaryWebUrl,
  resolveLiteDraftKind,
  waitForDocSummarySourceReady,
} from '@/composables/mindMap/useDocSummaryLiteSaveAndGenerate'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

describe('isValidDocSummaryWebUrl', () => {
  it('accepts http(s) URLs under the length cap', () => {
    expect(isValidDocSummaryWebUrl('https://example.com/a')).toBe(true)
    expect(isValidDocSummaryWebUrl('  http://example.com  ')).toBe(true)
  })

  it('rejects empty, non-http, and oversized URLs', () => {
    expect(isValidDocSummaryWebUrl('')).toBe(false)
    expect(isValidDocSummaryWebUrl('ftp://example.com')).toBe(false)
    expect(isValidDocSummaryWebUrl('not a url')).toBe(false)
    expect(isValidDocSummaryWebUrl(`https://example.com/${'x'.repeat(DOC_SUMMARY_WEB_URL_MAX_CHARS)}`)).toBe(
      false
    )
  })
})

describe('resolveLiteDraftKind', () => {
  it('returns none when a source is already bound', () => {
    expect(
      resolveLiteDraftKind({
        hasActiveSource: true,
        activeTab: 'file',
        uploadedFile: new File(['x'], 'a.pdf'),
        pastedText: 'notes',
        webUrl: 'https://example.com',
      })
    ).toBe('none')
  })

  it('detects file, paste, and valid web drafts', () => {
    expect(
      resolveLiteDraftKind({
        hasActiveSource: false,
        activeTab: 'file',
        uploadedFile: new File(['x'], 'a.pdf'),
        pastedText: '',
        webUrl: '',
      })
    ).toBe('file')

    expect(
      resolveLiteDraftKind({
        hasActiveSource: false,
        activeTab: 'file',
        uploadedFile: null,
        pastedText: '  hello  ',
        webUrl: '',
      })
    ).toBe('paste')

    expect(
      resolveLiteDraftKind({
        hasActiveSource: false,
        activeTab: 'web',
        uploadedFile: null,
        pastedText: '',
        webUrl: 'https://example.com/a',
      })
    ).toBe('web')
  })

  it('ignores invalid web URLs as drafts', () => {
    expect(
      resolveLiteDraftKind({
        hasActiveSource: false,
        activeTab: 'web',
        uploadedFile: null,
        pastedText: '',
        webUrl: 'example.com',
      })
    ).toBe('none')
  })
})

describe('waitForDocSummarySourceReady', () => {
  it('returns completed when the first document is ready', async () => {
    const documents = ref<KnowledgeDocument[]>([
      { id: 1, status: 'completed' } as KnowledgeDocument,
    ])
    const detailQuery = {
      refetch: vi.fn().mockResolvedValue(undefined),
    }

    await expect(
      waitForDocSummarySourceReady({
        detailQuery: detailQuery as never,
        documents,
        timeoutMs: 2_000,
      })
    ).resolves.toBe('completed')
    expect(detailQuery.refetch).toHaveBeenCalled()
  })

  it('returns failed when documents become empty', async () => {
    const documents = ref<KnowledgeDocument[]>([])
    const detailQuery = {
      refetch: vi.fn().mockResolvedValue(undefined),
    }

    await expect(
      waitForDocSummarySourceReady({
        detailQuery: detailQuery as never,
        documents,
        timeoutMs: 2_000,
      })
    ).resolves.toBe('failed')
  })

  it('returns failed when extract fails', async () => {
    const documents = ref<KnowledgeDocument[]>([
      { id: 1, status: 'failed' } as KnowledgeDocument,
    ])
    const detailQuery = {
      refetch: vi.fn().mockResolvedValue(undefined),
    }

    await expect(
      waitForDocSummarySourceReady({
        detailQuery: detailQuery as never,
        documents,
        timeoutMs: 2_000,
      })
    ).resolves.toBe('failed')
  })

  it('returns timeout when status stays processing', async () => {
    vi.useFakeTimers()
    const documents = ref<KnowledgeDocument[]>([
      { id: 1, status: 'processing' } as KnowledgeDocument,
    ])
    const detailQuery = {
      refetch: vi.fn().mockResolvedValue(undefined),
    }

    const pending = waitForDocSummarySourceReady({
      detailQuery: detailQuery as never,
      documents,
      timeoutMs: 1_200,
    })
    await vi.advanceTimersByTimeAsync(1_500)
    await expect(pending).resolves.toBe('timeout')
    vi.useRealTimers()
  })
})
