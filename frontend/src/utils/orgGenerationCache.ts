/**
 * Attach skip_cache / record cached generate_graph results for the canvas notice.
 */
import { useOrgGenerationCacheNoticeStore } from '@/stores/orgGenerationCacheNotice'

export function withOrgGenerationCacheBypass(
  body: Record<string, unknown>
): Record<string, unknown> {
  const notice = useOrgGenerationCacheNoticeStore()
  if (!notice.visible) {
    return body
  }
  return { ...body, skip_cache: true }
}

export function noteOrgGenerationCacheResult(payload: { cached?: unknown } | null | undefined): void {
  useOrgGenerationCacheNoticeStore().applyCachedFlag(payload?.cached)
}
