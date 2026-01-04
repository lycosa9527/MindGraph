<script setup lang="ts">
/**
 * SuggestionBubbles - Auto-scrolling suggestion prompts
 * Migrated from prototype SuggestionBubbles.tsx
 */
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps<{
  suggestions: string[]
}>()

const emit = defineEmits<{
  (e: 'click', suggestion: string): void
}>()

const containerRef = ref<HTMLDivElement | null>(null)
const isScrolling = ref(false)
let scrollInterval: number | null = null

// Auto-scroll effect
function startAutoScroll() {
  if (props.suggestions.length <= 3) return

  scrollInterval = window.setInterval(() => {
    if (!isScrolling.value && containerRef.value) {
      const container = containerRef.value
      const firstChild = container.firstElementChild as HTMLElement

      if (firstChild) {
        const bubbleWidth = firstChild.offsetWidth + 12

        container.scrollBy({
          left: bubbleWidth,
          behavior: 'smooth',
        })

        // Move first element to end after scroll animation
        setTimeout(() => {
          if (container.firstElementChild) {
            container.appendChild(container.firstElementChild)
            container.scrollLeft = 0
          }
        }, 500)
      }
    }
  }, 5000)
}

function stopAutoScroll() {
  if (scrollInterval) {
    clearInterval(scrollInterval)
    scrollInterval = null
  }
}

function handleMouseEnter() {
  isScrolling.value = true
}

function handleMouseLeave() {
  isScrolling.value = false
}

function handleClick(suggestion: string) {
  emit('click', suggestion)
}

onMounted(() => {
  startAutoScroll()
})

onUnmounted(() => {
  stopAutoScroll()
})

watch(
  () => props.suggestions.length,
  () => {
    stopAutoScroll()
    startAutoScroll()
  }
)
</script>

<template>
  <div class="suggestion-bubbles">
    <div class="text-sm text-gray-500 mb-2">可以试着问我：</div>
    <div
      ref="containerRef"
      class="bubbles-container flex gap-3 py-2 hide-scrollbar"
      @mouseenter="handleMouseEnter"
      @mouseleave="handleMouseLeave"
    >
      <div
        v-for="(suggestion, index) in suggestions"
        :key="index"
        class="bubble bg-gray-100 rounded-full px-4 py-1.5 text-sm text-gray-700 whitespace-nowrap hover:bg-gray-200 cursor-pointer transition-colors flex-shrink-0"
        @click="handleClick(suggestion)"
      >
        {{ suggestion }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.bubbles-container {
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  max-height: 8rem;
  overflow-x: auto;
  overflow-y: hidden;
  align-items: flex-start;
}

.hide-scrollbar::-webkit-scrollbar {
  display: none;
}

.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
