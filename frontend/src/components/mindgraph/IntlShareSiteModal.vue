<script setup lang="ts">
/**
 * Back-compat alias: share-site / international QR modal
 * (implementation lives in QuickRegisterModal).
 */
import QuickRegisterModal from './QuickRegisterModal.vue'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>
<template>
  <QuickRegisterModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>
