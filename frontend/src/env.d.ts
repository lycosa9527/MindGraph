/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />

declare const __APP_VERSION__: string
declare const __BUILD_TIME__: number
declare const __DEV_API_ORIGIN__: string

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

interface Window {
  __mgPwaInstallEarly?: BeforeInstallPromptEvent | null
}

declare module 'vue3-carousel-3d' {
  import type { DefineComponent } from 'vue'

  export const Carousel3d: DefineComponent<
    Record<string, unknown>,
    Record<string, unknown>,
    unknown
  >
  export const Slide: DefineComponent<
    Record<string, unknown>,
    Record<string, unknown>,
    unknown
  >
}

/** Loaded at runtime from `/debug/eruda.js` (not bundled). */
interface ErudaApi {
  init: (options?: Record<string, unknown>) => void
  destroy: () => void
  position: (pos?: { x: number; y: number }) => { x: number; y: number } | ErudaApi
}

interface Window {
  eruda?: ErudaApi
}

declare module 'element-plus/es/components/loading/style/css'
declare module 'element-plus/es/components/message-box/style/css'
declare module 'element-plus/es/components/message/style/css'
declare module 'element-plus/es/components/notification/style/css'
declare module 'element-plus/es/components/button/style/css'
declare module 'element-plus/es/components/config-provider/style/css'
