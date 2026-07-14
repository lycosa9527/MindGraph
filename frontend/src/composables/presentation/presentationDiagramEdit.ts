import { computed, ref } from 'vue'

/** Module-level flag — reliable across Vue Flow node tree (inject can miss). */
export const presentationDiagramEditLockedRef = ref(false)

export function setPresentationDiagramEditLocked(locked: boolean): void {
  presentationDiagramEditLockedRef.value = locked
}

/** Case-square .mg reader lock — independent depth counter so other unlock calls cannot open edits. */
let showcaseReaderLockDepth = 0
export const showcaseReaderLockRef = ref(false)

export function pushShowcaseReaderLock(): void {
  showcaseReaderLockDepth += 1
  showcaseReaderLockRef.value = true
}

export function popShowcaseReaderLock(): void {
  showcaseReaderLockDepth = Math.max(0, showcaseReaderLockDepth - 1)
  showcaseReaderLockRef.value = showcaseReaderLockDepth > 0
}

/** True when any presentation or showcase reader lock is active. */
export const diagramPresentationReadOnlyRef = computed(
  () => presentationDiagramEditLockedRef.value || showcaseReaderLockRef.value
)

/** Teleport target for presentation overlays/tooltips (must stay inside fullscreen root). */
export const presentationFullscreenRootRef = ref<HTMLElement | null>(null)

export function setPresentationFullscreenRoot(el: HTMLElement | null): void {
  presentationFullscreenRootRef.value = el
}

export function resolvePresentationTeleportTarget(): HTMLElement | string {
  return presentationFullscreenRootRef.value ?? 'body'
}
