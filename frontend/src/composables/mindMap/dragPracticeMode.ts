/**
 * Drag-practice flags that other modules can read without loading the session.
 * While picking blanks or playing, the diagram itself must not change.
 */
import { ref } from 'vue'

export const dragPracticeActive = ref(false)
/** Teacher is clicking nodes to choose blanks before play. */
export const dragPracticePicking = ref(false)

export function isDragPracticeDiagramLocked(): boolean {
  return dragPracticeActive.value || dragPracticePicking.value
}
