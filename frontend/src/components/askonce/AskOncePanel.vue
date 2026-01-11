<script setup lang="ts">
/**
 * AskOncePanel - Individual LLM response panel
 * Displays streaming response with collapsible thinking section
 * Swiss Design theme - light, clean, minimal
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { ElButton, ElCard, ElIcon } from 'element-plus'

import { Bottom } from '@element-plus/icons-vue'

import { Check, ChevronDown, ChevronUp, Copy, Square } from 'lucide-vue-next'
import MarkdownIt from 'markdown-it'

import { useLanguage } from '@/composables/useLanguage'
import { type ModelId, type ModelResponse, useAskOnceStore } from '@/stores/askonce'

const store = useAskOnceStore()

const { isZh } = useLanguage()

// Initialize markdown-it for rendering
const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

const props = defineProps<{
  modelId: ModelId
  modelName: string
  response: ModelResponse
}>()

// ============================================================================
// State
// ============================================================================

const thinkingCollapsed = ref(false)
const copied = ref(false)
const contentRef = ref<HTMLElement | null>(null)
const userAtBottom = ref(true) // Track if user is at/near bottom for smart auto-scroll

// ============================================================================
// Computed
// ============================================================================

const hasThinking = computed(() => props.response.thinking.length > 0)

const hasContent = computed(() => props.response.content.length > 0)

const renderedContent = computed(() => {
  if (!props.response.content) return ''
  return md.render(props.response.content)
})

const statusColor = computed(() => {
  switch (props.response.status) {
    case 'streaming':
      return 'text-blue-500'
    case 'done':
      return 'text-green-500'
    case 'error':
      return 'text-red-500'
    default:
      return 'text-gray-400'
  }
})

const statusIcon = computed(() => {
  switch (props.response.status) {
    case 'streaming':
      return '●'
    case 'done':
      return '✓'
    case 'error':
      return '✗'
    default:
      return '○'
  }
})

const modelIcon = computed(() => {
  switch (props.modelId) {
    case 'qwen':
      return '🌟'
    case 'deepseek':
      return '🧠'
    case 'kimi':
      return '🌙'
    default:
      return '🤖'
  }
})

// Show scroll-to-bottom button when user is scrolled up and has content
const showScrollButton = computed(() => {
  return !userAtBottom.value && hasContent.value
})

// ============================================================================
// Auto-Scroll
// ============================================================================

// Check if user is near bottom (within 80px threshold)
function isNearBottom(): boolean {
  if (!contentRef.value) return true
  const threshold = 80
  const distanceFromBottom =
    contentRef.value.scrollHeight - contentRef.value.scrollTop - contentRef.value.clientHeight
  return distanceFromBottom <= threshold
}

// Handle scroll events to track user position
function handleScroll() {
  userAtBottom.value = isNearBottom()
}

// Scroll to bottom of content (only if user is at bottom or forced)
async function scrollToBottom(force = false) {
  await nextTick()
  if (!contentRef.value) return

  // Only auto-scroll if user is already at bottom or force is true
  if (!force && !userAtBottom.value) return

  contentRef.value.scrollTop = contentRef.value.scrollHeight
  userAtBottom.value = true
}

// Force scroll to bottom (for button click)
function forceScrollToBottom() {
  scrollToBottom(true)
}

// Set up scroll listener
onMounted(() => {
  nextTick(() => {
    if (contentRef.value) {
      contentRef.value.addEventListener('scroll', handleScroll, { passive: true })
    }
  })
})

// Clean up scroll listener
onUnmounted(() => {
  if (contentRef.value) {
    contentRef.value.removeEventListener('scroll', handleScroll)
  }
})

// Auto-collapse thinking when content starts
watch(
  () => props.response.content,
  (content) => {
    if (content.length > 0 && hasThinking.value) {
      thinkingCollapsed.value = true
    }
  }
)

// Auto-scroll when content updates during streaming
watch(
  () => props.response.content,
  async () => {
    if (props.response.status === 'streaming') {
      await scrollToBottom()
    }
  }
)

// Auto-scroll when thinking updates during streaming
watch(
  () => props.response.thinking,
  async () => {
    if (props.response.status === 'streaming') {
      await scrollToBottom()
    }
  }
)

// Force scroll when streaming starts
watch(
  () => props.response.status,
  async (newStatus, oldStatus) => {
    if (newStatus === 'streaming' && oldStatus !== 'streaming') {
      await scrollToBottom(true) // Force scroll when starting
    }
  }
)

// ============================================================================
// Actions
// ============================================================================

function toggleThinking() {
  if (props.response.status !== 'streaming' || hasContent.value) {
    thinkingCollapsed.value = !thinkingCollapsed.value
  }
}

async function copyResponse() {
  if (!props.response.content) return

  try {
    await navigator.clipboard.writeText(props.response.content)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

function stopStream() {
  store.abortStream(props.modelId)
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}K`
  }
  return tokens.toString()
}
</script>

<template>
  <ElCard
    class="flex flex-col h-full overflow-hidden"
    :body-style="{
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      overflow: 'hidden',
    }"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-gray-50">
      <div class="flex items-center gap-2">
        <span class="text-lg">{{ modelIcon }}</span>
        <h3 class="text-sm font-semibold text-gray-700">{{ modelName }}</h3>
      </div>
      <div class="flex items-center gap-2">
        <span
          class="text-xs transition-colors"
          :class="[statusColor, { 'animate-pulse': response.status === 'streaming' }]"
        >
          {{ statusIcon }}
        </span>
        <span
          class="text-xs text-gray-400 font-mono"
          :title="`${response.tokens} tokens used`"
        >
          {{ formatTokens(response.tokens) }}
        </span>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Thinking Section -->
      <div
        v-if="hasThinking"
        class="border-b border-gray-100 bg-amber-50"
      >
        <div
          class="flex items-center gap-2 px-3 py-2 cursor-pointer select-none text-amber-700 text-sm hover:bg-amber-100 transition-colors"
          @click="toggleThinking"
        >
          <span>💭</span>
          <span class="flex-1">
            {{
              response.status === 'streaming' && !hasContent
                ? isZh
                  ? '思考中...'
                  : 'Thinking...'
                : isZh
                  ? '思考过程'
                  : 'Thought process'
            }}
          </span>
          <component
            :is="thinkingCollapsed ? ChevronDown : ChevronUp"
            class="w-4 h-4"
          />
        </div>
        <div
          v-show="!thinkingCollapsed"
          class="px-3 py-2 text-sm text-amber-800 whitespace-pre-wrap max-h-48 overflow-y-auto border-t border-amber-100"
        >
          {{ response.thinking }}
        </div>
      </div>

      <!-- Response Area -->
      <div
        ref="contentRef"
        class="flex-1 p-4 overflow-y-auto text-sm text-gray-700 leading-relaxed relative"
      >
        <!-- Loading -->
        <div
          v-if="response.status === 'streaming' && !hasContent && !hasThinking"
          class="flex gap-1 py-2"
        >
          <span
            class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
            style="animation-delay: 0s"
          />
          <span
            class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
            style="animation-delay: 0.1s"
          />
          <span
            class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"
            style="animation-delay: 0.2s"
          />
        </div>

        <!-- Error -->
        <div
          v-else-if="response.status === 'error'"
          class="p-3 bg-red-50 text-red-600 rounded-lg"
        >
          {{ response.error || (isZh ? '发生错误' : 'An error occurred') }}
        </div>

        <!-- Placeholder -->
        <div
          v-else-if="!hasContent && response.status === 'idle'"
          class="text-gray-400 italic"
        >
          {{ isZh ? '响应将在此显示...' : 'Response will appear here...' }}
        </div>

        <!-- Content -->
        <div
          v-else
          class="markdown-content prose prose-sm max-w-none"
          v-html="renderedContent"
        />

        <!-- Streaming cursor -->
        <span
          v-if="response.status === 'streaming' && hasContent"
          class="inline-block w-0.5 h-4 bg-blue-500 ml-0.5 animate-pulse"
        />

        <!-- Scroll to Bottom Button -->
        <transition name="fade">
          <ElButton
            v-if="showScrollButton"
            class="scroll-to-bottom-btn"
            circle
            size="small"
            @click="forceScrollToBottom"
          >
            <ElIcon><Bottom /></ElIcon>
          </ElButton>
        </transition>
      </div>
    </div>

    <!-- Footer -->
    <div class="flex justify-between px-3 py-2 border-t border-gray-100 bg-gray-50">
      <!-- Stop button (visible during streaming) -->
      <ElButton
        v-if="response.status === 'streaming'"
        size="small"
        type="danger"
        text
        :title="isZh ? '停止生成' : 'Stop generating'"
        @click="stopStream"
      >
        <Square class="w-4 h-4 mr-1" />
        {{ isZh ? '停止' : 'Stop' }}
      </ElButton>
      <span v-else />

      <!-- Copy button -->
      <ElButton
        size="small"
        text
        :disabled="!hasContent"
        :title="copied ? (isZh ? '已复制' : 'Copied!') : isZh ? '复制响应' : 'Copy response'"
        @click="copyResponse"
      >
        <Check
          v-if="copied"
          class="w-4 h-4 text-green-500"
        />
        <Copy
          v-else
          class="w-4 h-4"
        />
      </ElButton>
    </div>
  </ElCard>
</template>

<style scoped>
/* Markdown content styling */
.markdown-content :deep(p) {
  margin: 0 0 1em;
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(pre) {
  background: #f3f4f6;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 1em 0;
}

.markdown-content :deep(code) {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 1em 0;
  padding-left: 1.5em;
}

.markdown-content :deep(li) {
  margin: 0.5em 0;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  margin-top: 1.5em;
  margin-bottom: 0.5em;
  font-weight: 600;
  color: #1f2937;
}

.markdown-content :deep(blockquote) {
  border-left: 3px solid #d1d5db;
  padding-left: 1em;
  margin: 1em 0;
  color: #6b7280;
}

.markdown-content :deep(a) {
  color: #3b82f6;
  text-decoration: underline;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #e5e7eb;
  padding: 8px 12px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: #f9fafb;
  font-weight: 600;
}

/* Scroll to bottom button */
.scroll-to-bottom-btn {
  position: sticky;
  bottom: 8px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  opacity: 0.9;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  background: white;
  border: 1px solid #e5e7eb;
}

.scroll-to-bottom-btn:hover {
  opacity: 1;
  background: #f3f4f6;
}

/* Fade transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
