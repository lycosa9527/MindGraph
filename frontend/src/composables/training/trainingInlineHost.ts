import { inject, provide, type InjectionKey } from 'vue'

const TRAINING_INLINE_HOST: InjectionKey<boolean> = Symbol('trainingInlineHost')

export function provideTrainingInlineHost(): void {
  provide(TRAINING_INLINE_HOST, true)
}

export function isTrainingInlineHost(): boolean {
  return inject(TRAINING_INLINE_HOST, false)
}
