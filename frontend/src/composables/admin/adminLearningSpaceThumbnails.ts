/**
 * Admin Learning Space: keep asking for the next thumbnail batch until none remain.
 */
import type { ThumbnailBackfillBatch } from '@/utils/learningSpaceApi'

export interface ThumbnailBackfillTotals {
  stored: number
  generated: number
  failed: number
}

export async function runLearningSpaceThumbnailBackfill(
  postBatch: (skip: string[]) => Promise<ThumbnailBackfillBatch>,
  onProgress?: (state: { done: number; remaining: number }) => void
): Promise<ThumbnailBackfillTotals> {
  const skip = new Set<string>()
  const failed = new Set<string>()
  let stored = 0
  let generated = 0
  for (let step = 0; step < 2000; step += 1) {
    const batch = await postBatch([...skip])
    stored += Number(batch.stored) || 0
    generated += Number(batch.generated) || 0
    for (const key of batch.failed_keys || []) {
      skip.add(key)
      failed.add(key)
    }
    for (const key of batch.ready_keys || []) {
      skip.add(key)
    }
    const remaining = Number(batch.remaining) || 0
    onProgress?.({ done: stored + generated, remaining })
    if (remaining <= 0) break
    const progressed =
      (Number(batch.stored) || 0) +
      (Number(batch.generated) || 0) +
      (batch.failed_keys?.length || 0) +
      (batch.ready_keys?.length || 0)
    if (progressed <= 0) break
  }
  return { stored, generated, failed: failed.size }
}
