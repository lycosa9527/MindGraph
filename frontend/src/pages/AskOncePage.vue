<script setup lang="ts">
/**
 * AskOncePage - Multi-LLM streaming chat interface
 * Route: /askonce
 *
 * Chinese name: 多应
 * English name: AskOnce
 */
import { computed, onUnmounted, ref } from 'vue'

import { ElButton, ElDialog, ElIcon, ElInput, ElOption, ElSelect } from 'element-plus'

import { Plus } from '@element-plus/icons-vue'

import { BookOpen, Send, Settings } from 'lucide-vue-next'

import { AskOncePanel } from '@/components/askonce'
import { LoginModal } from '@/components/auth'
import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { ASKONCE_PROMPT_TEMPLATES } from '@/config/askOncePrompts'
import { type ModelId, useAskOnceStore } from '@/stores/askonce'
import { useRouter } from 'vue-router'

// ============================================================================
// i18n
// ============================================================================

const { t, isZh } = useLanguage()
const router = useRouter()

// ============================================================================
// Store
// ============================================================================

const store = useAskOnceStore()
const authStore = useAuthStore()
const showLoginModal = ref(false)

// ============================================================================
// State
// ============================================================================

const promptInput = ref('')
const showSystemModal = ref(false)
const systemPromptDraft = ref('')
const selectedTemplate = ref('')

const MODEL_IDS: ModelId[] = ['qwen', 'deepseek', 'kimi']

const MODEL_CONFIG: Record<ModelId, { modelName: string }> = {
  qwen: { modelName: 'qwen3-235b' },
  deepseek: { modelName: 'deepseek-v3.2' },
  kimi: { modelName: 'kimi-k2' },
}

// ============================================================================
// Computed
// ============================================================================

const charCount = computed(() => promptInput.value.length)

const canSend = computed(() => promptInput.value.trim().length > 0 && !store.isStreaming && authStore.isAuthenticated)

const placeholderText = computed(() =>
  isZh.value
    ? '输入您的问题... 按 Ctrl+Enter 或点击发送'
    : 'Enter your prompt... Press Ctrl+Enter or click Send'
)

// Current conversation title for display
const conversationTitle = computed(() => {
  const conv = store.currentConversation
  if (!conv) return isZh.value ? '新对话' : 'New Conversation'
  return conv.name || (isZh.value ? '未命名对话' : 'Untitled Conversation')
})

// ============================================================================
// Streaming
// ============================================================================

async function streamFromModel(
  modelId: ModelId,
  messages: { role: string; content: string }[]
): Promise<string> {
  if (!authStore.isAuthenticated) {
    store.updateModelResponse(modelId, { status: 'error', error: 'Authentication required' })
    return ''
  }

  const controller = new AbortController()
  store.setAbortController(modelId, controller)
  store.updateModelResponse(modelId, { status: 'streaming', content: '', thinking: '' })

  try {
    const response = await fetch(`/api/askonce/stream/${modelId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()

      if (done) {
        if (buffer.trim()) {
          processSSELines(modelId, buffer.split('\n'))
        }
        store.updateModelResponse(modelId, { status: 'done' })
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      processSSELines(modelId, lines)
    }

    // Return the final content for saving to conversation history
    return store.responses[modelId].content
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      console.log(`[AskOnce] ${modelId} stream aborted`)
      store.updateModelResponse(modelId, { status: 'idle' })
    } else {
      console.error(`[AskOnce] ${modelId} error:`, error)
      store.updateModelResponse(modelId, {
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
      })
    }
    return '' // Return empty on error/abort
  } finally {
    store.setAbortController(modelId, null)
  }
}

function processSSELines(modelId: ModelId, lines: string[]) {
  for (const line of lines) {
    if (!line.startsWith('data: ')) continue

    const jsonStr = line.slice(6).trim()
    if (!jsonStr) continue

    try {
      const data = JSON.parse(jsonStr)

      if (data.type === 'thinking' && data.content) {
        store.appendThinking(modelId, data.content)
      } else if (data.type === 'token' && data.content) {
        store.appendContent(modelId, data.content)
      } else if (data.type === 'usage' && data.usage) {
        const totalTokens =
          data.usage.total_tokens ||
          (data.usage.prompt_tokens || 0) + (data.usage.completion_tokens || 0)
        store.setTokens(modelId, totalTokens)
      } else if (data.type === 'done') {
        store.updateModelResponse(modelId, { status: 'done' })
      } else if (data.type === 'error') {
        store.updateModelResponse(modelId, { status: 'error', error: data.error })
      }
    } catch (e) {
      console.warn('[AskOnce] Failed to parse SSE:', jsonStr, e)
    }
  }
}

// ============================================================================
// Actions
// ============================================================================

async function sendToAllModels() {
  if (!authStore.isAuthenticated) {
    openLoginModal()
    return
  }

  const prompt = promptInput.value.trim()
  if (!prompt) return

  store.isStreaming = true
  promptInput.value = ''

  // Add user message first (shared across all models)
  store.addUserMessage(prompt)
  store.resetAllResponses()

  // Build per-model messages and stream
  const streamPromises = MODEL_IDS.map(async (modelId) => {
    // Build messages for this specific model (includes its own response history)
    const messages: { role: string; content: string }[] = []

    if (store.systemPrompt) {
      messages.push({ role: 'system', content: store.systemPrompt })
    }

    // Get this model's conversation history (user messages + this model's responses)
    for (const msg of store.getMessagesForModel(modelId)) {
      messages.push({ role: msg.role, content: msg.content })
    }

    // Stream and get the response content
    const responseContent = await streamFromModel(modelId, messages)

    // Save this model's response to its conversation history (including thinking)
    if (responseContent) {
      const thinking = store.responses[modelId].thinking || ''
      store.addAssistantMessage(modelId, responseContent, thinking)
    }
  })

  try {
    await Promise.all(streamPromises)
  } finally {
    store.isStreaming = false
  }
}

function clearAll() {
  if (!authStore.isAuthenticated) {
    openLoginModal()
    return
  }
  store.abortAllStreams()
  store.startNewConversation()
  promptInput.value = ''
}

function openSystemModal() {
  if (!authStore.isAuthenticated) {
    openLoginModal()
    return
  }
  systemPromptDraft.value = store.systemPrompt
  selectedTemplate.value = ''
  showSystemModal.value = true
}

function saveSystemPrompt() {
  store.setSystemPrompt(systemPromptDraft.value.trim())
  showSystemModal.value = false
}

function loadTemplate(templateId: string) {
  if (templateId && ASKONCE_PROMPT_TEMPLATES[templateId]) {
    systemPromptDraft.value = ASKONCE_PROMPT_TEMPLATES[templateId].content
  }
}

function handleKeydown(e: Event | KeyboardEvent) {
  if (!('key' in e)) return
  
  // Check authentication before allowing input
  if (!authStore.isAuthenticated) {
    e.preventDefault()
    openLoginModal()
    return
  }
  
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    if (canSend.value) {
      sendToAllModels()
    }
  }
}

// Handle input focus - show login modal if not authenticated
function handleInputFocus() {
  if (!authStore.isAuthenticated) {
    openLoginModal()
  }
}

// Handle input change - prevent updates when not authenticated
function handleInputChange(value: string) {
  if (!authStore.isAuthenticated) {
    return
  }
  promptInput.value = value
}

function clearPromptDraft() {
  systemPromptDraft.value = ''
  selectedTemplate.value = ''
}

function openLoginModal() {
  showLoginModal.value = true
}

function handleLoginSuccess() {
  showLoginModal.value = false
}

onUnmounted(() => {
  store.abortAllStreams()
})
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50 relative">
    <!-- Header -->
    <header class="h-14 px-4 flex items-center justify-between bg-white border-b border-gray-200">
      <div class="flex items-center gap-3">
        <h1 class="text-sm font-semibold text-gray-800">{{ t('askonce.title') }}</h1>
        <span class="text-gray-300">|</span>
        <span
          class="text-sm text-gray-500 truncate max-w-xs"
          :title="conversationTitle"
        >
          {{ conversationTitle }}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <ElButton
          class="new-chat-btn"
          size="small"
          :disabled="!authStore.isAuthenticated"
          @click="clearAll"
        >
          <ElIcon class="mr-1"><Plus /></ElIcon>
          {{ isZh ? '新建对话' : 'New Chat' }}
        </ElButton>
      </div>
    </header>

    <!-- Input Area -->
    <section class="px-6 py-4 bg-white border-b border-gray-200">
      <div class="max-w-5xl mx-auto">
        <ElInput
          :model-value="promptInput"
          type="textarea"
          :rows="3"
          :placeholder="placeholderText"
          :disabled="!authStore.isAuthenticated"
          resize="vertical"
          @update:model-value="handleInputChange"
          @keydown="handleKeydown"
          @focus="handleInputFocus"
        />
        <div class="flex items-center justify-between mt-3">
          <div class="flex items-center gap-4 text-sm text-gray-500">
            <span>{{ charCount }} {{ isZh ? '字符' : 'chars' }}</span>
            <span
              v-if="store.hasSystemPrompt"
              class="text-green-600"
            >
              ✓ {{ isZh ? '提示词模板已应用' : 'Template active' }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <ElButton
              :icon="Settings"
              :disabled="!authStore.isAuthenticated"
              @click="openSystemModal"
            >
              {{ isZh ? '提示词模板' : 'Templates' }}
            </ElButton>
            <ElButton
              type="primary"
              :icon="Send"
              :disabled="!canSend || !authStore.isAuthenticated"
              @click="sendToAllModels"
            >
              {{ isZh ? '发送' : 'Send' }}
            </ElButton>
          </div>
        </div>
      </div>
    </section>

    <!-- Response Panels -->
    <main class="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 pb-10 overflow-hidden min-h-0">
      <AskOncePanel
        v-for="modelId in MODEL_IDS"
        :key="modelId"
        :model-id="modelId"
        :model-name="MODEL_CONFIG[modelId].modelName"
        :response="store.responses[modelId]"
      />
    </main>

    <!-- Prompt Template Modal -->
    <ElDialog
      v-model="showSystemModal"
      :title="isZh ? '提示词模板' : 'Prompt Templates'"
      width="600px"
    >
      <div class="mb-4">
        <label class="block text-sm text-gray-600 mb-2">
          {{ isZh ? '选择模板' : 'Select Template' }}
        </label>
        <ElSelect
          v-model="selectedTemplate"
          :placeholder="isZh ? '选择预设模板...' : 'Select a preset template...'"
          class="w-full"
          @change="loadTemplate"
        >
          <ElOption
            v-for="(template, key) in ASKONCE_PROMPT_TEMPLATES"
            :key="key"
            :label="isZh ? template.name.zh : template.name.en"
            :value="key"
          />
        </ElSelect>
      </div>
      <div>
        <label class="block text-sm text-gray-600 mb-2">
          {{ isZh ? '提示词内容' : 'Prompt Content' }}
        </label>
        <ElInput
          v-model="systemPromptDraft"
          type="textarea"
          :rows="10"
          :placeholder="isZh ? '输入或选择模板后编辑...' : 'Enter or select a template to edit...'"
        />
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <ElButton @click="clearPromptDraft">
            {{ isZh ? '清空' : 'Clear' }}
          </ElButton>
          <ElButton
            type="primary"
            @click="saveSystemPrompt"
          >
            {{ isZh ? '应用' : 'Apply' }}
          </ElButton>
        </div>
      </template>
    </ElDialog>

    <!-- Login Modal -->
    <LoginModal
      v-model:visible="showLoginModal"
      @success="handleLoginSuccess"
    />
  </div>
</template>

<style scoped>
/* New Chat button - Swiss Design style (grey, round) - matches MindMate */
.new-chat-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}

</style>
