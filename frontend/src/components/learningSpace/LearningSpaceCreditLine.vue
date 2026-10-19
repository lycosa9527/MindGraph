<script setup lang="ts">
/**
 * Publisher and grader line on a homework card or detail header.
 */
import { computed } from 'vue'

import { homeworkGraderLabel, homeworkPublisherName } from '@/composables/learningSpace/lsHelpers'

const props = defineProps<{
  publisherName?: string | null
  graderNames?: Array<string | null | undefined> | null
  unnamedReview?: boolean
}>()

const publisher = computed(() => homeworkPublisherName(props.publisherName))
const graders = computed(() => homeworkGraderLabel(props.graderNames))
</script>

<template>
  <I18nText
    k="learningSpace.publishedBy"
    :params="{ name: publisher }"
  />
  ·
  <I18nText
    v-if="graders"
    k="learningSpace.gradedBy"
    :params="{ name: graders }"
  /><I18nText
    v-else-if="unnamedReview"
    k="learningSpace.reviewed"
  /><I18nText
    v-else
    k="learningSpace.notGradedYet"
  />
</template>
