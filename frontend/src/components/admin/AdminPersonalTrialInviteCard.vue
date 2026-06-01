<script setup lang="ts">
/**
 * Personal trial (C2C) invite — share registration message for expert / operations.
 */
import { computed } from 'vue'

import { DocumentCopy, Loading } from '@element-plus/icons-vue'

import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'
import { useAdminPersonalTrialInvite } from '@/composables/queries'

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const inviteQuery = useAdminPersonalTrialInvite()

const isLoading = computed(() => inviteQuery.isFetching.value)

const configured = computed(() => Boolean(inviteQuery.data.value?.configured))
const missing = computed(() => Boolean(inviteQuery.data.value?.missing))
const invitationCode = computed(() =>
  String(inviteQuery.data.value?.invitation_code ?? '').trim()
)

async function copyShareMessage(): Promise<void> {
  if (!invitationCode.value) {
    return
  }
  const text = t('admin.personalTrialInviteCopyPayload', {
    siteUrl: publicSiteUrl.value,
    code: invitationCode.value,
  })
  try {
    await navigator.clipboard.writeText(text)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}
</script>

<template>
  <el-card shadow="never" class="admin-schools-card mt-4">
    <h3 class="text-base font-semibold text-stone-800 mb-2">
      {{ t('admin.personalTrialInviteTitle') }}
    </h3>
    <p class="text-sm text-stone-500 mb-4">
      {{ t('admin.personalTrialInviteDescription') }}
    </p>

    <div v-if="isLoading" class="flex justify-center py-8">
      <el-icon class="is-loading" :size="28">
        <Loading />
      </el-icon>
    </div>

    <el-alert
      v-else-if="missing"
      type="info"
      :closable="false"
      show-icon
      :title="t('admin.personalTrialInviteMissingTitle')"
      :description="t('admin.personalTrialInviteMissing')"
    />

    <el-alert
      v-else-if="!configured"
      type="info"
      :closable="false"
      show-icon
      :title="t('admin.personalTrialInviteNotConfiguredTitle')"
      :description="t('admin.personalTrialInviteNotConfigured')"
    />

    <div v-else class="flex flex-wrap items-center gap-3">
      <span class="font-mono text-sm text-stone-800">{{ invitationCode || '—' }}</span>
      <el-button
        v-if="invitationCode"
        type="primary"
        size="small"
        @click="copyShareMessage"
      >
        <el-icon class="mr-1"><DocumentCopy /></el-icon>
        {{ t('admin.copyShareMessage') }}
      </el-button>
    </div>
  </el-card>
</template>
