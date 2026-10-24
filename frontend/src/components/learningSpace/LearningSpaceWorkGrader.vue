<script setup lang="ts">
/**
 * Who graded one piece of work, on a wall card or in the review panel.
 */
import { computed } from 'vue'

import {
  submissionGraderNames,
  submissionHasUnnamedReview,
} from '@/composables/learningSpace/lsHelpers'
import type { LearningSubmission } from '@/utils/learningSpaceApi'

const props = defineProps<{
  submission:
    | (Pick<LearningSubmission, 'reviewed_at' | 'review_comment' | 'review_scores'> & {
        reviewer_name?: string | null
      })
    | null
    | undefined
  /** Prefix a separator when the line follows other meta. */
  lead?: boolean
}>()

const name = computed(() => submissionGraderNames(props.submission)[0] || '')
const unnamed = computed(() => submissionHasUnnamedReview(props.submission))
const showLead = computed(() => props.lead !== false)
</script>

<template>
  <span v-if="name">
    <template v-if="showLead"> · </template>
    <I18nText
      k="learningSpace.gradedBy"
      :params="{ name }"
    />
  </span>
  <span v-else-if="unnamed">
    <template v-if="showLead"> · </template>
    <I18nText k="learningSpace.reviewed" />
  </span>
</template>
