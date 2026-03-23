<script setup lang="ts">
/**
 * Suggestion Bubbles Component
 * Displays clickable prompt suggestions for MindMate welcome screen
 * Shows 3 rows of wrapped bubbles with horizontal scroll animation
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

const props = withDefaults(
  defineProps<{
    suggestions?: string[]
  }>(),
  {
    suggestions: () => [],
  }
)

const emit = defineEmits<{
  (e: 'select', suggestion: string): void
}>()

const { t } = useLanguage()
const authStore = useAuthStore()

// Default suggestions if none provided
const defaultSuggestions = computed(() => [
  t('mindmate.defaultSuggestion1'),
  t('mindmate.defaultSuggestion2'),
  t('mindmate.defaultSuggestion3'),
  t('mindmate.defaultSuggestion4'),
  t('mindmate.defaultSuggestion5'),
  t('mindmate.defaultSuggestion6'),
  t('mindmate.defaultSuggestion7'),
  t('mindmate.defaultSuggestion8'),
  t('mindmate.defaultSuggestion9'),
  t('mindmate.defaultSuggestion10'),
  t('mindmate.defaultSuggestion11'),
  t('mindmate.defaultSuggestion12'),
])

const displaySuggestions = computed(() => {
  return props.suggestions.length > 0 ? props.suggestions : defaultSuggestions.value
})

// Animation state
const containerRef = ref<HTMLElement | null>(null)
const isHovering = ref(false)
let scrollInterval: ReturnType<typeof setInterval> | null = null

const handleClick = (suggestion: string) => {
  // Check authentication before allowing click
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }
  emit('select', suggestion)
}

// Auto-scroll effect - scrolls horizontally through wrapped content
const startAutoScroll = () => {
  scrollInterval = setInterval(() => {
    if (!isHovering.value && containerRef.value) {
      const container = containerRef.value

      // Calculate scroll amount (width of approximately one bubble)
      const scrollAmount = 200

      // Scroll right
      container.scrollBy({
        left: scrollAmount,
        behavior: 'smooth',
      })

      // Reset to beginning when near end
      setTimeout(() => {
        if (container.scrollLeft + container.clientWidth >= container.scrollWidth - 100) {
          container.scrollTo({ left: 0, behavior: 'smooth' })
        }
      }, 500)
    }
  }, 4000) // Scroll every 4 seconds
}

onMounted(() => {
  startAutoScroll()
})

onUnmounted(() => {
  if (scrollInterval) {
    clearInterval(scrollInterval)
  }
})

const labelText = computed(() => t('mindmate.suggestionLabel'))

const isAuthenticated = computed(() => authStore.isAuthenticated)
</script>

<template>
  <div class="suggestion-bubbles">
    <div class="suggestion-label">{{ labelText }}</div>
    <div
      ref="containerRef"
      class="suggestion-container"
      @mouseenter="isHovering = true"
      @mouseleave="isHovering = false"
    >
      <button
        v-for="(suggestion, index) in displaySuggestions"
        :key="index"
        class="suggestion-bubble"
        :disabled="!isAuthenticated"
        @click="handleClick(suggestion)"
      >
        {{ suggestion }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.suggestion-bubbles {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
}

.suggestion-label {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 12px;
  text-align: center;
}

.suggestion-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  align-content: flex-start;
  max-height: 140px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 8px 4px;
  scroll-behavior: smooth;
  /* Hide scrollbar but keep functionality */
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.suggestion-container::-webkit-scrollbar {
  display: none;
}

/* Pause animation on hover */
.suggestion-container:hover {
  scroll-behavior: auto;
}

.suggestion-bubble {
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  padding: 8px 16px;
  font-size: 13px;
  color: #374151;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.suggestion-bubble:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.suggestion-bubble:hover {
  background: #e5e7eb;
  border-color: #d1d5db;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.suggestion-bubble:active {
  transform: translateY(0);
}

/* Dark mode support */
:global(.dark) .suggestion-label {
  color: #9ca3af;
}

:global(.dark) .suggestion-bubble {
  background: #374151;
  border-color: #4b5563;
  color: #e5e7eb;
}

:global(.dark) .suggestion-bubble:hover {
  background: #4b5563;
  border-color: #6b7280;
}
</style>
