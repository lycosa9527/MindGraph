<script setup lang="ts">
/**
 * Invite code and link, with one button that copies the full welcome message.
 */
import { computed } from 'vue'

import { Copy } from '@lucide/vue'

import { useLanguage, usePublicSiteUrl } from '@/composables'
import { mobileOrgInviteClipboardText } from '@/utils/mobileOrganizations'

const props = defineProps<{
  organizationName: string
  invitationCode: string
  inviteLink: string
}>()

const emit = defineEmits<{
  (e: 'copy', text: string): void
}>()

const { t } = useLanguage()
const { publicSiteUrl } = usePublicSiteUrl()

const shareText = computed(() =>
  mobileOrgInviteClipboardText(
    (key, named) => t(key, named),
    { name: props.organizationName, invitationCode: props.invitationCode },
    publicSiteUrl.value,
    String(t('admin.organizationName'))
  )
)

function copyShare(): void {
  if (!shareText.value) {
    return
  }
  emit('copy', shareText.value)
}
</script>

<template>
  <div class="space-y-3">
    <div>
      <div class="text-xs text-gray-500 mb-1">
        <I18nText k="mobile.orgsInviteCode" />
      </div>
      <div class="text-sm font-semibold text-gray-900 break-all">
        {{ invitationCode }}
      </div>
    </div>
    <div>
      <div class="text-xs text-gray-500 mb-1">
        <I18nText k="mobile.orgsInviteLink" />
      </div>
      <div class="text-sm font-semibold text-gray-900 break-all">
        {{ inviteLink }}
      </div>
    </div>
    <button
      type="button"
      class="w-full h-10 rounded-xl bg-indigo-600 text-white text-sm font-medium flex items-center justify-center gap-2 active:bg-indigo-700 disabled:opacity-45"
      :disabled="!shareText"
      @click="copyShare"
    >
      <Copy :size="16" />
      <I18nText k="admin.copyShareMessage" />
    </button>
  </div>
</template>
