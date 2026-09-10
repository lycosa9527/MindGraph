<script setup lang="ts">
/**
 * Share invitation message dialog — Swiss minimal.
 */
import { computed } from 'vue'

import { Copy, Share2 } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage, useNotifications, usePublicSiteUrl } from '@/composables'

const props = defineProps<{
  modelValue: boolean
  invitationCode: string
  organizationName?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const { publicSiteUrl } = usePublicSiteUrl()

const isVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const resolvedOrgName = computed(
  () => props.organizationName?.trim() || (t('admin.organizationName') as string)
)

const shareMessageText = computed(() =>
  t('admin.shareInviteMessage', {
    orgName: resolvedOrgName.value,
    code: props.invitationCode,
    siteUrl: publicSiteUrl.value,
  })
)

const shortInviteText = computed(() =>
  t('admin.schoolInviteCopyPayload', {
    orgName: resolvedOrgName.value,
    code: props.invitationCode,
    siteUrl: publicSiteUrl.value,
  })
)

function closeModal() {
  isVisible.value = false
}

async function copyShareMessage() {
  try {
    await navigator.clipboard.writeText(shareMessageText.value)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}

async function copyShortInvite() {
  try {
    await navigator.clipboard.writeText(shortInviteText.value)
    notify.success(t('notification.copied'))
  } catch {
    notify.error(t('notification.copyFailed'))
  }
}
</script>

<template>
  <SwissGlassCard
    v-model="isVisible"
    :ribbon="t('swissGlass.hero.adminSchoolShare.ribbon')"
    :title="t('swissGlass.hero.adminSchoolShare.title')"
    :line1="t('swissGlass.hero.adminSchoolShare.line1')"
    :icon="Share2"
    card-class="swiss-glass-card--wide"
  >
    <p
      class="whitespace-pre-wrap rounded-lg bg-stone-50 p-4 text-sm text-stone-700 leading-relaxed max-h-[min(50vh,320px)] overflow-y-auto"
    >
      {{ shareMessageText }}
    </p>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="closeModal"
        >
          {{ t('common.close') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="copyShortInvite"
        >
          <Copy class="w-4 h-4" />
          {{ t('admin.copyShortInvite') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="copyShareMessage"
        >
          <Copy class="w-4 h-4" />
          {{ t('admin.copyShareMessage') }}
        </button>
      </div>
    </template>
  </SwissGlassCard>
</template>
