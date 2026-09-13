/**
 * First 演讲模式 fit must wait for measure-batch + two frames
 * (same settle as useDiagramCanvasFit mind-map load).
 */

export const MIND_MAP_SLIDE_PLAY_READY_TIMEOUT_MS = 4000

function waitTwoAnimationFrames(): Promise<void> {
  if (typeof requestAnimationFrame !== 'function') {
    return new Promise((resolve) => {
      window.setTimeout(resolve, 0)
    })
  }
  return new Promise((resolve) => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => resolve())
    })
  })
}

export async function waitForMindMapSlidePlayReady(
  isBulkLoading: () => boolean,
  timeoutMs = MIND_MAP_SLIDE_PLAY_READY_TIMEOUT_MS
): Promise<void> {
  const started = performance.now()
  while (isBulkLoading() && performance.now() - started < timeoutMs) {
    await waitTwoAnimationFrames()
  }
  await waitTwoAnimationFrames()
}
