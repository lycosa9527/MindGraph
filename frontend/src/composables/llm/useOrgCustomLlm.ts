/**
 * School custom LLM from the session organization payload.
 */
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

export function useOrgCustomLlm() {
  const authStore = useAuthStore()

  const customLlmEnabled = computed(() => authStore.user?.customLlmEnabled === true)

  const customLlmModel = computed(() => {
    const name = authStore.user?.customLlmModel
    return typeof name === 'string' && name.trim() ? name.trim() : null
  })

  const canvasModels = computed(() => {
    if (customLlmEnabled.value) {
      return ['qwen'] as const
    }
    return ['qwen', 'deepseek', 'doubao'] as const
  })

  function displayNameForModel(modelKey: string): string {
    if (customLlmEnabled.value && customLlmModel.value) {
      return customLlmModel.value
    }
    const names: Record<string, string> = {
      qwen: 'Qwen',
      deepseek: 'DeepSeek',
      doubao: 'Doubao',
    }
    return names[modelKey] ?? modelKey
  }

  return {
    customLlmEnabled,
    customLlmModel,
    canvasModels,
    displayNameForModel,
  }
}
