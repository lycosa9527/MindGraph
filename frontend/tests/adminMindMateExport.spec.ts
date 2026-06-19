/**
 * Frontend tests for MindMate export admin panel helpers.
 */
import { describe, expect, it } from 'vitest'

import { adminKeys } from '@/composables/queries/adminKeys'

describe('adminKeys.mindmateExport', () => {
  it('includes scope in conversation query key', () => {
    const key = adminKeys.mindmateExport.conversations({
      scope: 'all',
      org_id: null,
      start: 100,
      end: 200,
    })
    expect(key).toContain('mindmate-export')
    expect(key).toContain('conversations')
    expect(JSON.stringify(key)).toContain('all')
  })

  it('builds job query keys', () => {
    expect(adminKeys.mindmateExport.job(42)).toContain(42)
    expect(adminKeys.mindmateExport.jobs(20)).toContain('jobs')
  })
})
