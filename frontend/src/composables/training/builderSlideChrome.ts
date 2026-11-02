/**
 * Slide chrome the builder and its preview share.
 * Preview must not open a sidebar or toolbar the teacher had closed.
 */
import { ref } from 'vue'

/** The diagram sidebar inside a course slide. Closed until the teacher opens it. */
export const builderSlideSidebarClosed = ref(true)
