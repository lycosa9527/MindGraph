<script setup lang="ts">
/**
 * Stone Swiss pagination bar — previous/next pill buttons for admin tables.
 */
import { computed } from 'vue'

const props = defineProps<{
  pageInfo: string
  page: number
  totalPages: number
}>()

const emit = defineEmits<{
  (e: 'previous'): void
  (e: 'next'): void
}>()

const effectiveTotalPages = computed(() => Math.max(props.totalPages, 1))
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
        <I18nText k="admin.previous" />
      </el-button>
      <el-button
        size="small"
        class="admin-swiss-btn"
        :disabled="page >= effectiveTotalPages"
        @click="emit('next')"
      >
        <I18nText k="admin.next" />
      </el-button>
    </div>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
