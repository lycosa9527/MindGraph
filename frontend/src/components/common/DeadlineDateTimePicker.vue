<script setup lang="ts">
/**
 * Shared deadline control. Format stays `yyyy/mm/dd hh:mm` in every locale.
 */
import {
  DEADLINE_PICKER_FORMAT,
  DEADLINE_PICKER_PLACEHOLDER,
  DEADLINE_PICKER_TIME_FORMAT,
} from '@/utils/deadlineDateTime'

const model = defineModel<string | Date | null>()
</script>

<template>
  <el-date-picker
    v-model="model"
    type="datetime"
    :format="DEADLINE_PICKER_FORMAT"
    :time-format="DEADLINE_PICKER_TIME_FORMAT"
    :placeholder="DEADLINE_PICKER_PLACEHOLDER"
    style="width: 100%; --el-date-editor-width: 100%"
  />
</template>
