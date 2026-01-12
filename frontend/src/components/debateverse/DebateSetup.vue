<script setup lang="ts">
/**
 * DebateSetup - Stage 1: Setup and role selection
 * Redesigned with centered layout similar to Mindmate fullpage mode
 */
import { computed, ref } from 'vue'

import { ElAvatar, ElButton, ElDropdown, ElDropdownItem, ElDropdownMenu, ElIcon, ElInput } from 'element-plus'

import { ArrowDown } from '@element-plus/icons-vue'
import { Send } from 'lucide-vue-next'

import debateverseAvatarLg from '@/assets/debateverse-avatar-lg.png'
import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { useDebateVerseStore, type LLMAssignment } from '@/stores/debateverse'

import SuggestionBubbles from '../common/SuggestionBubbles.vue'

const { isZh } = useLanguage()
const authStore = useAuthStore()
const store = useDebateVerseStore()

// ============================================================================
// State
// ============================================================================

const topic = ref('')
const userRole = ref<'debater' | 'judge' | 'viewer'>('viewer')

const isCreating = ref(false)

// Shuffle LLM models randomly
function shuffleLLMAssignments(): LLMAssignment {
  const models = ['qwen', 'doubao', 'deepseek', 'kimi']
  const shuffled = [...models].sort(() => Math.random() - 0.5)
  
  return {
    affirmative_1: shuffled[0],
    affirmative_2: shuffled[1],
    negative_1: shuffled[2],
    negative_2: shuffled[3],
    judge: models[Math.floor(Math.random() * models.length)],
  }
}

// Default LLM assignments (randomized)
const llmAssignments = ref<LLMAssignment>(shuffleLLMAssignments())

// ============================================================================
// Computed
// ============================================================================

const canStart = computed(() => topic.value.trim().length > 0 && !isCreating.value)

const username = computed(() => authStore.user?.username || '')

const roleLabel = computed(() => {
  if (isZh.value) {
    return userRole.value === 'viewer'
      ? '作为观众观看'
      : userRole.value === 'debater'
        ? '作为辩手参与'
        : '作为裁判评判'
  }
  return userRole.value === 'viewer' ? 'Play as Viewer' : userRole.value === 'debater' ? 'Play as Debater' : 'Play as Judge'
})

// Debate-specific suggestions
const debateSuggestions = computed(() => {
  if (isZh.value) {
    return [
      '人工智能是否应该被赋予法律人格？',
      '网络游戏对青少年利大于弊还是弊大于利？',
      '应该取消高考还是保留高考？',
      '社交媒体是否应该对用户内容进行更严格的审查？',
      '远程办公是否应该成为主流工作方式？',
      '是否应该对AI生成内容进行版权保护？',
      '教育应该更注重知识传授还是能力培养？',
      '是否应该允许基因编辑技术用于人类胚胎？',
    ]
  }
  return [
    'Should AI be granted legal personhood?',
    'Do video games benefit or harm teenagers more?',
    'Should college entrance exams be abolished?',
    'Should social media platforms have stricter content moderation?',
    'Should remote work become the mainstream?',
    'Should AI-generated content be copyright protected?',
    'Should education focus more on knowledge or skills?',
    'Should gene editing be allowed for human embryos?',
  ]
})

// ============================================================================
// Actions
// ============================================================================

async function startDebate() {
  if (!canStart.value) return

  isCreating.value = true
  try {
    // createSession() already saves to recent debates internally
    await store.createSession(topic.value.trim(), llmAssignments.value)

    // If user selected a role, join as that role
    if (userRole.value !== 'viewer') {
      await store.joinSession(
        store.currentSessionId!,
        userRole.value,
        undefined,
        undefined
      )
    }

    // Set stage to coin_toss (positions will auto-generate)
    // Don't call coinToss() yet - wait for user to click next
    await store.advanceStage('coin_toss')
  } catch (error) {
    console.error('Error starting debate:', error)
  } finally {
    isCreating.value = false
  }
}

function handleSuggestionSelect(suggestion: string) {
  topic.value = suggestion
}

function selectRole(role: 'debater' | 'judge' | 'viewer') {
  userRole.value = role
}

function handleKeydown(e: Event | KeyboardEvent) {
  if (!(e instanceof KeyboardEvent)) return
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (canStart.value) {
      startDebate()
    }
  }
}
</script>

<template>
  <div class="debate-setup-fullpage">
    <!-- Title Section -->
    <div class="debate-header">
      <ElAvatar
        :src="debateverseAvatarLg"
        alt="Debateverse"
        :size="128"
        class="debateverse-avatar"
      />
      <div class="text-center mt-6">
        <p class="debate-subtitle">
          {{ isZh ? `${username}你好，真正的智慧，诞生于观点的交锋。` : `${username}, true wisdom is born from the clash of viewpoints.` }}
        </p>
      </div>
    </div>

    <!-- Suggestion Bubbles -->
    <div class="debate-suggestions">
      <SuggestionBubbles :suggestions="debateSuggestions" @select="handleSuggestionSelect" />
    </div>

    <!-- Input Area -->
    <div class="debate-input-area">
      <!-- Input Container -->
      <div class="debate-input-container">
        <!-- Text Input -->
        <div class="debate-input-field">
          <ElInput
            v-model="topic"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="isZh ? '输入辩论主题...' : 'Enter debate topic...'"
            :disabled="isCreating"
            class="debate-textarea"
            @keydown="handleKeydown"
          />
        </div>

        <!-- Action buttons (right side) -->
        <div class="debate-input-actions">
          <!-- Role Selection Button -->
          <ElDropdown
            trigger="click"
            placement="top"
            @command="selectRole"
          >
            <ElButton
              class="role-select-btn"
              :disabled="isCreating"
            >
              {{ roleLabel }}
              <ElIcon class="ml-1"><ArrowDown /></ElIcon>
            </ElButton>
            <template #dropdown>
              <ElDropdownMenu>
                <ElDropdownItem
                  command="viewer"
                  :class="{ 'is-selected': userRole === 'viewer' }"
                >
                  {{ isZh ? '作为观众观看' : 'Play as Viewer' }}
                </ElDropdownItem>
                <ElDropdownItem
                  command="debater"
                  :class="{ 'is-selected': userRole === 'debater' }"
                >
                  {{ isZh ? '作为辩手参与' : 'Play as Debater' }}
                </ElDropdownItem>
                <ElDropdownItem
                  command="judge"
                  :class="{ 'is-selected': userRole === 'judge' }"
                >
                  {{ isZh ? '作为裁判评判' : 'Play as Judge' }}
                </ElDropdownItem>
              </ElDropdownMenu>
            </template>
          </ElDropdown>

          <!-- Send Button -->
          <ElButton
            type="primary"
            class="debate-send-btn"
            :disabled="!canStart"
            :loading="isCreating"
            @click="startDebate"
          >
            <Send :size="18" />
          </ElButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.debate-setup-fullpage {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  min-height: 100%;
  padding: 140px 20px 40px;
  background: #f9fafb;
}

.debate-header {
  text-align: center;
  margin-bottom: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.debateverse-avatar {
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.debateverse-avatar :deep(img) {
  object-fit: cover;
}

.debate-subtitle {
  font-size: 18px;
  color: #6b7280;
  margin: 0;
  font-weight: 400;
}

.debate-suggestions {
  width: 100%;
  max-width: 680px;
  margin-bottom: 40px;
}

.debate-input-area {
  width: 100%;
  max-width: 680px;
  flex-shrink: 0;
}

.debate-input-container {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px;
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 16px;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}

.debate-input-container:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.debate-input-field {
  flex: 1;
  min-width: 0;
}

.debate-textarea {
  width: 100%;
}

.debate-textarea :deep(.el-textarea__inner) {
  padding: 8px 0;
  border: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  box-shadow: none;
}

.debate-textarea :deep(.el-textarea__inner):focus {
  box-shadow: none;
}

.debate-textarea :deep(.el-textarea__inner)::placeholder {
  color: #9ca3af;
}

.debate-input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.role-select-btn {
  height: 40px;
  padding: 0 16px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #374151;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s;
}

.role-select-btn:hover:not(:disabled) {
  background: #f9fafb;
  border-color: #d1d5db;
}

.role-select-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.debate-send-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 10px;
  background: #3b82f6;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.debate-send-btn:hover:not(:disabled) {
  background: #2563eb;
}

.debate-send-btn:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: not-allowed;
}

/* Dropdown menu item selected state */
:deep(.el-dropdown-menu__item.is-selected) {
  background: #eff6ff;
  color: #3b82f6;
  font-weight: 500;
}

/* Dark mode support */
:global(.dark) .debate-setup-fullpage {
  background: #111827;
}

:global(.dark) .debate-title {
  color: #f9fafb;
}

:global(.dark) .debate-subtitle {
  color: #9ca3af;
}

:global(.dark) .debate-input-container {
  background: #1f2937;
  border-color: #374151;
}

:global(.dark) .debate-input-container:focus-within {
  border-color: #3b82f6;
}

:global(.dark) .debate-textarea :deep(.el-textarea__inner) {
  background: transparent;
  color: #f9fafb;
}

:global(.dark) .debate-textarea :deep(.el-textarea__inner)::placeholder {
  color: #6b7280;
}

:global(.dark) .role-select-btn {
  background: #1f2937;
  border-color: #374151;
  color: #f9fafb;
}

:global(.dark) .role-select-btn:hover:not(:disabled) {
  background: #374151;
  border-color: #4b5563;
}
</style>
