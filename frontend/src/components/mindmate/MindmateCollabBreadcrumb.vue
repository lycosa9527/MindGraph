<script setup lang="ts">
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { formatMindmateCollabCode } from '@/utils/mindmateCollabSessions'

const props = withDefaults(
  defineProps<{
    visibility?: string
    sessionTitle?: string
    inviteCode?: string
    /** Toolbar on /mindmate full page (dark mode classes). */
    tone?: 'light' | 'toolbar'
  }>(),
  {
    visibility: 'organization',
    sessionTitle: '',
    inviteCode: '',
    tone: 'light',
  },
)

const { t } = useLanguage()

const isPublicSeminar = computed(() => props.visibility === 'network')

const formattedInviteCode = computed(() => {
  const raw = props.inviteCode.trim()
  if (!raw) {
    return ''
  }
  return formatMindmateCollabCode(raw)
})

const breadcrumb = computed(() => {
  const visLabel =
    isPublicSeminar.value
      ? t('mindmate.collabSeminarPublic')
      : t('mindmate.collabSeminarOrg')
  const name = props.sessionTitle.trim() || t('mindmate.collabPill')
  const segments: Array<{ label: string; isCurrent: boolean }> = [
    { label: visLabel, isCurrent: false },
    { label: name, isCurrent: !isPublicSeminar.value || !formattedInviteCode.value },
  ]
  if (isPublicSeminar.value && formattedInviteCode.value) {
    segments.push({
      label: t('mindmate.collabInviteCodeBreadcrumb', { code: formattedInviteCode.value }),
      isCurrent: true,
    })
  }
  return segments
})

const parentClass = computed(() =>
  props.tone === 'toolbar'
    ? 'text-gray-500 dark:text-gray-400'
    : 'text-stone-500',
)

const currentClass = computed(() =>
  props.tone === 'toolbar'
    ? 'font-semibold text-gray-900 dark:text-white'
    : 'font-semibold text-stone-900',
)

const sepClass = computed(() =>
  props.tone === 'toolbar' ? 'text-gray-400 dark:text-gray-500' : 'text-stone-400',
)
</script>

<template>
  <nav
    aria-label="breadcrumb"
    class="mindmate-collab-breadcrumb flex min-w-0 items-center gap-1 text-sm truncate"
  >
    <template
      v-for="(segment, index) in breadcrumb"
      :key="index"
    >
      <span
        v-if="index > 0"
        class="shrink-0"
        :class="sepClass"
        aria-hidden="true"
      >
        /
      </span>
      <span
        class="truncate"
        :class="segment.isCurrent ? currentClass : parentClass"
      >
        {{ segment.label }}
      </span>
    </template>
  </nav>
</template>
