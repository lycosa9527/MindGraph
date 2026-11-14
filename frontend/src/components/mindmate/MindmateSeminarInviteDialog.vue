<script setup lang="ts">
/**
 * Share a seminar invite code and copyable invite message.
 */
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

async function copyCode(): Promise<void> {
  const code = props.code.trim()
  if (!code) {
    return
  }
  try {
    await navigator.clipboard.writeText(code)
    notify.successKey('mindmate.home.inviteCodeCopied')
  } catch {
    notify.errorKey('notification.copyFailed')
  }
}

async function copyInviteMessage(): Promise<void> {
  const code = props.code.trim()
  if (!code) {
    return
  }
  try {
    await navigator.clipboard.writeText(
      t('mindmate.home.brief.inviteShareText', { code })
    )
    notify.successKey('mindmate.home.brief.inviteShareCopied')
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
    class="mm-seminar-swiss"
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
    </template>
    <template #footer>
      <ElButton
        :disabled="creating || !code.trim()"
        @click="copyCode"
      >
        <I18nText
          k="mindmate.home.inviteCopyCode"
          dense
        />
      </ElButton>
      <ElButton
        type="primary"
        :disabled="creating || !code.trim()"
        @click="copyInviteMessage"
      >
        <I18nText
          k="mindmate.home.brief.inviteCopyMessage"
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
  color: #1c1917;
}
</style>
