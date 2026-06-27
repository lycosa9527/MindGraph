<script setup lang="ts">
/**
 * Modal: scan WeChat or DingTalk QR to sign in (pre-linked accounts only).
 */
import { computed, ref, watch } from 'vue'

import { Close } from '@element-plus/icons-vue'

import OAuthQrLoginPanel from './OAuthQrLoginPanel.vue'
import { useLanguage } from '@/composables'
import type { OAuthProvider, OAuthQrMode } from '@/composables/auth/useOAuthQrLogin'

const props = defineProps<{
  visible: boolean
  inviteCode: string
  mode?: OAuthQrMode
  initialProvider?: OAuthProvider
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
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="oauth-qr-modal-overlay fixed inset-0 z-[1100] flex items-center justify-center bg-stone-900/70 p-4"
      @click.self="close"
    >
      <div
        class="oauth-qr-modal-card bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden"
        role="dialog"
        aria-modal="true"
        :aria-label="t('auth.qrLoginTitle')"
      >
        <div class="flex items-center justify-between px-5 py-4 border-b border-stone-100">
          <h2 class="text-base font-semibold text-stone-900">
            {{ mode === 'bind' ? t('auth.oauthBindTitle') : t('auth.qrLoginTitle') }}
          </h2>
          <button
            type="button"
            class="p-1 rounded hover:bg-stone-100 text-stone-500"
            :aria-label="t('common.close')"
            @click="close"
          >
            <Close class="w-5 h-5" />
          </button>
        </div>

        <div class="px-5 pt-3">
          <div class="flex gap-2 mb-3">
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
        </div>

        <div class="px-5 pb-5">
          <OAuthQrLoginPanel
            :invite-code="inviteCode"
            :mode="mode"
            :provider="activeProvider"
            @success="onQrSuccess"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>
