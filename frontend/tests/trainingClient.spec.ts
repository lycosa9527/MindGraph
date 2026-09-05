import { afterEach, describe, expect, it, vi } from 'vitest'

import { MINDGRAPH_HEADLESS_EXPORT_KEY } from '@/utils/headlessExportSession'
import { resetOfficeEmbedForTests } from '@/utils/officeEmbed'
import {
  isTrainingRailVisible,
  shouldSkipTrainingFollow,
  trainingEventsUrl,
  windowedRosterRows,
} from '@/utils/trainingClient'

describe('trainingClient', () => {
  afterEach(() => {
    sessionStorage.clear()
    resetOfficeEmbedForTests()
    vi.unstubAllGlobals()
  })

  it('skips headless export, word add-in, and export-render', () => {
    expect(shouldSkipTrainingFollow('/mindmate')).toBe(false)
    sessionStorage.setItem(MINDGRAPH_HEADLESS_EXPORT_KEY, '1')
    expect(shouldSkipTrainingFollow('/canvas')).toBe(true)
    sessionStorage.clear()
    expect(shouldSkipTrainingFollow('/export-render')).toBe(true)
    sessionStorage.setItem('mg_office_embed_client', 'word-addin')
    expect(shouldSkipTrainingFollow('/canvas')).toBe(true)
  })

  it('adds org_id only for platform instructors', () => {
    expect(trainingEventsUrl(12, true)).toBe('/api/training/events?org_id=12')
    expect(trainingEventsUrl(12, false)).toBe('/api/training/events')
    expect(trainingEventsUrl(null, true)).toBe('/api/training/events')
  })

  it('hides the friends rail from teachers', () => {
    expect(isTrainingRailVisible(false, true)).toBe(false)
    expect(isTrainingRailVisible(true, true)).toBe(true)
    expect(isTrainingRailVisible(true, false)).toBe(false)
  })

  it('windows long roster lists', () => {
    const rows = Array.from({ length: 80 }, (_, index) => index)
    expect(windowedRosterRows(rows, 50)).toHaveLength(50)
    expect(windowedRosterRows(rows.slice(0, 10), 50)).toHaveLength(10)
  })
})
