/**
 * Library switch durability for multi-LLM auto-complete.
 *
 * 1. Always drain in-flight PUTs first. After 3/3 the last persist may still
 *    be on the wire with ``isDirty`` already false — skipping flush must not
 *    ``clearActiveDiagram`` under that request (new-canvas CREATE race).
 * 2. Flush again only when dirty or still generating. First-result-wins paints
 *    once and that persist clears canvas-fingerprint dirty; later models do
 *    not change the fingerprint. ``llm:model_completed`` marks dirty again.
 */
export function shouldFlushBeforeLibrarySwitch(state: {
  isDirty: boolean
  isGenerating: boolean
}): boolean {
  return state.isDirty || state.isGenerating
}

export async function flushCanvasBeforeLibrarySwitch(options: {
  isDirty: boolean
  isGenerating: boolean
  drainPersistQueue: () => Promise<void>
  flushOnLeave: () => Promise<{ saved: boolean; reason?: string }>
  collabOwnsPersist: boolean
}): Promise<'ok' | 'failed'> {
  await options.drainPersistQueue()
  if (!shouldFlushBeforeLibrarySwitch(options)) {
    return 'ok'
  }
  const flushResult = await options.flushOnLeave()
  if (
    !flushResult.saved &&
    !(options.collabOwnsPersist && flushResult.reason === 'skipped_guards')
  ) {
    return 'failed'
  }
  return 'ok'
}
