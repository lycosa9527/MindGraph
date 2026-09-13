const STORAGE_KEY = 'mg_slide_remote_start'

export function setSlideRemotePendingStart(diagramId: string): void {
  const id = diagramId.trim()
  if (!id) {
    return
  }
  sessionStorage.setItem(STORAGE_KEY, id)
}

export function peekSlideRemotePendingStart(): string | null {
  const id = sessionStorage.getItem(STORAGE_KEY)?.trim() ?? ''
  return id || null
}

export function consumeSlideRemotePendingStart(diagramId: string): boolean {
  const pending = peekSlideRemotePendingStart()
  const target = diagramId.trim()
  if (!pending || !target || pending !== target) {
    return false
  }
  sessionStorage.removeItem(STORAGE_KEY)
  return true
}

export function shouldJumpForSlideRemoteStart(
  currentId: string | null | undefined,
  targetId: string
): boolean {
  const target = targetId.trim()
  const current = currentId?.trim() ?? ''
  return target.length > 0 && current !== target
}
