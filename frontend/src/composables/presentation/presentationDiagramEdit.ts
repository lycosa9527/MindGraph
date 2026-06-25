import { ref } from 'vue'

/** Module-level flag — reliable across Vue Flow node tree (inject can miss). */
export const presentationDiagramEditLockedRef = ref(false)

export function setPresentationDiagramEditLocked(locked: boolean): void {
  presentationDiagramEditLockedRef.value = locked
}

/** Teleport target for presentation overlays/tooltips (must stay inside fullscreen root). */
export const presentationFullscreenRootRef = ref<HTMLElement | null>(null)

export function setPresentationFullscreenRoot(el: HTMLElement | null): void {
  presentationFullscreenRootRef.value = el
}

export function resolvePresentationTeleportTarget(): HTMLElement | string {
  return presentationFullscreenRootRef.value ?? 'body'
}
