/**
 * Serial paste/persist queue + bounded parallel LLM fetch slots for
 * multi-branch Kitty auto-complete.
 */

const MAX_PARALLEL_FETCHES = 4

let applyChain: Promise<void> = Promise.resolve()
let activeFetches = 0
const fetchWaiters: Array<() => void> = []

async function acquireFetchSlot(): Promise<void> {
  if (activeFetches < MAX_PARALLEL_FETCHES) {
    activeFetches += 1
    return
  }
  await new Promise<void>((resolve) => {
    fetchWaiters.push(() => {
      activeFetches += 1
      resolve()
    })
  })
}

function releaseFetchSlot(): void {
  activeFetches = Math.max(0, activeFetches - 1)
  const next = fetchWaiters.shift()
  if (next) {
    next()
  }
}

export async function withSubgraphFetchSlot<T>(fn: () => Promise<T>): Promise<T> {
  await acquireFetchSlot()
  try {
    return await fn()
  } finally {
    releaseFetchSlot()
  }
}

export function enqueueSubgraphApply<T>(fn: () => Promise<T>): Promise<T> {
  const run = applyChain.then(() => fn())
  applyChain = run.then(
    () => undefined,
    () => undefined
  )
  return run
}

/** Test helper — reset queue state between vitest cases. */
export function resetSubgraphApplyQueueForTests(): void {
  applyChain = Promise.resolve()
  activeFetches = 0
  fetchWaiters.length = 0
}
