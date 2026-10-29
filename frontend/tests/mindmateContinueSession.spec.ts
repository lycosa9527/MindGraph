import { createApp, nextTick } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import MindmateHeader from '@/components/panels/mindmate/MindmateHeader.vue'
import {
  LOCAL_MINDMATE_COLLAB_SESSIONS_KEY,
  loadLocalMindmateSeminarSessions,
  trackLocalMindmateSeminarSession,
} from '@/utils/mindmateSeminarSessions'
import { canContinueSavedSeminar } from '@/utils/mindmateSeminarTranscript'

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (key: string) => key,
    currentLanguage: { value: 'en' },
  }),
}))

vi.mock('@/components/common/I18nText.vue', () => ({
  default: {
    props: ['k'],
    template: '<span>{{ k }}</span>',
  },
}))

describe('MindmateHeader continue session', () => {
  let host: HTMLElement

  beforeEach(() => {
    host = document.createElement('div')
    document.body.appendChild(host)
  })

  it('shows Continue session on a closed seminar and emits when clicked', async () => {
    const emitted: string[] = []
    const app = createApp(MindmateHeader, {
      showContinueSession: true,
      mode: 'fullpage',
      onContinueSession: () => {
        emitted.push('continue')
      },
    })
    app.mount(host)
    await nextTick()
    const button = [...host.querySelectorAll('button')].find((node) =>
      node.textContent?.includes('mindmate.collabContinueSession')
    )
    expect(button).toBeTruthy()
    button?.click()
    await nextTick()
    expect(emitted).toEqual(['continue'])
    app.unmount()
    host.remove()
  })

  it('hides Continue session while the seminar is still open', async () => {
    const app = createApp(MindmateHeader, {
      showContinueSession: false,
      mode: 'fullpage',
    })
    app.mount(host)
    await nextTick()
    const button = [...host.querySelectorAll('button')].find((node) =>
      node.textContent?.includes('mindmate.collabContinueSession')
    )
    expect(button).toBeUndefined()
    app.unmount()
    host.remove()
  })
})

describe('canContinueSavedSeminar', () => {
  it('shows Continue session only for the owner of a closed seminar', () => {
    expect(canContinueSavedSeminar('seminar-1', true, false)).toBe(true)
    expect(canContinueSavedSeminar('seminar-1', false, false)).toBe(false)
    expect(canContinueSavedSeminar('seminar-1', true, true)).toBe(false)
    expect(canContinueSavedSeminar(null, true, false)).toBe(false)
  })
})

describe('reopened seminar sidebar row', () => {
  beforeEach(() => {
    localStorage.removeItem(LOCAL_MINDMATE_COLLAB_SESSIONS_KEY)
  })

  it('marks an existing row live without rewriting the title', () => {
    trackLocalMindmateSeminarSession({
      session_id: 'sess-hosted',
      code: '8K2-EUR',
      title: 'Seminar',
    })
    trackLocalMindmateSeminarSession({
      session_id: 'sess-hosted',
      code: '8K2-EUR',
      title: 'Seminar (join)',
      live: true,
      expires_at: '2026-10-19T12:00:00Z',
    })
    const rows = loadLocalMindmateSeminarSessions()
    expect(rows).toHaveLength(1)
    expect(rows[0]?.live).toBe(true)
    expect(rows[0]?.expires_at).toBe('2026-10-19T12:00:00Z')
    expect(rows[0]?.title).toBe('Seminar')
  })
})
