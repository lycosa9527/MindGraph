import { computed, ref } from 'vue'

/** Module-level flag — reliable across Vue Flow node tree (inject can miss). */
export const presentationDiagramEditLockedRef = ref(false)

export function setPresentationDiagramEditLocked(locked: boolean): void {
  presentationDiagramEditLockedRef.value = locked
}

/** Case-square .mg reader lock — independent depth counter so other unlock calls cannot open edits. */
let caseSquareReaderLockDepth = 0
export const caseSquareReaderLockRef = ref(false)

export function pushCaseSquareReaderLock(): void {
  caseSquareReaderLockDepth += 1
  caseSquareReaderLockRef.value = true
}

export function popCaseSquareReaderLock(): void {
  caseSquareReaderLockDepth = Math.max(0, caseSquareReaderLockDepth - 1)
  caseSquareReaderLockRef.value = caseSquareReaderLockDepth > 0
}

/** True when any presentation or case-square reader lock is active. */
export const diagramPresentationReadOnlyRef = computed(
  () => presentationDiagramEditLockedRef.value || caseSquareReaderLockRef.value
)

/** Teleport target for presentation overlays/tooltips (must stay inside fullscreen root). */
export const presentationFullscreenRootRef = ref<HTMLElement | null>(null)

export function setPresentationFullscreenRoot(el: HTMLElement | null): void {
  presentationFullscreenRootRef.value = el
}

export function resolvePresentationTeleportTarget(): HTMLElement | string {
  return presentationFullscreenRootRef.value ?? 'body'
}
