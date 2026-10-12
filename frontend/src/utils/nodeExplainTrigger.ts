/** Marks toolbar controls that start node explanation. */
export const NODE_EXPLAIN_TRIGGER_SELECTOR = '[data-node-explain-trigger]'

export function isNodeExplainTriggerTarget(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(NODE_EXPLAIN_TRIGGER_SELECTOR) !== null
}

/** Keep the open editor focused so this click cannot confirm the draft. */
export function retainEditOnExplainPointer(event: Event, locked: boolean): void {
  if (!locked) return
  event.preventDefault()
  event.stopPropagation()
}
