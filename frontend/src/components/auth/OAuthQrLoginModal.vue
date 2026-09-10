<script setup lang="ts">
/**
 * Modal: scan WeChat or DingTalk QR to sign in (pre-linked accounts only).
 */
import { computed, ref, watch } from 'vue'

import { QrCode } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables'
import type { OAuthProvider, OAuthQrMode } from '@/composables/auth/useOAuthQrLogin'

import OAuthQrLoginPanel from './OAuthQrLoginPanel.vue'

const props = defineProps<{
  visible: boolean
  inviteCode: string
  mode?: OAuthQrMode
  initialProvider?: OAuthProvider
  lockProvider?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success'): void
}>()

const { t } = useLanguage()

const activeProvider = ref<OAuthProvider>('wechat')
const mode = computed(() => props.mode ?? 'login')

const isVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

function close(): void {
  isVisible.value = false
}

function onQrSuccess(): void {
  emit('success')
  close()
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      activeProvider.value = props.initialProvider ?? 'wechat'
    }
  }
)
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.oauthQr.ribbon')"
    :title="t('swissGlass.hero.oauthQr.title')"
    :line1="t('swissGlass.hero.oauthQr.line1')"
    :icon="QrCode"
    @close="close"
  >
    <div
      v-if="!lockProvider"
      class="flex gap-2 mb-3"
    >
      <button
        type="button"
        class="flex-1 py-2 text-sm rounded-lg border transition-colors"
        :class="
          activeProvider === 'wechat'
            ? 'border-stone-900 bg-stone-900 text-white'
            : 'border-stone-200 text-stone-600 hover:bg-stone-50'
        "
        @click="activeProvider = 'wechat'"
      >
        {{ t('auth.qrLoginWechatTab') }}
      </button>
      <button
        type="button"
        class="flex-1 py-2 text-sm rounded-lg border transition-colors"
        :class="
          activeProvider === 'dingtalk'
            ? 'border-stone-900 bg-stone-900 text-white'
            : 'border-stone-200 text-stone-600 hover:bg-stone-50'
        "
        @click="activeProvider = 'dingtalk'"
      >
        {{ t('auth.qrLoginDingtalkTab') }}
      </button>
    </div>

    <OAuthQrLoginPanel
      :invite-code="inviteCode"
      :mode="mode"
      :provider="activeProvider"
      @success="onQrSuccess"
    />
  </SwissGlassCard>
</template>
