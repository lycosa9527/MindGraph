<script setup lang="ts">
/**
 * Stone Swiss pagination bar — previous/next pill buttons for admin tables.
 */
import { useLanguage } from '@/composables'

defineProps<{
  pageInfo: string
  page: number
  totalPages: number
}>()

const emit = defineEmits<{
  (e: 'previous'): void
  (e: 'next'): void
}>()

const { t } = useLanguage()
</script>

<template>
  <div class="admin-swiss-pagination">
    <span class="admin-swiss-pagination__info">{{ pageInfo }}</span>
    <div class="admin-swiss-pagination__nav">
      <el-button
        size="small"
        class="admin-swiss-btn admin-swiss-btn--ghost"
        :disabled="page <= 1"
        @click="emit('previous')"
      >
        {{ t('admin.previous') }}
      </el-button>
      <el-button
        size="small"
        class="admin-swiss-btn"
        :disabled="page >= totalPages"
        @click="emit('next')"
      >
        {{ t('admin.next') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
