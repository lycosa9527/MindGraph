<script setup lang="ts">
/**
 * Embedded WeChat / DingTalk QR widgets for OAuth login or bind.
 */
import { computed } from 'vue'

import { Loader2 } from '@lucide/vue'

import { useLanguage } from '@/composables'
import {
  useOAuthQrLogin,
  type OAuthProvider,
  type OAuthQrMode,
} from '@/composables/auth/useOAuthQrLogin'

const props = defineProps<{
  inviteCode: string
  mode: OAuthQrMode
  provider: OAuthProvider
}>()

const emit = defineEmits<{
  (e: 'success'): void
}>()

const { t } = useLanguage()

const {
  providers,
  loadingProviders,
  providerError,
  wechatContainerId,
  dingtalkContainerId,
} = useOAuthQrLogin({
  inviteCode: () => props.inviteCode,
  mode: () => props.mode,
  activeProvider: () => props.provider,
  onSuccess: () => emit('success'),
})

const showWechat = computed(
  () => props.provider === 'wechat' && (providers.value?.wechat_enabled ?? false)
)
const showDingtalk = computed(
  () => props.provider === 'dingtalk' && (providers.value?.dingtalk_enabled ?? false)
)
</script>

<template>
  <div class="oauth-qr-panel">
    <div
      v-if="mode === 'login' && !inviteCode.trim()"
      class="text-sm text-stone-500 text-center py-4"
    >
      {{ t('auth.qrLoginInviteRequired') }}
    </div>
    <div
      v-else-if="loadingProviders"
      class="flex justify-center py-8 text-stone-500"
    >
      <Loader2 class="w-6 h-6 animate-spin" />
    </div>
    <div
      v-else-if="providerError"
      class="text-sm text-red-600 text-center py-4"
    >
      {{
        providerError === 'invite_required'
          ? t('auth.qrLoginInviteRequired')
          : t('auth.qrLoginProvidersFailed')
      }}
    </div>
    <div
      v-else-if="showWechat"
      class="flex flex-col items-center"
    >
      <div
        :id="wechatContainerId"
        class="oauth-qr-panel__wechat"
      />
    </div>
    <div
      v-else-if="showDingtalk"
      class="flex flex-col items-center"
    >
      <div
        :id="dingtalkContainerId"
        class="oauth-qr-panel__dingtalk"
      />
    </div>
    <div
      v-else
      class="text-sm text-stone-500 text-center py-4"
    >
      {{ t('auth.qrLoginProviderDisabled') }}
    </div>
    <p class="text-xs text-stone-400 text-center mt-3 px-2">
      {{ t('auth.accountBindingsHint') }}
    </p>
  </div>
</template>

<style scoped>
.oauth-qr-panel__wechat,
.oauth-qr-panel__dingtalk {
  min-width: 220px;
  min-height: 220px;
}
</style>
