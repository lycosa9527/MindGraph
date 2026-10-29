<script setup lang="ts">
/**
 * Share a seminar invite link and QR code. Any signed-in account can open the link.
 */
import { computed } from 'vue'

import { ElButton, ElDialog } from 'element-plus'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage, useNotifications } from '@/composables'

const visible = defineModel<boolean>({ required: true })

const props = defineProps<{
  code: string
  creating?: boolean
  errorText?: string
}>()

const { t } = useLanguage()
const notify = useNotifications()

const joinLink = computed(() => {
  const code = props.code.trim()
  if (!code || typeof window === 'undefined') {
    return ''
  }
  const url = new URL('/mindmate', window.location.origin)
  url.searchParams.set('join_mindmate_seminar', code)
  return url.toString()
})

const qrSrc = computed(() => {
  if (!joinLink.value) {
    return ''
  }
  return `/api/qrcode?data=${encodeURIComponent(joinLink.value)}&size=220`
})

async function copyLink(): Promise<void> {
  if (!joinLink.value) {
    return
  }
  try {
    await navigator.clipboard.writeText(joinLink.value)
    notify.successKey('mindmate.home.inviteCopied')
  } catch {
    notify.errorKey('notification.copyFailed')
  }
}
</script>

<template>
  <ElDialog
    v-model="visible"
    width="420px"
    :title="t('mindmate.home.inviteDialogTitle')"
    append-to-body
  >
    <p
      v-if="creating"
      class="mm-invite-dialog__hint"
    >
      <I18nText k="common.loading" />
    </p>
    <p
      v-else-if="errorText"
      class="mm-invite-dialog__error"
    >
      {{ errorText }}
    </p>
    <template v-else>
      <p class="mm-invite-dialog__hint">
        <I18nText k="mindmate.home.inviteDialogHint" />
      </p>
      <p class="mm-invite-dialog__code">{{ code }}</p>
      <img
        v-if="qrSrc"
        class="mm-invite-dialog__qr"
        :src="qrSrc"
        alt=""
      />
      <p class="mm-invite-dialog__link">{{ joinLink }}</p>
    </template>
    <template #footer>
      <ElButton
        type="primary"
        :disabled="creating || !joinLink"
        @click="copyLink"
      >
        <I18nText
          k="mindmate.home.inviteCopy"
          dense
        />
      </ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.mm-invite-dialog__hint,
.mm-invite-dialog__error {
  margin: 0 0 12px;
  font-size: 13px;
  color: #78716c;
}

.mm-invite-dialog__error {
  color: #b45309;
}

.mm-invite-dialog__code {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-align: center;
}

.mm-invite-dialog__qr {
  display: block;
  width: 220px;
  height: 220px;
  margin: 0 auto 12px;
}

.mm-invite-dialog__link {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #57534e;
  word-break: break-all;
}
</style>
