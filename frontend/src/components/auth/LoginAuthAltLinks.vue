<script setup lang="ts">
/**
 * Password-login footer: forgot password, then a two-line SMS / WeChat stack.
 */
import { useLanguage } from '@/composables'

defineProps<{
  showWechatLogin: boolean
}>()

const emit = defineEmits<{
  (e: 'forgot'): void
  (e: 'sms'): void
  (e: 'wechat'): void
}>()

const { t } = useLanguage()

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
</template>
