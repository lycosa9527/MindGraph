import { afterEach, describe, expect, it, vi } from 'vitest'

import { MINDGRAPH_HEADLESS_EXPORT_KEY } from '@/utils/headlessExportSession'
import { resetOfficeEmbedForTests } from '@/utils/officeEmbed'
import {
  emptyTrainingSnapshot,
  canOpenTrainingEvents,
  isTrainingOwnerHeartbeat,
  isTrainingRailVisible,
  isTrainingRemotePath,
  shouldHideTrainingDesktopChrome,
  shouldHoldTrainingHostOnMobile,
  shouldSkipTrainingFollow,
  TRAINING_RAIL_VISIBLE_ROWS,
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

  it('does not open SSE for a platform lead until an org is known', () => {
    expect(canOpenTrainingEvents(true, null)).toBe(false)
    expect(canOpenTrainingEvents(true, 12)).toBe(true)
    expect(canOpenTrainingEvents(false, null)).toBe(true)
  })

  it('hides the friends rail from teachers', () => {
    expect(isTrainingRailVisible(false, true)).toBe(false)
    expect(isTrainingRailVisible(true, true)).toBe(true)
    expect(isTrainingRailVisible(true, false)).toBe(false)
  })

  it('builds an empty command snapshot', () => {
    expect(emptyTrainingSnapshot()).toMatchObject({
      state: 'none',
      session_id: null,
      org_id: null,
      seq: 0,
    })
  })

  it('heartbeats only the hosting instructor', () => {
    expect(isTrainingOwnerHeartbeat(true, true, 3, 3)).toBe(true)
    expect(isTrainingOwnerHeartbeat(true, true, 3, 9)).toBe(false)
    expect(isTrainingOwnerHeartbeat(false, true, 3, 3)).toBe(false)
    expect(isTrainingOwnerHeartbeat(true, false, 3, 3)).toBe(false)
  })

  it('windows long roster lists', () => {
    const rows = Array.from({ length: 80 }, (_, index) => index)
    expect(windowedRosterRows(rows, 50)).toHaveLength(50)
    expect(windowedRosterRows(rows.slice(0, 10), 50)).toHaveLength(10)
  })

  it('keeps fifteen friends visible before the rail scrolls', () => {
    expect(TRAINING_RAIL_VISIBLE_ROWS).toBe(15)
  })

  it('hides desktop training chrome on every phone route', () => {
    expect(isTrainingRemotePath('/m/training')).toBe(true)
    expect(isTrainingRemotePath('/m/mindgraph')).toBe(false)
    expect(shouldHideTrainingDesktopChrome('/m/training')).toBe(true)
    expect(shouldHideTrainingDesktopChrome('/m')).toBe(true)
    expect(shouldHideTrainingDesktopChrome('/m/mindmate')).toBe(true)
    expect(shouldHideTrainingDesktopChrome('/training/builder/c1')).toBe(true)
    expect(shouldHideTrainingDesktopChrome('/canvas')).toBe(false)
  })

  it('keeps the host on phone pages and anyone on the remote', () => {
    expect(shouldHoldTrainingHostOnMobile('/m/training', 1, 9)).toBe(true)
    expect(shouldHoldTrainingHostOnMobile('/m', 3, 3)).toBe(true)
    expect(shouldHoldTrainingHostOnMobile('/m', 3, 9)).toBe(false)
    expect(shouldHoldTrainingHostOnMobile('/canvas', 3, 3)).toBe(false)
  })
})
