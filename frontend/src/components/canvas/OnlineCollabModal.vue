<script setup lang="ts">
/**
 * OnlineCollabModal — canvas online collaboration (org vs network visibility).
 * Not the separate Workshop Chat module.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { ElButton, ElDialog, ElPopover, ElRadioButton, ElRadioGroup, ElTag } from 'element-plus'

import { Copy, Settings, Users } from 'lucide-vue-next'

import {
  getDefaultDiagramName,
  useDiagramSpecForSave,
  useLanguage,
  useNotifications,
} from '@/composables'
import { useDiagramStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useUIStore } from '@/stores/ui'
import { authFetch } from '@/utils/api'

function generateQRCodeUrl(text: string): string {
  const encodedText = encodeURIComponent(text)
  return `/api/qrcode?data=${encodedText}&size=150`
}

interface Props {
  visible: boolean
  diagramId: string | null
  /** organization = 校内, network = 共同 (VooV-style code share) */
  mode: 'organization' | 'network'
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'collabCodeChanged', code: string | null): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const { t, promptLanguage } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramStore()
const savedDiagramsStore = useSavedDiagramsStore()
const uiStore = useUIStore()

const workshopCode = ref<string | null>(null)
const resolvedDiagramId = ref<string | null>(null)
const isActive = ref(false)
const participantCount = ref(0)
const isLoading = ref(false)
/** Session window preset for next start (校内: 1h|today|2d; 校外: today|2d) */
const sessionDurationPreset = ref<'1h' | 'today' | '2d'>('today')
const remainingSeconds = ref<number | null>(null)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const isNetworkMode = computed(() => props.mode === 'network')

const durationOptions = computed(() => {
  if (isNetworkMode.value) {
    return [
      { value: 'today' as const, labelKey: 'collab.durationToday' },
      { value: '2d' as const, labelKey: 'collab.duration2d' },
    ]
  }
  return [
    { value: '1h' as const, labelKey: 'collab.duration1h' },
    { value: 'today' as const, labelKey: 'collab.durationToday' },
    { value: '2d' as const, labelKey: 'collab.duration2d' },
  ]
})

watch(isNetworkMode, (net) => {
  if (net && sessionDurationPreset.value === '1h') {
    sessionDurationPreset.value = 'today'
  }
})

function formatRemaining(): string {
  const sec = remainingSeconds.value
  if (sec === null || sec < 0) return ''
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) {
    return t('collab.countdown.hoursMinutes', { h, m })
  }
  return t('collab.countdown.minutesSeconds', { m, s })
}

function startCountdown() {
  stopCountdown()
  countdownTimer = setInterval(() => {
    if (remainingSeconds.value !== null && remainingSeconds.value > 0) {
      remainingSeconds.value--
    }
  }, 1000)
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

onUnmounted(() => {
  stopCountdown()
})

const qrCodeUrl = computed(() => {
  if (!workshopCode.value || !isNetworkMode.value) return null
  const joinUrl = `${window.location.origin}/mindgraph?join_workshop=${workshopCode.value}`
  return generateQRCodeUrl(joinUrl)
})

const joinLinkDisplay = computed(() => {
  if (!workshopCode.value || !isNetworkMode.value) return ''
  return `${window.location.origin}/mindgraph?join_workshop=${encodeURIComponent(workshopCode.value)}`
})

const showDialog = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const getDiagramSpec = useDiagramSpecForSave()

function getDiagramTitle(): string {
  const topicText = diagramStore.getTopicNodeText()
  if (topicText) {
    return topicText
  }
  if (diagramStore.effectiveTitle) {
    return diagramStore.effectiveTitle
  }
  return getDefaultDiagramName(diagramStore.type, uiStore.language)
}

async function ensureDiagramSaved(): Promise<string | null> {
  if (props.diagramId) {
    resolvedDiagramId.value = props.diagramId
    return props.diagramId
  }
  if (savedDiagramsStore.activeDiagramId) {
    resolvedDiagramId.value = savedDiagramsStore.activeDiagramId
    return savedDiagramsStore.activeDiagramId
  }
  if (!diagramStore.type || !diagramStore.data) {
    notify.warning(t('collab.noDiagramToSave'))
    return null
  }
  const spec = getDiagramSpec()
  if (!spec) {
    notify.warning(t('collab.invalidDiagramData'))
    return null
  }
  isLoading.value = true
  try {
    const result = await savedDiagramsStore.manualSaveDiagram(
      getDiagramTitle(),
      diagramStore.type,
      spec,
      promptLanguage.value,
      null
    )
    if (result.success && result.diagramId) {
      savedDiagramsStore.setActiveDiagram(result.diagramId)
      resolvedDiagramId.value = result.diagramId
      notify.success(t('collab.diagramSavedStarting'))
      await new Promise((resolve) => setTimeout(resolve, 100))
      return result.diagramId
    }
    if (result.needsSlotClear) {
      notify.warning(t('collab.galleryFull'))
      return null
    }
    notify.error(result.error || t('collab.saveFailed'))
    return null
  } catch (error) {
    console.error('Failed to save diagram:', error)
    notify.error(t('collab.networkErrorSave'))
    return null
  } finally {
    isLoading.value = false
  }
}

watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      const diagramId = await ensureDiagramSaved()
      if (diagramId) {
        await checkWorkshopStatusWithId(diagramId)
        if (!workshopCode.value) {
          await startWorkshopWithId(diagramId)
        }
        if (workshopCode.value) {
          emit('collabCodeChanged', workshopCode.value)
        }
      }
    } else {
      workshopCode.value = null
      isActive.value = false
      participantCount.value = 0
      remainingSeconds.value = null
      stopCountdown()
    }
  }
)

watch(
  () => props.diagramId,
  (id) => {
    if (id) {
      resolvedDiagramId.value = id
    }
  },
  { immediate: true }
)

async function checkWorkshopStatusWithId(diagramId: string) {
  if (!diagramId) return
  try {
    const response = await authFetch(`/api/diagrams/${diagramId}/workshop/status`)
    if (response.ok) {
      const data = await response.json()
      isActive.value = data.active || false
      workshopCode.value = data.code || null
      participantCount.value = data.participant_count || 0
      if (typeof data.remaining_seconds === 'number') {
        remainingSeconds.value = data.remaining_seconds
        if (data.active && workshopCode.value) {
          startCountdown()
        }
      } else {
        remainingSeconds.value = null
      }
    } else {
      const err = await response.json().catch(() => ({}))
      console.warn('Workshop status:', err.detail || response.status)
    }
  } catch (error) {
    console.warn('Workshop status check failed:', error)
  }
}

async function startWorkshopWithId(diagramId: string) {
  if (!diagramId) return
  if (isLoading.value) {
    return
  }
  const visibility = props.mode === 'network' ? 'network' : 'organization'
  const duration =
    isNetworkMode.value && sessionDurationPreset.value === '1h'
      ? 'today'
      : sessionDurationPreset.value
  isLoading.value = true
  try {
    const response = await authFetch(`/api/diagrams/${diagramId}/workshop/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ visibility, duration }),
    })
    if (response.ok) {
      const data = await response.json()
      workshopCode.value = data.code
      isActive.value = true
      participantCount.value = 1
      await checkWorkshopStatusWithId(diagramId)
      if (isNetworkMode.value) {
        notify.success(t('collab.codeGenerated'))
      } else {
        notify.success(t('collab.schoolStarted'))
      }
    } else {
      const error = await response.json().catch(() => ({}))
      const errorMessage = error.detail || error.message || `HTTP ${response.status}`
      notify.error(t('collab.startFailed', { msg: String(errorMessage) }))
    }
  } catch (error) {
    console.error('Start collaboration failed:', error)
    notify.error(t('collab.networkErrorStart'))
  } finally {
    isLoading.value = false
  }
}

async function handleGenerateCode() {
  const diagramId = await ensureDiagramSaved()
  if (diagramId) {
    await startWorkshopWithId(diagramId)
    if (workshopCode.value) {
      emit('collabCodeChanged', workshopCode.value)
    }
  }
}

async function copyCode() {
  if (!workshopCode.value) return
  try {
    await navigator.clipboard.writeText(workshopCode.value)
    notify.success(t('collab.codeCopied'))
  } catch (error) {
    console.error('Copy failed:', error)
    notify.error(t('collab.copyFailed'))
  }
}

async function copyJoinLink() {
  if (!joinLinkDisplay.value) return
  try {
    await navigator.clipboard.writeText(joinLinkDisplay.value)
    notify.success(t('collab.linkCopied'))
  } catch (error) {
    console.error('Copy failed:', error)
    notify.error(t('collab.copyFailed'))
  }
}

async function endCollaboration() {
  const diagramId = resolvedDiagramId.value
  if (!diagramId) return
  isLoading.value = true
  try {
    const response = await authFetch(`/api/diagrams/${diagramId}/workshop/stop`, {
      method: 'POST',
    })
    if (response.ok) {
      workshopCode.value = null
      isActive.value = false
      participantCount.value = 0
      emit('collabCodeChanged', null)
      showDialog.value = false
      notify.success(t('collab.ended'))
    } else {
      const error = await response.json().catch(() => ({}))
      notify.error(error.detail || t('collab.endFailed'))
    }
  } catch (error) {
    console.error('Stop collaboration failed:', error)
    notify.error(t('collab.networkError'))
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <ElDialog
    v-model="showDialog"
    :title="t('collab.title')"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="online-collab-modal">
      <div
        v-if="resolvedDiagramId"
        class="collab-section"
      >
        <h3 class="section-title">
          {{ isNetworkMode ? t('collab.sectionNetwork') : t('collab.sectionSchool') }}
        </h3>

        <p
          v-if="workshopCode && remainingSeconds !== null && remainingSeconds >= 0"
          class="session-remaining text-sm text-gray-500 mb-3"
        >
          {{ t('collab.sessionRemaining') }}: {{ formatRemaining() }}
        </p>

        <div v-if="workshopCode && isNetworkMode">
          <p class="description mb-4">
            {{ t('collab.shareDescNetwork') }}
          </p>
          <div class="share-container">
            <div class="qr-code-section">
              <div class="qr-code-wrapper">
                <img
                  v-if="qrCodeUrl"
                  :src="qrCodeUrl"
                  alt="Join QR"
                  class="qr-code-image"
                />
              </div>
              <p class="qr-code-hint">{{ t('collab.scanToJoin') }}</p>
            </div>
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
                  {{ t('collab.copy') }}
                </ElButton>
              </div>
              <p class="code-hint text-xs break-all px-2">{{ joinLinkDisplay }}</p>
              <ElButton
                text
                size="small"
                class="mt-1"
                @click="copyJoinLink"
              >
                {{ t('collab.copyLink') }}
              </ElButton>
            </div>
          </div>
          <div
            v-if="participantCount > 0"
            class="participants-info mt-4"
          >
            <Users class="w-4 h-4" />
            <span>
              {{ t('collab.participants', { n: participantCount }) }}
            </span>
          </div>
          <div class="mt-4 flex justify-end">
            <ElButton
              type="danger"
              plain
              :loading="isLoading"
              @click="endCollaboration"
            >
              {{ t('collab.end') }}
            </ElButton>
          </div>
        </div>

        <div v-else-if="workshopCode && !isNetworkMode">
          <p class="description mb-4">
            {{ t('collab.schoolDescActive') }}
          </p>
          <div
            v-if="participantCount > 0"
            class="participants-info"
          >
            <Users class="w-4 h-4" />
            <span>
              {{ t('collab.participants', { n: participantCount }) }}
            </span>
          </div>
          <div class="mt-4 flex justify-end">
            <ElButton
              type="danger"
              plain
              :loading="isLoading"
              @click="endCollaboration"
            >
              {{ t('collab.end') }}
            </ElButton>
          </div>
        </div>

        <div
          v-else
          class="inactive-workshop"
        >
          <div class="duration-row mb-3 flex items-center gap-2">
            <span class="text-sm text-gray-600">{{ t('collab.sessionDuration') }}</span>
            <ElPopover
              placement="bottom"
              :width="280"
              trigger="click"
            >
              <template #reference>
                <ElButton
                  text
                  circle
                  size="small"
                  :aria-label="t('collab.durationAria')"
                >
                  <Settings class="w-4 h-4" />
                </ElButton>
              </template>
              <div class="p-2">
                <ElRadioGroup
                  v-model="sessionDurationPreset"
                  size="small"
                  class="flex flex-col gap-2"
                >
                  <ElRadioButton
                    v-for="opt in durationOptions"
                    :key="opt.value"
                    :label="opt.value"
                  >
                    {{ t(opt.labelKey) }}
                  </ElRadioButton>
                </ElRadioGroup>
              </div>
            </ElPopover>
          </div>
          <p class="description">
            {{ isNetworkMode ? t('collab.hintNetworkInactive') : t('collab.hintSchoolInactive') }}
          </p>
          <ElButton
            type="primary"
            :loading="isLoading"
            @click="handleGenerateCode"
          >
            {{ t('collab.start') }}
          </ElButton>
        </div>
      </div>
    </div>
  </ElDialog>
</template>

<style scoped>
.online-collab-modal {
  padding: 4px 0;
}

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

.collab-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.description {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin-bottom: 24px;
  line-height: 1.6;
  text-align: center;
}

.participants-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.inactive-workshop {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.share-container {
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
}

.code-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
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
}

.code-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
  margin: 0;
}
</style>
