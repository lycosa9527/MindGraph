<script setup lang="ts">
/**
 * Copyable invite code + link block for mobile org management.
 */
import { Copy } from '@lucide/vue'

import { useLanguage } from '@/composables'

defineProps<{
  invitationCode: string
  inviteLink: string
}>()

const emit = defineEmits<{
  (e: 'copy', text: string): void
}>()

const { t } = useLanguage()
</script>

<template>
  <div class="space-y-3">
    <div>
      <div class="text-xs text-gray-500 mb-1">
        {{ t('mobile.orgsInviteCode') }}
      </div>
      <div class="flex items-center gap-2">
        <code class="flex-1 min-w-0 text-sm font-semibold tracking-wider text-gray-900">
          {{ invitationCode }}
        </code>
        <button
          type="button"
          class="shrink-0 w-9 h-9 rounded-lg bg-gray-100 text-gray-600 flex items-center justify-center"
          :aria-label="t('mobile.orgsCopyCode')"
          @click="emit('copy', invitationCode)"
        >
          <Copy :size="16" />
        </button>
      </div>
    </div>
    <div>
      <div class="text-xs text-gray-500 mb-1">
        {{ t('mobile.orgsInviteLink') }}
      </div>
      <div class="flex items-center gap-2">
        <div class="flex-1 min-w-0 text-xs text-gray-700 break-all">
          {{ inviteLink }}
        </div>
        <button
          type="button"
          class="shrink-0 w-9 h-9 rounded-lg bg-gray-100 text-gray-600 flex items-center justify-center"
          :aria-label="t('mobile.orgsCopyLink')"
          @click="emit('copy', inviteLink)"
        >
          <Copy :size="16" />
        </button>
      </div>
    </div>
  </div>
</template>
