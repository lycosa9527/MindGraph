/**
 * Lets auth/session teardown close the Workshop Chat WebSocket and reset state
 * without importing the Pinia store from the auth store (avoids circular deps).
 */
let disconnectHandler: (() => void) | null = null

export function registerWorkshopChatWsDisconnect(fn: () => void): void {
  disconnectHandler = fn
}

export function unregisterWorkshopChatWsDisconnect(fn: () => void): void {
  if (disconnectHandler === fn) {
    disconnectHandler = null
  }
}

export function disconnectWorkshopChatWsIfAny(): void {
  disconnectHandler?.()
}

type WorkshopChatResetOnAuthClear = (userId?: string) => void

let resetOnAuthClearHandler: WorkshopChatResetOnAuthClear | null = null

export function registerWorkshopChatResetOnAuthClear(fn: WorkshopChatResetOnAuthClear): void {
  resetOnAuthClearHandler = fn
}

export function unregisterWorkshopChatResetOnAuthClear(fn: WorkshopChatResetOnAuthClear): void {
  if (resetOnAuthClearHandler === fn) {
    resetOnAuthClearHandler = null
  }
}

export function resetWorkshopChatOnAuthClear(userId?: string): void {
  resetOnAuthClearHandler?.(userId)
}
