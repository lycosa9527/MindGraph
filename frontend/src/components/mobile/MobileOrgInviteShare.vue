<script setup lang="ts">
/**
 * Invite code and link, with one button that copies the full welcome message.
 */
import { computed } from 'vue'

import { Copy, Pencil } from '@lucide/vue'

import { useLanguage, usePublicSiteUrl } from '@/composables'
import { mobileOrgInviteClipboardText } from '@/utils/mobileOrganizations'

const props = defineProps<{
  organizationName: string
  invitationCode: string
  inviteLink: string
}>()

const emit = defineEmits<{
  (e: 'copy', text: string): void
  (e: 'edit'): void
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
    <div v-if="invitationCode">
      <div class="text-xs text-gray-500 mb-1">
        <I18nText k="mobile.orgsInviteCode" />
      </div>
      <div class="text-sm font-semibold text-gray-900 break-all">
        {{ invitationCode }}
      </div>
    </div>
    <div v-if="inviteLink">
      <div class="text-xs text-gray-500 mb-1">
        <I18nText k="mobile.orgsInviteLink" />
      </div>
      <div class="text-sm font-semibold text-gray-900 break-all">
        {{ inviteLink }}
      </div>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="org-pill org-pill--primary"
        :disabled="!shareText"
        @click="copyShare"
      >
        <Copy :size="16" />
        <I18nText k="admin.copyShareMessage" />
      </button>
      <button
        type="button"
        class="org-pill org-pill--quiet"
        @click="emit('edit')"
      >
        <Pencil :size="16" />
        <I18nText k="admin.edit" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.org-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  flex: 0 0 auto;
  width: fit-content;
  max-width: 100%;
  padding: 0 18px;
  border: 0;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
}

.org-pill:disabled {
  opacity: 0.45;
}

.org-pill--primary {
  background: #4f46e5;
  color: #fff;
}

.org-pill--primary:active:not(:disabled) {
  background: #4338ca;
}

.org-pill--quiet {
  background: #fff;
  color: #1f2937;
  border: 1px solid #e5e7eb;
}

.org-pill--quiet:active {
  background: #f9fafb;
}
</style>
