/**
 * Injection key for desktop canvas Kitty owner (apply/ack WS).
 */
import type { InjectionKey } from 'vue'

import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'

export type KittyCanvasOwnerApi = {
  kitty: ReturnType<typeof useKittyAgent>
  ensureConnected: () => Promise<boolean>
}

export const KITTY_CANVAS_OWNER_KEY: InjectionKey<KittyCanvasOwnerApi> = Symbol('kittyCanvasOwner')
