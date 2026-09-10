/**
 * Promise API for the Swiss glass confirm dialog (replaces ElMessageBox.confirm).
 */
import { type Component, reactive } from 'vue'

export interface SwissGlassConfirmHeroOptions {
  ribbon?: string
  title: string
  line1: string
  line2?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  icon?: Component
}

export interface SwissGlassConfirmBoxOptions {
  confirmButtonText?: string
  cancelButtonText?: string
  type?: 'warning' | 'info' | 'error' | 'success'
  distinguishCancelAndClose?: boolean
}

interface SwissGlassConfirmState {
  open: boolean
  ribbon: string
  title: string
  line1: string
  line2: string
  confirmLabel: string
  cancelLabel: string
  danger: boolean
  icon: Component | undefined
}

type ConfirmResolver = (ok: boolean) => void

const state = reactive<SwissGlassConfirmState>({
  open: false,
  ribbon: '',
  title: '',
  line1: '',
  line2: '',
  confirmLabel: '',
  cancelLabel: '',
  danger: false,
  icon: undefined,
})

let resolver: ConfirmResolver | null = null

function finish(ok: boolean): void {
  const resolve = resolver
  resolver = null
  state.open = false
  if (resolve) {
    resolve(ok)
  }
}

export function getSwissGlassConfirmState(): SwissGlassConfirmState {
  return state
}

export function settleSwissGlassConfirm(ok: boolean): void {
  finish(ok)
}

export function swissGlassConfirmHero(options: SwissGlassConfirmHeroOptions): Promise<void> {
  if (resolver) {
    finish(false)
  }
  state.ribbon = options.ribbon ?? ''
  state.title = options.title
  state.line1 = options.line1
  state.line2 = options.line2 ?? ''
  state.confirmLabel = options.confirmLabel ?? ''
  state.cancelLabel = options.cancelLabel ?? ''
  state.danger = options.danger === true
  state.icon = options.icon
  state.open = true
  return new Promise((resolve, reject) => {
    resolver = (ok) => {
      if (ok) {
        resolve()
        return
      }
      reject('cancel')
    }
  })
}

export function swissGlassConfirm(
  message: string,
  titleOrOptions?: string | SwissGlassConfirmBoxOptions,
  options?: SwissGlassConfirmBoxOptions
): Promise<void> {
  const title = typeof titleOrOptions === 'string' ? titleOrOptions : ''
  const opts = typeof titleOrOptions === 'object' ? titleOrOptions : options
  const danger = opts?.type === 'warning' || opts?.type === 'error'
  return swissGlassConfirmHero({
    ribbon: '',
    title: title || message,
    line1: title ? message : '',
    confirmLabel: opts?.confirmButtonText,
    cancelLabel: opts?.cancelButtonText,
    danger,
  })
}
