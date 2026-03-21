<script setup lang="ts">
/**
 * MindGraphContainer - MindGraph mode content area
 * Shows diagram type selection and discovery gallery
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElAvatar, ElButton, ElDialog, ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Upload, User } from '@element-plus/icons-vue'

import mindgraphLogo from '@/assets/mindgraph-logo-md.png'
import { useDiagramImport, useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { authFetch } from '@/utils/api'

import DiagramTemplateInput from './DiagramTemplateInput.vue'
import DiagramTypeGrid from './DiagramTypeGrid.vue'
import DiscoveryGallery from './DiscoveryGallery.vue'

const route = useRoute()
const router = useRouter()
const { isZh } = useLanguage()
const { triggerImport } = useDiagramImport()
const authStore = useAuthStore()
const notify = useNotifications()
const username = computed(() => authStore.user?.username || '')

// Collaboration: 校内 list + 共同 code
const showOrgSessionsDialog = ref(false)
const showSharedCodeDialog = ref(false)
const orgSessionsLoading = ref(false)
const orgSessions = ref<
  Array<{
    diagram_id: string
    title: string
    owner_username: string
    participant_count: number
  }>
>([])

const joinCode = ref(['', '', '', '', '', ''])
const isJoining = ref(false)
const codeInputRefs = ref<(HTMLInputElement | null)[]>([])

// Handle digit input
function handleDigitInput(index: number, event: Event) {
  const target = event.target as HTMLInputElement
  const value = target.value.replace(/\D/g, '') // Only digits

  if (value.length > 0) {
    joinCode.value[index] = value[value.length - 1] // Take last digit if multiple entered

    // Move to next input
    if (index < 5 && codeInputRefs.value[index + 1]) {
      codeInputRefs.value[index + 1]?.focus()
    }
  } else {
    joinCode.value[index] = ''
  }
}

// Handle backspace
function handleKeyDown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace' && !joinCode.value[index] && index > 0) {
    // Move to previous input if current is empty
    codeInputRefs.value[index - 1]?.focus()
  }
}

// Handle paste
function handlePaste(event: ClipboardEvent) {
  event.preventDefault()
  const pastedData = event.clipboardData?.getData('text') || ''
  const digits = pastedData.replace(/\D/g, '').slice(0, 6)

  digits.split('').forEach((digit, index) => {
    if (index < 6) {
      joinCode.value[index] = digit
    }
  })

  // Focus last filled input or next empty
  const nextEmptyIndex = digits.length < 6 ? digits.length : 5
  codeInputRefs.value[nextEmptyIndex]?.focus()
}

// Get formatted code string
function getFormattedCode(): string {
  const code = joinCode.value.join('')
  if (code.length === 6) {
    return `${code.slice(0, 3)}-${code.slice(3, 6)}`
  }
  return code
}

async function joinWorkshop() {
  const code = getFormattedCode()

  if (code.length !== 7) {
    // xxx-xxx = 7 characters
    notify.warning(
      isZh.value ? '请输入完整的演示代码' : 'Please enter the complete presentation code'
    )
    return
  }

  // Validate format (xxx-xxx)
  if (!/^\d{3}-\d{3}$/.test(code)) {
    notify.warning(
      isZh.value
        ? '演示代码格式不正确（应为 xxx-xxx）'
        : 'Invalid presentation code format (should be xxx-xxx)'
    )
    return
  }

  isJoining.value = true
  try {
    const response = await authFetch(`/api/workshop/join?code=${code}`, {
      method: 'POST',
    })

    if (response.ok) {
      const data = await response.json()
      notify.success(
        isZh.value
          ? `已加入演示：${data.workshop.title}`
          : `Joined presentation: ${data.workshop.title}`
      )
      // Navigate to the diagram; carry code so canvas can connect WS without re-entry
      const enc = encodeURIComponent(code)
      window.location.href = `/canvas?diagramId=${encodeURIComponent(data.workshop.diagram_id)}&join_workshop=${enc}`
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(error.detail || (isZh.value ? '加入演示失败' : 'Failed to join presentation'))
    }
  } catch (error) {
    console.error('Failed to join presentation mode:', error)
    notify.error(isZh.value ? '网络错误，加入失败' : 'Network error, failed to join')
  } finally {
    isJoining.value = false
  }
}

async function openOrgSessionsDialog() {
  showOrgSessionsDialog.value = true
  orgSessionsLoading.value = true
  orgSessions.value = []
  try {
    const response = await authFetch('/api/workshop/organization/sessions', { method: 'GET' })
    if (response.ok) {
      const data = await response.json()
      orgSessions.value = data.sessions || []
    } else {
      notify.error(isZh.value ? '无法加载校内会话' : 'Could not load school sessions')
    }
  } catch (error) {
    console.error(error)
    notify.error(isZh.value ? '网络错误' : 'Network error')
  } finally {
    orgSessionsLoading.value = false
  }
}

async function joinOrgSession(session: { diagram_id: string }) {
  isJoining.value = true
  try {
    const response = await authFetch('/api/workshop/join-organization', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diagram_id: session.diagram_id }),
    })
    if (response.ok) {
      const data = await response.json()
      const code = data.workshop.code as string
      const enc = encodeURIComponent(code)
      notify.success(
        isZh.value ? `加入协同：${data.workshop.title}` : `Joined: ${data.workshop.title}`
      )
      showOrgSessionsDialog.value = false
      window.location.href = `/canvas?diagramId=${encodeURIComponent(data.workshop.diagram_id)}&join_workshop=${enc}`
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(error.detail || (isZh.value ? '加入失败' : 'Failed to join'))
    }
  } catch (error) {
    console.error(error)
    notify.error(isZh.value ? '网络错误' : 'Network error')
  } finally {
    isJoining.value = false
  }
}

function handleCollabCommand(cmd: string) {
  if (cmd === 'organization') {
    void openOrgSessionsDialog()
  } else if (cmd === 'network') {
    showSharedCodeDialog.value = true
  }
}

// Handle join_workshop query parameter (from QR code scan)
onMounted(() => {
  const joinWorkshopCode = route.query.join_workshop as string | undefined
  if (joinWorkshopCode) {
    // Pre-fill the code
    const digits = joinWorkshopCode.replace(/\D/g, '').slice(0, 6)
    digits.split('').forEach((digit, index) => {
      if (index < 6) {
        joinCode.value[index] = digit
      }
    })
    // Remove query parameter from URL
    const newQuery = { ...route.query }
    delete newQuery.join_workshop
    router.replace({ query: newQuery })
    // Auto-join after a short delay
    setTimeout(() => {
      joinWorkshop()
    }, 500)
  }
})
</script>

<template>
  <div class="mindgraph-container flex flex-col h-full">
    <!-- Header -->
    <header class="h-14 px-4 flex items-center justify-between bg-white border-b border-gray-200">
      <div class="flex items-center gap-2">
        <h1 class="text-sm font-semibold text-gray-800">MindGraph</h1>
        <span class="text-xs text-gray-500">宇宙中最强大的AI思维图示生成软件</span>
      </div>
      <div class="flex items-center gap-2">
        <ElButton
          class="import-btn"
          size="small"
          :icon="Upload"
          @click="triggerImport"
        >
          {{ isZh ? '导入' : 'Import' }}
        </ElButton>
        <ElDropdown
          trigger="click"
          @command="handleCollabCommand"
        >
          <ElButton
            class="join-workshop-btn"
            size="small"
            :icon="User"
          >
            {{ isZh ? '协同' : 'Collaborate' }}
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="organization">
                {{ isZh ? '校内协同' : 'School collaboration' }}
              </ElDropdownItem>
              <ElDropdownItem command="network">
                {{ isZh ? '共同协同' : 'Shared collaboration' }}
              </ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
      </div>
    </header>

    <!-- 校内：同校可加入的会话列表 -->
    <ElDialog
      v-model="showOrgSessionsDialog"
      :title="isZh ? '校内协同' : 'School collaboration'"
      width="480px"
    >
      <div
        v-loading="orgSessionsLoading"
        class="min-h-[120px]"
      >
        <p
          v-if="!orgSessionsLoading && orgSessions.length === 0"
          class="text-gray-500 text-sm"
        >
          {{
            isZh
              ? '当前没有可加入的校内协同会话（需同事已开启「校内协同」）。'
              : 'No school sessions right now. A colleague must start “School collaboration” on the canvas.'
          }}
        </p>
        <ul
          v-else
          class="space-y-2 max-h-[360px] overflow-y-auto"
        >
          <li
            v-for="s in orgSessions"
            :key="s.diagram_id"
            class="flex items-center justify-between gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50/80"
          >
            <div class="min-w-0 flex-1">
              <div class="font-medium text-gray-900 truncate">{{ s.title }}</div>
              <div class="text-xs text-gray-500">
                {{ s.owner_username }} ·
                {{
                  isZh
                    ? `${s.participant_count} 人在线`
                    : `${s.participant_count} online`
                }}
              </div>
            </div>
            <ElButton
              type="primary"
              size="small"
              :loading="isJoining"
              @click="joinOrgSession(s)"
            >
              {{ isZh ? '加入' : 'Join' }}
            </ElButton>
          </li>
        </ul>
      </div>
    </ElDialog>

    <!-- 共同：输入邀请码 -->
    <ElDialog
      v-model="showSharedCodeDialog"
      :title="isZh ? '共同协同' : 'Shared collaboration'"
      width="400px"
    >
      <div class="join-workshop-dialog">
        <p class="mb-4 text-gray-600">
          {{
            isZh
              ? '输入邀请码（xxx-xxx），加入对方的协同会话。'
              : 'Enter the invitation code (xxx-xxx) to join their session.'
          }}
        </p>
        <div class="code-input-container">
          <div class="code-input-boxes">
            <input
              v-for="(digit, index) in joinCode.slice(0, 3)"
              :key="index"
              :ref="
                (el) => {
                  codeInputRefs[index] = el as HTMLInputElement | null
                }
              "
              v-model="joinCode[index]"
              type="text"
              inputmode="numeric"
              maxlength="1"
              class="code-input-box"
              @input="handleDigitInput(index, $event)"
              @keydown="handleKeyDown(index, $event)"
              @paste="handlePaste"
            />
            <span class="code-dash">-</span>
            <input
              v-for="(digit, index) in joinCode.slice(3, 6)"
              :key="index + 3"
              :ref="
                (el) => {
                  codeInputRefs[index + 3] = el as HTMLInputElement | null
                }
              "
              v-model="joinCode[index + 3]"
              type="text"
              inputmode="numeric"
              maxlength="1"
              class="code-input-box"
              @input="handleDigitInput(index + 3, $event)"
              @keydown="handleKeyDown(index + 3, $event)"
              @paste="handlePaste"
            />
          </div>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <ElButton @click="showSharedCodeDialog = false">
            {{ isZh ? '取消' : 'Cancel' }}
          </ElButton>
          <ElButton
            type="primary"
            :loading="isJoining"
            @click="joinWorkshop"
          >
            {{ isZh ? '加入' : 'Join' }}
          </ElButton>
        </div>
      </div>
    </ElDialog>

    <!-- Scrollable content area -->
    <div class="flex-1 min-h-0 overflow-y-auto">
      <div class="p-5 w-[70%] mx-auto pb-8">
        <!-- Welcome header - above input -->
        <div class="flex flex-col items-center justify-center mb-8">
          <div class="mindgraph-logo-wrapper">
            <div class="mindgraph-logo-inner">
              <ElAvatar
                :src="mindgraphLogo"
                alt="MindGraph"
                :size="96"
                class="mindgraph-logo"
              />
            </div>
          </div>
          <div class="text-lg text-gray-600">
            {{
              isZh
                ? `${username}你好，我是你的AI思维图示助手`
                : `Hello ${username}, I'm your AI visual thinking assistant`
            }}
          </div>
        </div>

        <!-- Template input -->
        <DiagramTemplateInput />

        <!-- Diagram type grid -->
        <div class="mt-6">
          <DiagramTypeGrid />
        </div>

        <!-- Discovery gallery -->
        <DiscoveryGallery />
      </div>
    </div>
  </div>
</template>

<style scoped>
@property --rainbow-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.mindgraph-logo-wrapper {
  position: relative;
  width: 104px;
  height: 104px;
  border-radius: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}

.mindgraph-logo-wrapper::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 20px;
  padding: 4px;
  --rainbow-angle: 0deg;
  /* Swiss design palette: stone tones + primary blue accent */
  background: conic-gradient(
    from var(--rainbow-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 45deg,
    #a8a29e 90deg,
    #409eff 135deg,
    #66b1ff 180deg,
    #409eff 225deg,
    #78716c 270deg,
    #d6d3d1 315deg,
    #e7e5e4 360deg
  );
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: rainbow-travel 2.5s linear infinite;
}

@keyframes rainbow-travel {
  to {
    --rainbow-angle: 360deg;
  }
}

.mindgraph-logo-inner {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 16px;
  overflow: hidden;
  background: var(--mg-bg-primary, #fff);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.mindgraph-logo {
  border-radius: 16px;
}

.mindgraph-logo :deep(img) {
  object-fit: cover;
}

/* Import button - Swiss Design style */
.import-btn {
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

/* Join presentation button - Swiss Design style (matching MindMate) */
.join-workshop-btn {
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

/* Code input boxes - Modern square boxes */
.code-input-container {
  display: flex;
  justify-content: center;
  margin: 20px 0;
}

.code-input-boxes {
  display: flex;
  align-items: center;
  gap: 8px;
}

.code-input-box {
  width: 48px;
  height: 48px;
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  border: 2px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #1f2937;
  transition: all 0.2s ease;
  outline: none;
}

.code-input-box:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  background: #f9fafb;
}

.code-dash {
  font-size: 24px;
  font-weight: 600;
  color: #6b7280;
  margin: 0 4px;
  user-select: none;
}

.dark .code-input-box {
  background: #1f2937;
  border-color: #4b5563;
  color: #f9fafb;
}

.dark .code-input-box:focus {
  border-color: #3b82f6;
  background: #111827;
}

.dark .code-dash {
  color: #9ca3af;
}
</style>
