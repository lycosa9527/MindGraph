import { ref } from 'vue'

/** Set on the link menu / relationship handle wrapper (data attribute for mobile hit-testing). */
export const MG_CONCEPT_LINK_HANDLE_ATTR = 'data-mg-concept-link-handle'

export const CONCEPT_LINK_HANDLE_SELECTOR = '[data-mg-concept-link-handle]'

/** True while a concept-map link is being drawn (pointer move/up tracked on window). */
export const conceptMapLinkChaseActive = ref(false)

export function isTargetOnConceptMapLinkHandle(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(CONCEPT_LINK_HANDLE_SELECTOR) !== null
}
