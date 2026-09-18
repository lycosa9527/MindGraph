<script setup lang="ts">
import { computed } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
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
  }
)

const isPublicSeminar = computed(() => props.visibility === 'network')

const formattedInviteCode = computed(() => {
  const raw = props.inviteCode.trim()
  if (!raw) {
    return ''
  }
  return formatMindmateCollabCode(raw)
})

const breadcrumb = computed(() => {
  const visKey = isPublicSeminar.value
    ? 'mindmate.collabSeminarPublic'
    : 'mindmate.collabSeminarOrg'
  const name = props.sessionTitle.trim()
  const segments: Array<{
    k?: string
    params?: Record<string, unknown>
    label?: string
    isCurrent: boolean
  }> = [
    { k: visKey, isCurrent: false },
    name
      ? {
          label: name,
          isCurrent: !isPublicSeminar.value || !formattedInviteCode.value,
        }
      : {
          k: 'mindmate.collabPill',
          isCurrent: !isPublicSeminar.value || !formattedInviteCode.value,
        },
  ]
  if (isPublicSeminar.value && formattedInviteCode.value) {
    segments.push({
      k: 'mindmate.collabInviteCodeBreadcrumb',
      params: { code: formattedInviteCode.value },
      isCurrent: true,
    })
  }
  return segments
})

const parentClass = computed(() =>
  props.tone === 'toolbar' ? 'text-gray-500 dark:text-gray-400' : 'text-stone-500'
)

const currentClass = computed(() =>
  props.tone === 'toolbar'
    ? 'font-semibold text-gray-900 dark:text-white'
    : 'font-semibold text-stone-900'
)

const sepClass = computed(() =>
  props.tone === 'toolbar' ? 'text-gray-400 dark:text-gray-500' : 'text-stone-400'
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
        <I18nText
          v-if="segment.k"
          :k="segment.k"
          :params="segment.params"
        />
        <template v-else>{{ segment.label }}</template>
      </span>
    </template>
  </nav>
</template>
