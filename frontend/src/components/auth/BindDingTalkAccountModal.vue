<script setup lang="ts">
/** @deprecated Use DingTalkPairModal with mode="bind" */
import DingTalkPairModal from './DingTalkPairModal.vue'

const props = defineProps<{ modelValue: boolean; linkedStaffId?: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; linked: [] }>()
</script>

<template>
  <DingTalkPairModal
    :model-value="props.modelValue"
    mode="bind"
    :linked-staff-id="props.linkedStaffId"
    @update:model-value="emit('update:modelValue', $event)"
    @completed="emit('linked')"
  />
</template>
