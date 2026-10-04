import { type ComputedRef, type InjectionKey, type Ref, computed, inject, provide, ref } from 'vue'

const TRAINING_INLINE_HOST: InjectionKey<boolean> = Symbol('trainingInlineHost')

/** Live-canvas element. Course dialogs mount here instead of the page body. */
export const TRAINING_DIALOG_HOST: InjectionKey<Ref<HTMLElement | null>> =
  Symbol('trainingDialogHost')

const dialogHosts = new Map<string, HTMLElement>()
const dialogHostRevision = ref(0)

export function setTrainingDialogHost(scope: string, el: HTMLElement | null): void {
  if (el) dialogHosts.set(scope, el)
  else dialogHosts.delete(scope)
  dialogHostRevision.value += 1
}

/** Portaled mascot for this slide, found beside the marks layer. */
export function trainingDialogHostNear(anchor: HTMLElement | null): HTMLElement | null {
  void dialogHostRevision.value
  const parent = anchor?.parentElement
  if (!parent) return null
  for (const el of dialogHosts.values()) {
    if (parent.contains(el)) return el
  }
  return null
}

export function useTrainingDialogHost(): ComputedRef<HTMLElement | 'body'> {
  const host = inject(TRAINING_DIALOG_HOST, null)
  return computed(() => host?.value ?? 'body')
}

export function provideTrainingInlineHost(): void {
  provide(TRAINING_INLINE_HOST, true)
}

export function isTrainingInlineHost(): boolean {
  return inject(TRAINING_INLINE_HOST, false)
}
