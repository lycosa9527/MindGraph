<script setup lang="ts">
/**
 * Settings QR the glasses photograph to attach that photo to this account.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { Camera, Loader2 } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const POLL_MS = 2000

type BindBody = {
  linked?: boolean
  token?: string
  qr_payload?: string
}

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  completed: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const token = ref('')
const qrPayload = ref('')
const loading = ref(false)
const completed = ref(false)
let pollTimer = 0

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const qrSrc = computed(() => {
  if (!qrPayload.value) {
    return ''
  }
  return `/api/qrcode?data=${encodeURIComponent(qrPayload.value)}&size=220`
})

function stopPoll() {
  if (pollTimer === 0) {
    return
  }
  window.clearInterval(pollTimer)
  pollTimer = 0
}

async function poll() {
  if (!token.value || completed.value) {
    return
  }
  const response = await apiRequest(
    `/api/learning-space/glasses/bind?token=${encodeURIComponent(token.value)}`,
    { method: 'GET' }
  )
  if (!response.ok) {
    return
  }
  const body = (await response.json()) as BindBody
  if (body.linked === true) {
    completed.value = true
    stopPoll()
    emit('completed')
  }
}

async function mint() {
  stopPoll()
  loading.value = true
  completed.value = false
  token.value = ''
  qrPayload.value = ''
  try {
    const response = await apiRequest('/api/learning-space/glasses/bind', { method: 'POST' })
    if (!response.ok) {
      notify.errorKey('auth.glassesBindMintError')
      return
    }
    const body = (await response.json()) as BindBody
    if (body.linked === true) {
      completed.value = true
      emit('completed')
      return
    }
    token.value = body.token || ''
    qrPayload.value = body.qr_payload || ''
    pollTimer = window.setInterval(() => {
      void poll()
    }, POLL_MS)
  } catch {
    notify.errorKey('auth.glassesBindMintError')
  } finally {
    loading.value = false
  }
}

function close() {
  visible.value = false
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      void mint()
      return
    }
    stopPoll()
  }
)

onBeforeUnmount(() => {
  stopPoll()
})
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('auth.glassesBindSection')"
    ribbon-key="auth.glassesBindSection"
    :title="t('auth.glassesBindTitle')"
    title-key="auth.glassesBindTitle"
    :line1="t('auth.glassesBindInstructions')"
    line1-key="auth.glassesBindInstructions"
    :icon="Camera"
    width="min(420px, 92vw)"
    @close="close"
  >
    <div class="flex flex-col items-center gap-3 min-h-[240px] justify-center text-sm text-stone-700">
      <Loader2
        v-if="loading"
        class="w-8 h-8 animate-spin text-stone-400"
      />
      <img
        v-else-if="qrSrc && !completed"
        :src="qrSrc"
        :alt="t('auth.glassesBindSection')"
        width="220"
        height="220"
        class="bg-white p-2"
      />
      <p
        v-if="completed"
        class="text-emerald-600 font-medium"
      >
        <I18nText k="auth.glassesBindSuccess" />
      </p>
      <p
        v-else-if="qrSrc"
        class="text-stone-500 text-xs text-center"
      >
        <I18nText k="auth.glassesBindWaiting" />
      </p>
    </div>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="close"
        >
          <I18nText k="common.close" />
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
