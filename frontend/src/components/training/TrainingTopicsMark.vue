<script setup lang="ts">
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { topicOptionLabel } from '@/composables/training/trainingTopicOptions'
import type { TrainingTopicOption } from '@/types/training'

const props = defineProps<{
  options: TrainingTopicOption[]
  dual?: boolean
  selectedId?: string | null
  selectable?: boolean
}>()

const emit = defineEmits<{
  pick: [option: TrainingTopicOption]
}>()

const { t } = useLanguage()
const rows = computed(() => props.options || [])

function pick(option: TrainingTopicOption): void {
  if (!props.selectable) return
  emit('pick', option)
}
</script>

<template>
  <div
    class="topics-mark"
    :class="{ 'topics-mark--live': selectable }"
  >
    <p class="topics-mark__title">{{ t('training.builder.topicChoices') }}</p>
    <p
      v-if="!rows.length"
      class="topics-mark__empty"
    >
      {{ t('training.builder.topicEmpty') }}
    </p>
    <button
      v-for="option in rows"
      :key="option.id"
      type="button"
      class="topics-mark__option"
      :class="{ 'is-on': selectedId === option.id }"
      :disabled="!selectable"
      @pointerdown.stop
      @click="pick(option)"
    >
      <template v-if="dual">
        <span>
          <em>{{ t('training.builder.topicLabelA') }}</em>
          {{ option.item_a }}
        </span>
        <span>
          <em>{{ t('training.builder.topicLabelB') }}</em>
          {{ option.item_b }}
        </span>
      </template>
      <span v-else>
        <em>{{ t('training.builder.topicLabel') }}</em>
        {{ topicOptionLabel(option, false) }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.topics-mark {
  min-width: 9.5rem;
  max-width: 16rem;
  border: 1px solid #e7e5e4;
  background: rgb(255 255 255 / 0.96);
  padding: 0.4rem 0.4rem 0.45rem;
  box-shadow: 0 10px 24px rgb(28 25 23 / 0.12);
  color: #1c1917;
}
.topics-mark__title {
  margin: 0 0 0.35rem;
  color: #78716c;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}
.topics-mark__empty {
  margin: 0;
  color: #a8a29e;
  font-size: 0.75rem;
}
.topics-mark__option {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 0.12rem;
  margin-top: 0.3rem;
  border: 1px solid #e7e5e4;
  background: #fafaf9;
  padding: 0.35rem 0.45rem;
  color: inherit;
  font: inherit;
  font-size: clamp(0.72rem, 2.3cqh, 0.86rem);
  line-height: 1.35;
  text-align: left;
}
.topics-mark__option:first-of-type {
  margin-top: 0;
}
.topics-mark__option em {
  margin-right: 0.3rem;
  color: #a8a29e;
  font-style: normal;
  font-size: 0.68em;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.topics-mark--live .topics-mark__option {
  cursor: pointer;
}
.topics-mark--live .topics-mark__option:hover {
  border-color: #a8a29e;
  background: #fff;
}
.topics-mark__option.is-on {
  border-color: #1c1917;
  background: #fff;
  box-shadow: inset 3px 0 0 #1c1917;
}
.topics-mark__option:disabled {
  cursor: default;
}
</style>
