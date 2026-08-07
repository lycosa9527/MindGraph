/**
 * Resolve canvas focus hints for a ZhiHui diagram lesson slide.
 *
 * Slide 0 is always topic overview (empty → fit whole map / select topic).
 * Later slides: prefer focus_child for detail/conflict, else branch / stored ids.
 */
export function resolveZhihuiSlideFocusHints(options: {
  slideIndex: number
  focusNodeIds?: string[] | null
  lessonPlan?: Record<string, unknown> | null
  /** Generation slide_title — last-resort text match to a child node. */
  slideTitle?: string | null
}): string[] {
  if (options.slideIndex <= 0) return []

  const frame = frameAtSlideIndex(options.lessonPlan, options.slideIndex)
  const role = String(frame?.frame_role ?? '')
    .trim()
    .toLowerCase()
  const branch = String(frame?.focus_branch ?? '').trim()
  const child = String(frame?.focus_child ?? '').trim()
  const stored = Array.isArray(options.focusNodeIds)
    ? options.focusNodeIds.map(String).filter((id) => id.trim())
    : []
  const title = String(options.slideTitle ?? '').trim()

  // Branch intro should frame the whole branch (+ children via canvas expand).
  if (role === 'branch_intro') {
    if (branch) return [branch]
    if (stored.length > 0) return stored
    return title ? [title] : []
  }

  // Child / conflict / generic develop frames: pinpoint the child when known.
  if (child) return [child]
  if (title && role !== 'synthesis' && role !== 'close' && role !== 'topic_overview') {
    // Prefer title over a coarse stored branch id so highlight tracks the PPT.
    if (stored.length === 0 || role === 'child_detail' || role === 'cognitive_conflict') {
      return [title]
    }
  }
  if (stored.length > 0) return stored
  if (branch) return [branch]
  if (title) return [title]
  return []
}

function frameAtSlideIndex(
  plan: Record<string, unknown> | null | undefined,
  slideIndex: number
): {
  focus_branch?: unknown
  focus_child?: unknown
  frame_role?: unknown
} | null {
  if (!plan || typeof plan !== 'object') return null
  const flat = flattenLessonPlanFrames(plan)
  const frame = flat[slideIndex]
  if (!frame || typeof frame !== 'object') return null
  return frame as {
    focus_branch?: unknown
    focus_child?: unknown
    frame_role?: unknown
  }
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
