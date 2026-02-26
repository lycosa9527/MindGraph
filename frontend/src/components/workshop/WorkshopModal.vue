<script setup lang="ts">
/**
 * WorkshopModal - Modal for managing workshop sessions
 * Allows users to start/stop workshops and join with codes
 */
import { computed, ref, watch } from 'vue'

import { ElButton, ElDialog, ElMessage, ElTag } from 'element-plus'

import { Copy, Users } from 'lucide-vue-next'

import { getDefaultDiagramName, useLanguage, useNotifications } from '@/composables'
import { useDiagramStore, useSavedDiagramsStore } from '@/stores'
import { authFetch } from '@/utils/api'

// QR Code generation using backend endpoint (offline, no CDN)
function generateQRCodeUrl(text: string): string {
  // Use backend endpoint for QR code generation (offline, secure)
  const encodedText = encodeURIComponent(text)
  // Smaller QR code for Swiss design: 150x150px
  return `/api/qrcode?data=${encodedText}&size=150`
}

interface Props {
  visible: boolean
  diagramId: string | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'workshopStarted', code: string): void
  (e: 'workshopStopped'): void
  (e: 'workshopCodeChanged', code: string | null): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const { isZh } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const savedDiagramsStore = useSavedDiagramsStore()

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

/** Get diagram spec for saving (uses recalculated positions for bubble map) */
function getDiagramSpec(): Record<string, unknown> | null {
  return diagramStore.getSpecForSave()
}

// Get diagram title for saving
function getDiagramTitle(): string {
  const topicText = diagramStore.getTopicNodeText()
  if (topicText) {
    return topicText
  }
  if (diagramStore.effectiveTitle) {
    return diagramStore.effectiveTitle
  }
  return getDefaultDiagramName(diagramStore.type, isZh.value)
}

// Auto-save diagram if needed before starting workshop
async function ensureDiagramSaved(): Promise<string | null> {
  // If diagramId is already provided, use it
  if (props.diagramId) {
    return props.diagramId
  }

  // Check if diagram is already saved
  if (savedDiagramsStore.activeDiagramId) {
    return savedDiagramsStore.activeDiagramId
  }

  // Need to save the diagram first
  if (!diagramStore.type || !diagramStore.data) {
    notify.warning(isZh.value ? '没有可保存的图示' : 'No diagram to save')
    return null
  }

  const spec = getDiagramSpec()
  if (!spec) {
    notify.warning(isZh.value ? '图示数据无效' : 'Invalid diagram data')
    return null
  }

  isLoading.value = true
  try {
    const result = await savedDiagramsStore.manualSaveDiagram(
      getDiagramTitle(),
      diagramStore.type,
      spec,
      isZh.value ? 'zh' : 'en',
      null // TODO: Generate thumbnail
    )

    if (result.success && result.diagramId) {
      // Ensure the diagram is set as active in the store
      savedDiagramsStore.setActiveDiagram(result.diagramId)
      notify.success(
        isZh.value ? '图示已保存，正在启动工作坊...' : 'Diagram saved, starting workshop...'
      )
      // Small delay to ensure database commit is complete
      await new Promise((resolve) => setTimeout(resolve, 100))
      return result.diagramId
    } else if (result.needsSlotClear) {
      notify.warning(
        isZh.value
          ? '图库已满，请先删除一个图示后再试'
          : 'Gallery is full. Please delete a diagram first'
      )
      return null
    } else {
      notify.error(result.error || (isZh.value ? '保存失败' : 'Failed to save diagram'))
      return null
    }
  } catch (error) {
    console.error('Failed to save diagram:', error)
    notify.error(isZh.value ? '网络错误，保存失败' : 'Network error, failed to save')
    return null
  } finally {
    isLoading.value = false
  }
}

// Watch for diagram changes - auto-generate code when opening
watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      // Ensure diagram is saved before starting workshop
      const diagramId = await ensureDiagramSaved()

      if (diagramId) {
        // Check if code already exists, otherwise generate one
        // Note: We need to check status with the saved diagramId
        // Since props.diagramId might be null, we'll pass diagramId to checkWorkshopStatus
        await checkWorkshopStatusWithId(diagramId)
        if (!workshopCode.value) {
          await startWorkshopWithId(diagramId)
        }
        // Emit code change
        if (workshopCode.value) {
          emit('workshopCodeChanged', workshopCode.value)
        }
      }
    } else {
      // Reset state when closing
      workshopCode.value = null
      isActive.value = false
      participantCount.value = 0
      joinCode.value = ''
      emit('workshopCodeChanged', null)
    }
  }
)

// Watch for workshop code changes and emit
watch(
  () => workshopCode.value,
  (code) => {
    emit('workshopCodeChanged', code)
  }
)

// Check workshop status with specific diagram ID
async function checkWorkshopStatusWithId(diagramId: string) {
  if (!diagramId) return

  try {
    const response = await authFetch(`/api/diagrams/${diagramId}/workshop/status`)

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

// Start workshop with specific diagram ID
async function startWorkshopWithId(diagramId: string) {
  if (!diagramId) return

  // Prevent multiple simultaneous calls
  if (isLoading.value) {
    console.warn('[WorkshopModal] Workshop start already in progress, skipping')
    return
  }

  isLoading.value = true
  try {
    const response = await authFetch(`/api/diagrams/${diagramId}/workshop/start`, {
      method: 'POST',
    })

    if (response.ok) {
      const data = await response.json()
      workshopCode.value = data.code
      isActive.value = true
      participantCount.value = 1 // Owner is first participant
      emit('workshopStarted', data.code)
      // Note: Workshop code is also available via props/emits for parent component
      notify.success(
        isZh.value
          ? '工作坊代码已生成，分享给其他人即可一起编辑'
          : 'Workshop code generated! Share with others to collaborate'
      )
    } else {
      const error = await response.json().catch(() => ({}))
      const errorMessage = error.detail || error.message || `HTTP ${response.status}`
      console.error('[WorkshopModal] Failed to start workshop:', {
        status: response.status,
        error,
        errorDetail: error.detail,
        errorMessage: error.message,
        fullError: JSON.stringify(error, null, 2),
        diagramId,
      })
      console.error('[WorkshopModal] Full error response:', error)
      // Use the error message from backend (now includes specific details)
      notify.error(
        isZh.value ? `启动工作坊失败: ${errorMessage}` : `Failed to start workshop: ${errorMessage}`
      )
    }
  } catch (error) {
    console.error('Failed to start workshop:', error)
    notify.error(isZh.value ? '网络错误，启动失败' : 'Network error, failed to start')
  } finally {
    isLoading.value = false
  }
}

// Handle generate code button click
async function handleGenerateCode() {
  // Ensure diagram is saved first
  const diagramId = await ensureDiagramSaved()
  if (diagramId) {
    await startWorkshopWithId(diagramId)
    // Emit code change after starting
    if (workshopCode.value) {
      emit('workshopCodeChanged', workshopCode.value)
    }
  }
}

// Copy code to clipboard
async function copyCode() {
  if (!workshopCode.value) return

  try {
    await navigator.clipboard.writeText(workshopCode.value)
    ElMessage.success(isZh.value ? '代码已复制到剪贴板' : 'Code copied to clipboard')
  } catch (error) {
    console.error('Failed to copy:', error)
    ElMessage.error(isZh.value ? '复制失败' : 'Failed to copy')
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
            <!-- QR Code (top) -->
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

            <!-- Code Display (below QR code) -->
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
                  class="copy-button"
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
            @click="handleGenerateCode"
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
  padding: 4px 0;
}

/* Swiss Design: Clean dialog styling */
:deep(.el-dialog) {
  border-radius: 12px;
}

:deep(.el-dialog__header) {
  padding: 20px 24px 16px;
  border-bottom: 1px solid #f3f4f6;
}

:deep(.el-dialog__body) {
  padding: 24px;
}

:deep(.el-dialog__title) {
  font-weight: 600;
  font-size: 18px;
  letter-spacing: -0.3px;
}

.workshop-section {
  margin-bottom: 24px;
}

.workshop-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
  letter-spacing: -0.3px;
}

.description {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin-bottom: 24px;
  line-height: 1.6;
  text-align: center;
}

.active-workshop {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Code display styles moved to code-section above */

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

/* Swiss Design: Clean, minimal, functional layout */
.workshop-share-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 20px 0;
}

.qr-code-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.qr-code-wrapper {
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.qr-code-image {
  width: 150px;
  height: 150px;
  display: block;
}

.qr-code-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-align: center;
  margin: 0;
  font-weight: 400;
  letter-spacing: 0.3px;
}

.code-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.code-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
}

.workshop-code-tag {
  font-size: 24px;
  font-weight: 600;
  letter-spacing: 4px;
  padding: 12px 24px;
  font-family: ui-monospace, monospace;
  background: #f0f9ff;
  border-color: #93c5fd;
  color: #1e40af;
}

.copy-button {
  color: var(--el-text-color-regular);
  transition: color 0.2s ease;
}

.copy-button:hover {
  color: var(--el-color-primary);
}

.code-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-align: center;
  margin: 0;
  font-weight: 400;
  letter-spacing: 0.3px;
}
</style>
