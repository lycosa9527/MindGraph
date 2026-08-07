/**
 * Resolve canvas focus hints for a ZhiHui diagram lesson slide.
 *
 * Slide 0 is always topic overview (empty → fit whole map).
 * Later slides prefer generation.focus_node_ids, then lesson_plan
 * batches[].frames (flat by slide index) focus_branch / focus_child.
 */
export function resolveZhihuiSlideFocusHints(options: {
  slideIndex: number
  focusNodeIds?: string[] | null
  lessonPlan?: Record<string, unknown> | null
}): string[] {
  if (options.slideIndex <= 0) return []
  const ids = options.focusNodeIds
  if (Array.isArray(ids)) {
    const cleaned = ids.map(String).filter((id) => id.trim())
    if (cleaned.length > 0) return cleaned
  }
  const frame = frameAtSlideIndex(options.lessonPlan, options.slideIndex)
  if (!frame) return []
  const branch = String(frame.focus_branch ?? '').trim()
  const child = String(frame.focus_child ?? '').trim()
  // Canvas currently pans to first-level branch (+ descendants).
  if (branch) return [branch]
  if (child) return [child]
  return []
}

function frameAtSlideIndex(
  plan: Record<string, unknown> | null | undefined,
  slideIndex: number
): { focus_branch?: unknown; focus_child?: unknown } | null {
  if (!plan || typeof plan !== 'object') return null
  const flat = flattenLessonPlanFrames(plan)
  const frame = flat[slideIndex]
  if (!frame || typeof frame !== 'object') return null
  return frame as { focus_branch?: unknown; focus_child?: unknown }
}

/** Flatten planner batches[].frames into a deck-ordered list. */
export function flattenLessonPlanFrames(
  plan: Record<string, unknown>
): Record<string, unknown>[] {
  const batches = plan.batches
  if (Array.isArray(batches)) {
    const frames: Record<string, unknown>[] = []
    for (const batch of batches) {
      if (!batch || typeof batch !== 'object') continue
      const batchFrames = (batch as { frames?: unknown }).frames
      if (!Array.isArray(batchFrames)) continue
      for (const frame of batchFrames) {
        if (frame && typeof frame === 'object') {
          frames.push(frame as Record<string, unknown>)
        }
      }
    }
    if (frames.length > 0) return frames
  }
  // Legacy / tests: top-level frames array
  const top = plan.frames
  if (Array.isArray(top)) {
    return top.filter(
      (frame): frame is Record<string, unknown> =>
        Boolean(frame) && typeof frame === 'object'
    )
  }
  return []
}
