<script setup lang="ts">
/**
 * Always-visible mgat_ row inside 账户信息.
 */
import { ref, watch } from 'vue'

import { ElMessage } from 'element-plus'

import { useLanguage } from '@/composables'
import { apiGet } from '@/utils/apiClient'

const props = defineProps<{
  active: boolean
  refreshTick?: number
}>()

const { t } = useLanguage()

type TokenPayload = {
  exists: boolean
  token: string | null
  expires_at: string | null
}

const loading = ref(false)
const payload = ref<TokenPayload | null>(null)

async function loadToken() {
  loading.value = true
  try {
    const res = await apiGet('/api/auth/api-token')
    if (!res.ok) {
      payload.value = null
      return
    }
    payload.value = (await res.json()) as TokenPayload
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.active, props.refreshTick] as const,
  ([active]) => {
    if (active) {
      void loadToken()
    }
  },
  { immediate: true }
)

async function copyToken() {
  const token = payload.value?.token
  if (!token) {
    return
  }
  try {
    await navigator.clipboard.writeText(token)
    ElMessage.success(t('auth.apiTokenCopied'))
  } catch {
    ElMessage.error(t('auth.apiTokenCopyFailed'))
  }
}
</script>

<template>
  <div class="account-api-token-field">
    <div class="text-xs font-medium text-stone-500 mb-1">
      {{ t('auth.apiTokenVisible') }}
    </div>
    <div
      v-if="loading && !payload"
      class="text-xs text-stone-400"
    >
      {{ t('auth.apiTokenLoading') }}
    </div>
    <template v-else-if="payload?.exists && payload.token">
      <div class="flex gap-2 items-stretch">
        <input
          :value="payload.token"
          type="text"
          readonly
          class="flex-1 min-w-0 px-2.5 py-1.5 rounded-lg border border-stone-200 bg-stone-50 font-mono text-xs text-stone-700"
        />
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost"
          @click="copyToken"
        >
          {{ t('auth.apiTokenCopy') }}
        </button>
      </div>
      <p
        v-if="payload.expires_at"
        class="mt-1 mb-0 text-xs text-stone-400"
      >
        {{ t('auth.apiTokenExpires', { date: payload.expires_at }) }}
      </p>
    </template>
    <p
      v-else-if="payload?.exists"
      class="m-0 text-xs text-stone-400"
    >
      {{ t('auth.apiTokenOpaque') }}
    </p>
    <p
      v-else
      class="m-0 text-xs text-stone-400"
    >
      {{ t('auth.apiTokenNone') }}
    </p>
  </div>
</template>
