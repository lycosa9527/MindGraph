import { beforeEach, describe, expect, it } from 'vitest'

import {
  applyRemoteSeminarHighlight,
  seminarHighlights,
} from '@/composables/mindmate/mindmateSeminarChrome'
import {
  MAX_SEMINAR_HIGHLIGHT_TEXT,
  highlightDedupeKey,
  mapSeminarHighlight,
  mergeSeminarHighlights,
  resolveSeminarHighlightBodyText,
} from '@/utils/mindmateSeminarHighlights'

const own = {
  id: 'hl-own',
  text: 'Keep this',
  authorName: 'MindMate',
  messageId: 18,
  createdAt: '2026-11-11T13:34:00+00:00',
  createdByUserId: 4,
  createdByName: 'Ada',
  messageAt: '2026-11-11T13:30:00+00:00',
}

const other = {
  id: 'hl-other',
  text: 'A second pin',
  authorName: '吴',
  messageId: 19,
  createdAt: '2026-11-11T13:40:00+00:00',
  createdByUserId: 9,
  createdByName: '吴',
  messageAt: '2026-11-11T13:31:00+00:00',
}

describe('MAX_SEMINAR_HIGHLIGHT_TEXT', () => {
  it('keeps a quoted reply well above a single sentence', () => {
    expect(MAX_SEMINAR_HIGHLIGHT_TEXT).toBe(65536)
  })
})

describe('resolveSeminarHighlightBodyText', () => {
  it('uses the live bubble when the pin is a truncated prefix', () => {
    const live = '给出三组数据：(3, 4, 5), (5, 12, 13), (6, 8, 10)。'
    expect(resolveSeminarHighlightBodyText(live.slice(0, 18), live)).toBe(live)
  })

  it('keeps a selected excerpt that is not a prefix', () => {
    const live = '前言。给出三组数据：(3, 4, 5), (5, 12, 13)。'
    expect(resolveSeminarHighlightBodyText('给出三组数据：(3, 4, 5)', live)).toBe(
      '给出三组数据：(3, 4, 5)'
    )
  })
})

describe('mapSeminarHighlight', () => {
  it('keeps the creator so the drawer can show everyone, not only me', () => {
    expect(
      mapSeminarHighlight({
        id: 'hl-1',
        text: 'Keep this',
        author_name: 'MindMate',
        message_id: 18,
        created_at: '2026-11-11T13:34:00+00:00',
        created_by_user_id: 9,
        created_by_name: '吴',
        message_at: '2026-11-11T13:30:00+00:00',
      })
    ).toMatchObject({
      createdByUserId: 9,
      createdByName: '吴',
      authorName: 'MindMate',
    })
  })
})

describe('mergeSeminarHighlights', () => {
  it('keeps a teammate pin next to a leftover local pin', () => {
    const merged = mergeSeminarHighlights([other], [own])
    expect(merged.map((item) => item.id).sort()).toEqual(['hl-other', 'hl-own'])
  })

  it('does not duplicate the same message excerpt', () => {
    expect(highlightDedupeKey(own)).toBe('18|Keep this')
    expect(mergeSeminarHighlights([own], [{ ...own, id: 'hl-copy' }])).toEqual([own])
  })
})

describe('applyRemoteSeminarHighlight', () => {
  beforeEach(() => {
    seminarHighlights.value = []
  })

  it('adds a pin from another participant', () => {
    applyRemoteSeminarHighlight('set', other)
    expect(seminarHighlights.value).toEqual([other])
  })

  it('removes a cancelled pin by id', () => {
    seminarHighlights.value = [own, other]
    applyRemoteSeminarHighlight('cancel', other)
    expect(seminarHighlights.value).toEqual([own])
  })
})
