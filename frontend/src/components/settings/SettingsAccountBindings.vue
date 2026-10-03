<script setup lang="ts">
/**
 * WeChat account linking row inside Settings → Security.
 */
import { Loader2 } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'

defineProps<{
  form: {
    showWechatOAuthRow: boolean
    wechatBindingStatus: string
    wechatOAuthLinked: boolean
    oauthLinksLoading: boolean
    canBindWechat: boolean
    unbindWechat: () => void
    openWechatBindModal: () => void
  }
}>()
</script>

<template>
  <div class="space-y-4">
    <div class="language-settings-swiss__kicker">
      <I18nText k="auth.accountBindingsSection" />
    </div>

    <div v-if="form.showWechatOAuthRow">
      <label
        class="language-settings-swiss__kicker"
        for="account-binding-wechat"
      >
        <I18nText k="auth.bindingWechat" />
      </label>
      <div class="flex items-center gap-2">
        <input
          id="account-binding-wechat"
          :value="form.wechatBindingStatus"
          type="text"
          name="account-binding-wechat"
          disabled
          class="swiss-glass-field__input min-w-0 flex-1"
        />
        <button
          v-if="form.wechatOAuthLinked"
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary shrink-0"
          :disabled="form.oauthLinksLoading"
          @click="form.unbindWechat()"
        >
          <Loader2
            v-if="form.oauthLinksLoading"
            class="w-3.5 h-3.5 animate-spin"
          />
          <I18nText k="auth.unbindWechat" />
        </button>
        <button
          v-else-if="form.canBindWechat"
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary shrink-0"
          :disabled="form.oauthLinksLoading"
          @click="form.openWechatBindModal()"
        >
          <Loader2
            v-if="form.oauthLinksLoading"
            class="w-3.5 h-3.5 animate-spin"
          />
          <I18nText k="auth.bindWechat" />
        </button>
      </div>
    </div>
  </div>
</template>
