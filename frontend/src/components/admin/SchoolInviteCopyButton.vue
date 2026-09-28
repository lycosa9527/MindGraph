<script setup lang="ts">
/**
 * Copies the full school invite message, same payload as the desktop invite button.
 */
import { computed } from 'vue'

import { DocumentCopy } from '@element-plus/icons-vue'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { copySchoolInvitationPayload } from '@/utils/admin/copySchoolInvitationCode'
import { mobileOrgInviteClipboardText } from '@/utils/mobileOrganizations'

const props = defineProps<{
  organizationName: string
  invitationCode: string
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const shareText = computed(() =>
  mobileOrgInviteClipboardText(
    (key, named) => t(key, named),
    { name: props.organizationName, invitationCode: props.invitationCode },
    publicSiteUrl.value,
    String(t('admin.organizationName'))
  )
)

async function copyInvite(): Promise<void> {
  await copySchoolInvitationPayload(
    shareText.value,
    () => notify.success(t('notification.copied')),
    () => notify.error(t('notification.copyFailed'))
  )
}
</script>

<template>
  <div
    v-if="shareText"
    class="school-invite-copy mb-3 flex items-center gap-2"
  >
    <code
      class="min-w-0 flex-1 truncate text-sm font-semibold tracking-wider text-[var(--geek-text,#f8fafc)]"
    >
      {{ invitationCode.trim() }}
    </code>
    <el-button
      type="primary"
      size="small"
      round
      @click="copyInvite"
    >
      <el-icon class="el-icon--left"><DocumentCopy /></el-icon>
      <I18nText k="admin.copyShareMessage" />
    </el-button>
  </div>
</template>
