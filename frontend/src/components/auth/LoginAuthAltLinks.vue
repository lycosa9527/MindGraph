<script setup lang="ts">
/**
 * Password-login footer: forgot password, then a two-line SMS / WeChat stack.
 */
import { computed, onMounted } from 'vue'

import { useLanguage } from '@/composables'
import {
  hydratePersistedOAuthLoginError,
  persistedOAuthLoginError,
} from '@/utils/oauthLoginUi'

defineProps<{
  showWechatLogin: boolean
}>()

const emit = defineEmits<{
  (e: 'forgot'): void
  (e: 'sms'): void
  (e: 'wechat'): void
}>()

const { t } = useLanguage()

const showNotLinkedHint = computed(
  () => persistedOAuthLoginError.value === 'oauth_not_linked'
)

onMounted(() => {
  hydratePersistedOAuthLoginError()
})

const linkClass =
  'm-0 p-0 border-0 bg-transparent text-sm leading-5 text-stone-500 hover:text-stone-900 cursor-pointer'
</script>

<template>
  <div class="flex justify-center items-center gap-x-2 pt-2">
    <button
      type="button"
      :class="linkClass"
      @click="emit('forgot')"
    >
      {{ t('auth.forgotPassword') }}
    </button>
    <span
      class="self-stretch w-px bg-stone-300"
      aria-hidden="true"
    />
    <div class="inline-flex flex-col items-start gap-0">
      <button
        type="button"
        :class="linkClass"
        @click="emit('sms')"
      >
        {{ t('auth.smsLogin') }}
      </button>
      <button
        v-if="showWechatLogin"
        type="button"
        :class="linkClass"
        @click="emit('wechat')"
      >
        {{ t('auth.wechatLogin') }}
      </button>
    </div>
  </div>
  <p
    v-if="showWechatLogin && showNotLinkedHint"
    class="mt-3 text-center text-sm text-red-600 leading-6"
  >
    {{ t('auth.qrLoginNotLinked') }}
  </p>
</template>
