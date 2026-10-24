<script setup lang="ts">
/**
 * Learning-space deadline. The form stores `YYYY-MM-DDTHH:mm` on the Beijing clock.
 * The picker emits `YYYY-MM-DD HH:mm`, so this field translates between the two.
 */
import { computed } from 'vue'

import DeadlineDateTimePicker from '@/components/common/DeadlineDateTimePicker.vue'
import {
  DEADLINE_VALUE_FORMAT,
  deadlineModelToPicker,
  deadlinePickerToModel,
} from '@/utils/deadlineDateTime'

const model = defineModel<string>({ required: true })

const pickerValue = computed({
  get(): string | null {
    return deadlineModelToPicker(model.value)
  },
  set(value: string | Date | null): void {
    const next = deadlinePickerToModel(typeof value === 'string' ? value : null)
    if (model.value !== next) model.value = next
  },
})
</script>

<template>
  <DeadlineDateTimePicker
    v-model="pickerValue"
    class="ls-deadline"
    :value-format="DEADLINE_VALUE_FORMAT"
    :teleported="true"
    clearable
  />
</template>
