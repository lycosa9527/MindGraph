import { describe, expect, it } from 'vitest'

import { runLearningSpaceThumbnailBackfill } from '@/composables/admin/adminLearningSpaceThumbnails'
import type { ThumbnailBackfillBatch } from '@/utils/learningSpaceApi'

describe('runLearningSpaceThumbnailBackfill', () => {
  it('keeps scanning and does not retry a failed card in the same click', async () => {
    const seen: string[][] = []
    const totals = await runLearningSpaceThumbnailBackfill(async (skip) => {
      seen.push(skip)
      if (seen.length === 1) {
        const batch: ThumbnailBackfillBatch = {
          stored: 1,
          generated: 0,
          remaining: 1,
          failed_keys: ['template:4'],
          ready_keys: ['template:5'],
        }
        return batch
      }
      return {
        stored: 0,
        generated: 1,
        remaining: 0,
        failed_keys: [],
        ready_keys: [],
      }
    })
    expect(seen[1]).toEqual(['template:4', 'template:5'])
    expect(totals).toEqual({ stored: 1, generated: 1, failed: 1 })
  })
})
