<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElAvatar, ElButton, ElIcon, ElLoading, ElScrollbar } from 'element-plus'
import { useResizeObserver } from '@vueuse/core'

import { Bottom } from '@element-plus/icons-vue'

import mindmateAvatarMd from '@/assets/mindmate-avatar-md.png'
import { useLanguage } from '@/composables'
import type { MindMateMessage } from '@/composables/useMindMate'
import { useUIStore } from '@/stores'

import MessageBubble from './MessageBubble.vue'
import MindmateWelcome from './MindmateWelcome.vue'

// v-loading directive
const vLoading = ElLoading.directive

const { isZh } = useLanguage()
const uiStore = useUIStore()

// Loading background color (dark mode aware)
const loadingBackground = computed(() =>
  uiStore.isDark ? 'rgba(31, 41, 55, 0.9)' : 'rgba(255, 255, 255, 0.9)'
)

const props = defineProps<{
  mode?: 'panel' | 'fullpage'
  messages: MindMateMessage[]
  userAvatar: string
  showWelcome?: boolean
  isLoading?: boolean
  isStreaming?: boolean
  isLoadingHistory?: boolean
  editingMessageId?: string | null
  editingContent?: string
  hoveredMessageId?: string | null
  isLastAssistantMessage?: (messageId: string) => boolean
  hasPreviousUserMessage?: (messageId: string) => boolean
}>()

const emit = defineEmits<{
  (e: 'edit', message: MindMateMessage): void
  (e: 'cancelEdit'): void
  (e: 'saveEdit', content: string): void
  (e: 'copy', content: string): void
  (e: 'regenerate', messageId: string): void
  (e: 'feedback', messageId: string, rating: 'like' | 'dislike' | null): void
  (e: 'share'): void
  (e: 'messageHover', messageId: string | null): void
  (e: 'scrollToBottom', force?: boolean): void
}>()

const scrollbarRef = ref<InstanceType<typeof ElScrollbar> | null>(null)
const messagesWrapperRef = ref<HTMLElement | null>(null)
const userAtBottom = ref(true) // Track if user is at/near bottom for smart auto-scroll

// Use VueUse's useResizeObserver for automatic cleanup
// Auto-scroll when content height changes (e.g., images load) if user is at bottom
useResizeObserver(messagesWrapperRef, () => {
  if (userAtBottom.value) {
    scrollToBottom()
  }
})

// Show scroll-to-bottom button when user is scrolled up and has messages
const showScrollButton = computed(() => {
  return !userAtBottom.value && props.messages.length > 0
})

// Check if user is near bottom (within 100px threshold)
function isNearBottom(): boolean {
  if (!scrollbarRef.value) return true
  const scrollContainer = scrollbarRef.value.$el.querySelector('.el-scrollbar__wrap')
  if (!scrollContainer) return true
  const threshold = 100
  const distanceFromBottom =
    scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight
  return distanceFromBottom <= threshold
}

// Handle scroll events to track user position
function handleScroll() {
  userAtBottom.value = isNearBottom()
}

// Scroll to bottom of messages (only if user is at bottom or forced)
async function scrollToBottom(force = false) {
  await nextTick()
  if (!scrollbarRef.value) return

  // Only auto-scroll if user is already at bottom or force is true
  if (!force && !userAtBottom.value) return

  const scrollContainer = scrollbarRef.value.$el.querySelector('.el-scrollbar__wrap')
  if (scrollContainer) {
    scrollContainer.scrollTop = scrollContainer.scrollHeight
    userAtBottom.value = true
  }
}

// Force scroll to bottom (for button click)
function forceScrollToBottom() {
  scrollToBottom(true)
  emit('scrollToBottom', true)
}

// Set up scroll listener for smart auto-scroll
// Note: ResizeObserver is handled by VueUse's useResizeObserver above (auto-cleanup)
onMounted(() => {
  nextTick(() => {
    if (scrollbarRef.value) {
      const scrollContainer = scrollbarRef.value.$el.querySelector('.el-scrollbar__wrap')
      if (scrollContainer) {
        scrollContainer.addEventListener('scroll', handleScroll, { passive: true })
      }
    }
  })
})

// Clean up scroll listener (VueUse's useResizeObserver auto-cleans up)
onUnmounted(() => {
  if (scrollbarRef.value) {
    const scrollContainer = scrollbarRef.value.$el.querySelector('.el-scrollbar__wrap')
    if (scrollContainer) {
      scrollContainer.removeEventListener('scroll', handleScroll)
    }
  }
})

// Watch for new messages - force scroll when a new message is added
watch(
  () => props.messages.length,
  async (newLen, oldLen) => {
    // Force scroll when user sends a message (new message added)
    const isNewUserMessage = newLen > oldLen && props.messages[newLen - 1]?.role === 'user'
    await scrollToBottom(isNewUserMessage)
  }
)

// Scroll when streaming updates content (respects user scroll position)
watch(
  () => props.messages[props.messages.length - 1]?.content,
  async () => {
    if (props.isStreaming) {
      await scrollToBottom()
    }
  }
)
</script>

<template>
  <div
    v-loading="isLoadingHistory ?? false"
    :element-loading-text="isZh ? '加载中...' : 'Loading...'"
    :element-loading-background="loadingBackground"
    class="messages-container"
  >
    <!-- Messages with Element Plus Scrollbar -->
    <ElScrollbar
      ref="scrollbarRef"
      class="messages-scrollbar"
    >
      <div
        ref="messagesWrapperRef"
        class="messages-wrapper p-4 space-y-6"
      >
        <!-- Welcome Message -->
        <MindmateWelcome
          v-if="showWelcome"
          :mode="mode"
        />

        <!-- Messages -->
        <MessageBubble
          v-for="message in messages"
          :key="message.id"
          :message="message"
          :user-avatar="userAvatar"
          :is-editing="editingMessageId === message.id"
          :editing-content="editingContent"
          :is-hovered="hoveredMessageId === message.id"
          :is-last-assistant="isLastAssistantMessage?.(message.id) ?? false"
          :has-previous-user-message="hasPreviousUserMessage?.(message.id) ?? false"
          :is-loading="isLoading"
          @edit="emit('edit', $event)"
          @cancel-edit="emit('cancelEdit')"
          @save-edit="emit('saveEdit', $event)"
          @copy="emit('copy', $event)"
          @regenerate="emit('regenerate', $event)"
          @feedback="
            (messageId: string, rating: 'like' | 'dislike' | null) =>
              emit('feedback', messageId, rating)
          "
          @share="emit('share')"
          @mouseenter="emit('messageHover', message.id)"
          @mouseleave="emit('messageHover', null)"
        />

        <!-- Loading indicator (before first response) -->
        <div
          v-if="isLoading && !isStreaming"
          class="message flex gap-3"
        >
          <!-- MindMate avatar -->
          <ElAvatar
            :src="mindmateAvatarMd"
            alt="MindMate"
            :size="40"
            class="mindmate-avatar flex-shrink-0"
          />
          <div class="message-content bg-gray-100 dark:bg-gray-700 rounded-lg px-3 py-2">
            <div class="flex gap-1.5 items-center justify-center">
              <span
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 0ms"
              />
              <span
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 150ms"
              />
              <span
                class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                style="animation-delay: 300ms"
              />
            </div>
          </div>
        </div>
      </div>
    </ElScrollbar>

    <!-- Scroll to Bottom Button -->
    <transition name="fade">
      <ElButton
        v-if="showScrollButton"
        class="scroll-to-bottom-btn"
        circle
        @click="forceScrollToBottom"
      >
        <ElIcon><Bottom /></ElIcon>
      </ElButton>
    </transition>
  </div>
</template>

<style scoped>
@import './mindmate.css';

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
