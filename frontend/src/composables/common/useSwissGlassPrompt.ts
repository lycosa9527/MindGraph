/**
 * Promise API for a Swiss glass text prompt (replaces ElMessageBox.prompt).
 */
import { type Component, markRaw, reactive } from 'vue'

export interface SwissGlassPromptOptions {
  confirmButtonText?: string
  cancelButtonText?: string
  inputValue?: string
  inputPlaceholder?: string
  inputPattern?: RegExp
  inputErrorMessage?: string
  inputMaxLength?: number
  ribbon?: string
  ribbonKey?: string
  titleKey?: string
  line1Key?: string
  confirmLabelKey?: string
  cancelLabelKey?: string
  icon?: Component
}

interface SwissGlassPromptState {
  open: boolean
  session: number
  ribbon: string
  title: string
  line1: string
  ribbonKey: string
  titleKey: string
  line1Key: string
  confirmLabel: string
  cancelLabel: string
  confirmLabelKey: string
  cancelLabelKey: string
  inputValue: string
  inputPlaceholder: string
  inputMaxLength: number
  icon: Component | undefined
}

interface PromptResult {
  ok: boolean
  value: string
}

type PromptResolver = (result: PromptResult) => void

const state = reactive<SwissGlassPromptState>({
  open: false,
  session: 0,
  ribbon: '',
  title: '',
  line1: '',
  ribbonKey: '',
  titleKey: '',
  line1Key: '',
  confirmLabel: '',
  cancelLabel: '',
  confirmLabelKey: '',
  cancelLabelKey: '',
  inputValue: '',
  inputPlaceholder: '',
  inputMaxLength: 0,
  icon: undefined,
})

let resolver: PromptResolver | null = null
let inputPattern: RegExp | undefined
let inputErrorMessage = ''

function finish(value: string | null): void {
  const resolve = resolver
  resolver = null
  inputPattern = undefined
  inputErrorMessage = ''
  state.open = false
  if (!resolve) return
  if (value === null) {
    resolve({ ok: false, value: '' })
    return
  }
  resolve({ ok: true, value })
}

export function getSwissGlassPromptState(): SwissGlassPromptState {
  return state
}

/** Returns an error message when the value is rejected, otherwise closes and resolves. */
export function trySettleSwissGlassPrompt(raw: string): string {
  const value = raw.trim()
  if (inputPattern && !inputPattern.test(value)) {
    return inputErrorMessage
  }
  if (state.inputMaxLength > 0 && value.length > state.inputMaxLength) {
    return inputErrorMessage
  }
  finish(value)
  return ''
}

export function cancelSwissGlassPrompt(): void {
  finish(null)
}

export function swissGlassPrompt(
  message: string,
  title: string,
  options?: SwissGlassPromptOptions
): Promise<string> {
  if (resolver) {
    finish(null)
  }
  state.ribbon = options?.ribbon ?? ''
  state.title = title
  state.line1 = message
  state.ribbonKey = options?.ribbonKey ?? ''
  state.titleKey = options?.titleKey ?? ''
  state.line1Key = options?.line1Key ?? ''
  state.confirmLabel = options?.confirmButtonText ?? ''
  state.cancelLabel = options?.cancelButtonText ?? ''
  state.confirmLabelKey = options?.confirmLabelKey ?? ''
  state.cancelLabelKey = options?.cancelLabelKey ?? ''
  state.inputValue = options?.inputValue ?? ''
  state.inputPlaceholder = options?.inputPlaceholder ?? ''
  state.inputMaxLength = options?.inputMaxLength ?? 0
  state.icon = options?.icon ? markRaw(options.icon) : undefined
  inputPattern = options?.inputPattern
  inputErrorMessage = options?.inputErrorMessage ?? ''
  state.session += 1
  state.open = true
  return new Promise((resolve, reject) => {
    resolver = (result) => {
      if (result.ok) {
        resolve(result.value)
        return
      }
      reject('cancel')
    }
  })
}
