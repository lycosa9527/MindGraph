/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, any>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_TITLE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Build-time injected constants
declare const __APP_VERSION__: string
declare const __BUILD_TIME__: number

declare module 'vue3-carousel-3d' {
  import type { Component } from 'vue'
  export const Carousel3d: Component
  export const Slide: Component
}
