<script setup lang="ts">
/**
 * IMEAutocompleteDropdown - Chinese IME-style suggestion dropdown
 *
 * Features:
 * - Numbered suggestions (1-5) with visual styling
 * - Page indicator and navigation hints
 * - Loading spinner during fetch
 * - Keyboard shortcut hints in footer
 */
import { computed } from 'vue'

import { useLanguage } from '@/composables'

interface Suggestion {
  text: string
  confidence: number
}

const props = withDefaults(
  defineProps<{
    /** Current suggestions to display */
    suggestions: Suggestion[]
    /** Whether suggestions are loading */
    isLoading?: boolean
    /** Current page number (1-indexed for display) */
    currentPage?: number
    /** Whether there's a next page */
    hasNextPage?: boolean
    /** Whether there's a previous page */
    hasPrevPage?: boolean
    /** Error message */
    error?: string | null
  }>(),
  {
    isLoading: false,
    currentPage: 1,
    hasNextPage: true,
    hasPrevPage: false,
    error: null,
  }
)

const emit = defineEmits<{
  (e: 'select', index: number): void
  (e: 'nextPage'): void
  (e: 'prevPage'): void
  (e: 'close'): void
}>()

const { isZh } = useLanguage()

// Labels
const labels = computed(() => ({
  tab: isZh.value ? 'Tab 接受' : 'Tab accept',
  navigate: isZh.value ? '- = 翻页' : '- = navigate',
  esc: 'Esc',
  loading: isZh.value ? '加载中...' : 'Loading...',
  noSuggestions: isZh.value ? '无建议' : 'No suggestions',
  page: isZh.value ? '页' : 'Page',
}))

function handleSelect(index: number) {
  emit('select', index)
}
</script>

<template>
  <div class="ime-dropdown">
    <!-- Loading state -->
    <div
      v-if="isLoading && suggestions.length === 0"
      class="ime-loading"
    >
      <span class="ime-spinner"></span>
      <span>{{ labels.loading }}</span>
    </div>

    <!-- Error state -->
    <div
      v-else-if="error"
      class="ime-error"
    >
      {{ error }}
    </div>

    <!-- Suggestions list -->
    <template v-else-if="suggestions.length > 0">
      <ul class="ime-suggestions">
        <li
          v-for="(suggestion, index) in suggestions"
          :key="index"
          class="ime-suggestion-item"
          @click="handleSelect(index)"
        >
          <span class="ime-number">{{ index + 1 }}.</span>
          <span class="ime-text">{{ suggestion.text }}</span>
        </li>
      </ul>

      <!-- Footer with hints -->
      <div class="ime-footer">
        <span class="ime-hint">{{ labels.tab }}</span>
        <span class="ime-divider">|</span>
        <span class="ime-hint">{{ labels.navigate }}</span>
        <span class="ime-divider">|</span>
        <span class="ime-hint">{{ labels.esc }}</span>
        <span
          v-if="isLoading"
          class="ime-loading-inline"
        >
          <span class="ime-spinner-small"></span>
        </span>
      </div>
    </template>

    <!-- No suggestions -->
    <div
      v-else
      class="ime-empty"
    >
      {{ labels.noSuggestions }}
    </div>
  </div>
</template>

<style scoped>
.ime-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  margin-top: 4px;
  background: var(--mg-bg-primary, #ffffff);
  border: 1px solid var(--mg-border-color, #dcdfe6);
  border-radius: 8px;
  box-shadow: var(--mg-shadow-md, 0 4px 12px rgba(0, 0, 0, 0.1));
  overflow: hidden;
  min-width: 200px;
  max-width: 400px;
}

/* Dark mode */
.dark .ime-dropdown {
  background: var(--mg-bg-primary, #1a1a2e);
  border-color: var(--mg-border-color, #4a4a5e);
}

.ime-suggestions {
  list-style: none;
  margin: 0;
  padding: 4px 0;
}

.ime-suggestion-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.ime-suggestion-item:hover {
  background: var(--mg-bg-secondary, #f5f7fa);
}

.dark .ime-suggestion-item:hover {
  background: var(--mg-bg-secondary, #16213e);
}

.ime-number {
  flex-shrink: 0;
  width: 20px;
  font-weight: 600;
  color: var(--mg-primary, #409eff);
  font-size: 12px;
}

.ime-text {
  flex: 1;
  color: var(--mg-text-primary, #303133);
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dark .ime-text {
  color: var(--mg-text-primary, #e4e7ed);
}

.ime-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--mg-bg-secondary, #f5f7fa);
  border-top: 1px solid var(--mg-border-light, #e4e7ed);
  font-size: 11px;
}

.dark .ime-footer {
  background: var(--mg-bg-secondary, #16213e);
  border-top-color: var(--mg-border-color, #4a4a5e);
}

.ime-hint {
  color: var(--mg-text-secondary, #909399);
}

.ime-divider {
  color: var(--mg-border-color, #dcdfe6);
}

.ime-loading,
.ime-error,
.ime-empty {
  padding: 12px 16px;
  text-align: center;
  color: var(--mg-text-secondary, #909399);
  font-size: 13px;
}

.ime-error {
  color: var(--mg-danger, #f56c6c);
}

.ime-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.ime-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--mg-border-color, #dcdfe6);
  border-top-color: var(--mg-primary, #409eff);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.ime-spinner-small {
  width: 12px;
  height: 12px;
  border: 1.5px solid var(--mg-border-color, #dcdfe6);
  border-top-color: var(--mg-primary, #409eff);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.ime-loading-inline {
  margin-left: 8px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
