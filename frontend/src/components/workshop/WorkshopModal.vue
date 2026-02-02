<script setup lang="ts">
/**
 * WorkshopModal - Modal for managing workshop sessions
 * Allows users to start/stop workshops and join with codes
 */
import { computed, ref, watch } from 'vue'

import {
  ElButton,
  ElDialog,
  ElInput,
  ElMessage,
  ElTag,
} from 'element-plus'

import { Copy, Users, X } from 'lucide-vue-next'

import { authFetch } from '@/utils/api'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'

// QR Code generation using a simple API service
function generateQRCodeUrl(text: string): string {
  // Use a QR code API service (you can replace with a library like qrcode if preferred)
  const encodedText = encodeURIComponent(text)
  return `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodedText}`
}

interface Props {
  visible: boolean
  diagramId: string | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'workshop-started', code: string): void
  (e: 'workshop-stopped'): void
  (e: 'workshop-code-changed', code: string | null): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const { isZh } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()

// Workshop state
const workshopCode = ref<string | null>(null)
const isActive = ref(false)
const participantCount = ref(0)
const isLoading = ref(false)
const joinCode = ref('')

// QR Code URL
const qrCodeUrl = computed(() => {
  if (!workshopCode.value) return null
  // Generate URL that will join the workshop when scanned
  const joinUrl = `${window.location.origin}/mindgraph?join_workshop=${workshopCode.value}`
  return generateQRCodeUrl(joinUrl)
})

// Computed
const showDialog = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

// Watch for diagram changes - auto-generate code when opening
watch(
  () => props.visible,
  async (visible) => {
    if (visible && props.diagramId) {
      // Check if code already exists, otherwise generate one
      await checkWorkshopStatus()
      if (!workshopCode.value) {
        await startWorkshop()
      }
      // Emit code change
      if (workshopCode.value) {
        emit('workshop-code-changed', workshopCode.value)
      }
    } else {
      // Reset state when closing
      workshopCode.value = null
      isActive.value = false
      participantCount.value = 0
      joinCode.value = ''
      emit('workshop-code-changed', null)
    }
  }
)

// Watch for workshop code changes and emit
watch(
  () => workshopCode.value,
  (code) => {
    emit('workshop-code-changed', code)
  }
)

// Check workshop status
async function checkWorkshopStatus() {
  if (!props.diagramId) return

  try {
    const response = await authFetch(
      `/api/diagrams/${props.diagramId}/workshop/status`
    )

    if (response.ok) {
      const data = await response.json()
      isActive.value = data.active || false
      workshopCode.value = data.code || null
      participantCount.value = data.participant_count || 0
    } else {
      // Non-critical error, just log it
      const error = await response.json().catch(() => ({}))
      console.warn('Failed to check workshop status:', error.detail || 'Unknown error')
    }
  } catch (error) {
    // Non-critical error, just log it
    console.warn('Failed to check workshop status:', error)
  }
}

// Start workshop
async function startWorkshop() {
  if (!props.diagramId) return

  isLoading.value = true
  try {
    const response = await authFetch(
      `/api/diagrams/${props.diagramId}/workshop/start`,
      {
        method: 'POST',
      }
    )

    if (response.ok) {
      const data = await response.json()
      workshopCode.value = data.code
      isActive.value = true
      participantCount.value = 1 // Owner is first participant
      emit('workshop-started', data.code)
      // Note: Workshop code is also available via props/emits for parent component
      notify.success(
        isZh.value
          ? '工作坊代码已生成，分享给其他人即可一起编辑'
          : 'Workshop code generated! Share with others to collaborate'
      )
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(
        error.detail ||
          (isZh.value ? '启动工作坊失败' : 'Failed to start workshop')
      )
    }
  } catch (error) {
    console.error('Failed to start workshop:', error)
    notify.error(
      isZh.value ? '网络错误，启动失败' : 'Network error, failed to start'
    )
  } finally {
    isLoading.value = false
  }
}

// Stop workshop
async function stopWorkshop() {
  if (!props.diagramId) return

  isLoading.value = true
  try {
    const response = await authFetch(
      `/api/diagrams/${props.diagramId}/workshop/stop`,
      {
        method: 'POST',
      }
    )

    if (response.ok) {
      workshopCode.value = null
      isActive.value = false
      participantCount.value = 0
      emit('workshop-stopped')
      notify.success(
        isZh.value ? '工作坊已停止' : 'Workshop stopped'
      )
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(
        error.detail ||
          (isZh.value ? '停止工作坊失败' : 'Failed to stop workshop')
      )
    }
  } catch (error) {
    console.error('Failed to stop workshop:', error)
    notify.error(
      isZh.value ? '网络错误，停止失败' : 'Network error, failed to stop'
    )
  } finally {
    isLoading.value = false
  }
}

// Join workshop
async function joinWorkshop() {
  const code = joinCode.value.trim()

  if (!code) {
    notify.warning(
      isZh.value ? '请输入工作坊代码' : 'Please enter a workshop code'
    )
    return
  }

  // Validate format (xxx-xxx)
  if (!/^\d{3}-\d{3}$/.test(code)) {
    notify.warning(
      isZh.value
        ? '工作坊代码格式不正确（应为 xxx-xxx）'
        : 'Invalid workshop code format (should be xxx-xxx)'
    )
    return
  }

  isLoading.value = true
  try {
    const response = await authFetch(`/api/workshop/join?code=${code}`, {
      method: 'POST',
    })

    if (response.ok) {
      const data = await response.json()
      notify.success(
        isZh.value
          ? `已加入工作坊：${data.workshop.title}`
          : `Joined workshop: ${data.workshop.title}`
      )
      // Navigate to the diagram
      window.location.href = `/canvas?diagram_id=${data.workshop.diagram_id}`
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(
        error.detail ||
          (isZh.value ? '加入工作坊失败' : 'Failed to join workshop')
      )
    }
  } catch (error) {
    console.error('Failed to join workshop:', error)
    notify.error(
      isZh.value ? '网络错误，加入失败' : 'Network error, failed to join'
    )
  } finally {
    isLoading.value = false
  }
}

// Copy code to clipboard
async function copyCode() {
  if (!workshopCode.value) return

  try {
    await navigator.clipboard.writeText(workshopCode.value)
    ElMessage.success(
      isZh.value ? '代码已复制到剪贴板' : 'Code copied to clipboard'
    )
  } catch (error) {
    console.error('Failed to copy:', error)
    ElMessage.error(
      isZh.value ? '复制失败' : 'Failed to copy'
    )
  }
}
</script>

<template>
  <ElDialog
    v-model="showDialog"
    :title="isZh ? '工作坊协作' : 'Workshop Collaboration'"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="workshop-modal">
      <!-- Generate Code Section (for diagram editor) -->
      <div
        v-if="diagramId"
        class="workshop-section"
      >
        <h3 class="section-title">
          {{ isZh ? '生成工作坊代码' : 'Generate Workshop Code' }}
        </h3>

        <div
          v-if="workshopCode"
          class="active-workshop"
        >
          <p class="description mb-4">
            {{
              isZh
                ? '扫描二维码或分享代码给其他人，邀请他们加入并一起编辑此图示。'
                : 'Scan the QR code or share the code with others to join and collaboratively edit this diagram.'
            }}
          </p>

          <div class="workshop-share-container">
            <!-- QR Code -->
            <div class="qr-code-section">
              <div class="qr-code-wrapper">
                <img
                  v-if="qrCodeUrl"
                  :src="qrCodeUrl"
                  alt="Workshop QR Code"
                  class="qr-code-image"
                />
              </div>
              <p class="qr-code-hint">
                {{ isZh ? '扫描二维码加入' : 'Scan to join' }}
              </p>
            </div>

            <!-- Code Display -->
            <div class="code-section">
              <div class="code-display">
                <ElTag
                  type="success"
                  size="large"
                  class="workshop-code-tag"
                >
                  {{ workshopCode }}
                </ElTag>
                <ElButton
                  text
                  size="small"
                  @click="copyCode"
                >
                  <Copy class="w-4 h-4" />
                  {{ isZh ? '复制' : 'Copy' }}
                </ElButton>
              </div>
              <p class="code-hint">
                {{ isZh ? '或输入代码加入' : 'Or enter code to join' }}
              </p>
            </div>
          </div>

          <div
            v-if="participantCount > 0"
            class="participants-info mt-4"
          >
            <Users class="w-4 h-4" />
            <span>
              {{
                isZh
                  ? `${participantCount} 位参与者`
                  : `${participantCount} participant${participantCount !== 1 ? 's' : ''}`
              }}
            </span>
          </div>
        </div>

        <div
          v-else
          class="inactive-workshop"
        >
          <p class="description">
            {{
              isZh
                ? '生成工作坊代码后，其他人可以使用此代码加入并一起编辑此图示。'
                : 'Generate a workshop code to allow others to join and collaboratively edit this diagram.'
            }}
          </p>
          <ElButton
            type="primary"
            :loading="isLoading"
            @click="startWorkshop"
          >
            {{ isZh ? '生成代码' : 'Generate Code' }}
          </ElButton>
        </div>
      </div>
    </div>
  </ElDialog>
</template>

<style scoped>
.workshop-modal {
  padding: 8px 0;
}

.workshop-section {
  margin-bottom: 24px;
}

.workshop-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
}

.description {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin-bottom: 16px;
  line-height: 1.6;
}

.active-workshop {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.code-display {
  display: flex;
  align-items: center;
  gap: 12px;
}

.workshop-code-tag {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 2px;
  padding: 8px 16px;
  font-family: ui-monospace, monospace;
}

.participants-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.join-input-group {
  display: flex;
  gap: 8px;
}

.join-input {
  flex: 1;
}

.inactive-workshop {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.workshop-share-container {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: center;
  padding: 16px 0;
  flex-wrap: wrap;
}

@media (max-width: 640px) {
  .workshop-share-container {
    flex-direction: column;
    align-items: center;
  }
}

.qr-code-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.qr-code-wrapper {
  padding: 12px;
  background: #fff;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.qr-code-image {
  width: 200px;
  height: 200px;
  display: block;
}

.qr-code-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
  margin: 0;
}

.code-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.code-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
  margin: 0;
}
</style>
