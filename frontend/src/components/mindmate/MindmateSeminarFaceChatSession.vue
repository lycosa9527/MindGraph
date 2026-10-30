<script setup lang="ts">
/**
 * In-seminar face-to-face recorder. Uses the mobile voice-notes sheet,
 * writes the transcript to seminar COS while the mic is open, then
 * drafts a minutes card the room can post.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ElDialog } from 'element-plus'

import MindmateSeminarSummaryPreview from '@/components/mindmate/MindmateSeminarSummaryPreview.vue'
import MobileVoiceNotesSheet, {
  type VoiceNotesSheetSession,
} from '@/components/voiceNotes/MobileVoiceNotesSheet.vue'
import { useLanguage, useNotifications } from '@/composables'
import { upsertSeminarServerArtifact } from '@/composables/mindmate/mindmateSeminarChrome'
import { draftFaceChatSummary } from '@/composables/mindmate/seminarFaceChatSummary'
import { confirmHideVoiceNotesWhileRecording } from '@/composables/voiceNotes/confirmVoiceNotesModalClose'
import { useAuthStore } from '@/stores/auth'
import { useVoiceNotesStore } from '@/stores/voiceNotes'
import { mindmateDifyUserIdFromSession } from '@/utils/mindmateDifyUserId'
import {
  type SeminarSummaryCardModel,
  seminarMinutesMessage,
  seminarSummaryPlainText,
} from '@/utils/mindmateSeminarCards'
import {
  claimSeminarFaceChat,
  releaseSeminarFaceChat,
  saveSeminarFaceChat,
} from '@/utils/mindmateSeminarFolder'
import { composeFaceChatDocument, faceChatFilename } from '@/utils/seminarFaceChatDocument'

const props = withDefaults(
  defineProps<{
    open: boolean
    sessionId?: string
    topic?: string
    goals?: string[]
  }>(),
  {
    sessionId: '',
    topic: '',
    goals: () => [],
  }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'send', content: string): void
}>()

const { t, isZh } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const voiceNotes = useVoiceNotesStore()

const step = ref<'record' | 'preview'>('record')
const generating = ref(false)
const filename = ref('')
const fileId = ref('')
const startedAt = ref('')
const draft = ref<SeminarSummaryCardModel | null>(null)
const closed = ref(false)
let abort: AbortController | null = null
let sessionTicket = 0
let recorderToken = ''
let beatTimer: number | null = null

const persisting = computed(() => voiceNotes.ingesting)
const busy = computed(() => generating.value || voiceNotes.ingesting || voiceNotes.stopping)

const sheetSession: VoiceNotesSheetSession = {
  busy,
  generating,
  persisting,
  voiceNotes,
  stopRecordingOnly: () => voiceNotes.stopRecording('user'),
  generateMindmap: () => generateSummary(),
}

function speakerNames(): string[] {
  const seen = new Set<string>()
  const names: string[] = []
  for (const turn of voiceNotes.turns) {
    if (!turn.text.trim()) continue
    const label = voiceNotes
      .labelForSpeakerId(turn.speakerId)
      .replace(/[：:]\s*$/, '')
      .trim()
    if (!label || seen.has(label)) continue
    seen.add(label)
    names.push(label)
  }
  return names
}

function stopBeat(): void {
  if (beatTimer === null) return
  window.clearInterval(beatTimer)
  beatTimer = null
}

function startBeat(): void {
  stopBeat()
  beatTimer = window.setInterval(() => {
    const sessionId = props.sessionId
    if (!sessionId || !recorderToken) return
    void claimSeminarFaceChat(sessionId, recorderToken, true).catch(() => {
      /* the next beat retries */
    })
  }, 25_000)
}

async function dropHold(): Promise<void> {
  stopBeat()
  const token = recorderToken
  const sessionId = props.sessionId
  recorderToken = ''
  if (!token || !sessionId) return
  try {
    await releaseSeminarFaceChat(sessionId, token)
  } catch {
    /* the lock expires on its own */
  }
}

async function sink(markdown: string): Promise<void> {
  const sessionId = props.sessionId
  if (!sessionId) {
    throw new Error(t('mindmate.faceChat.saveFailed'))
  }
  try {
    const saved = await saveSeminarFaceChat(sessionId, {
      content: markdown,
      filename: filename.value,
      fileId: fileId.value,
      token: recorderToken,
    })
    fileId.value = saved.id
    upsertSeminarServerArtifact(saved)
  } catch {
    throw new Error(t('mindmate.faceChat.saveFailed'))
  }
}

async function persistSummary(model: SeminarSummaryCardModel): Promise<boolean> {
  const sessionId = props.sessionId
  if (!sessionId) return false
  const content = composeFaceChatDocument({
    transcript: voiceNotes.transcriptText,
    summary: seminarSummaryPlainText(model),
    summaryHeading: t('mindmate.faceChat.summaryTitle'),
    notesHeading: t('mindmate.faceChat.notesTitle'),
  })
  if (!content.trim()) return false
  try {
    const saved = await saveSeminarFaceChat(sessionId, {
      content,
      filename: filename.value,
      fileId: fileId.value,
      token: recorderToken,
    })
    fileId.value = saved.id
    upsertSeminarServerArtifact(saved)
    return true
  } catch {
    notify.warningKey('mindmate.faceChat.saveFailed')
    return false
  }
}

async function begin(): Promise<void> {
  const mine = ++sessionTicket
  const sessionId = props.sessionId
  if (!sessionId) {
    notify.warningKey('mindmate.collabNotConnected')
    emit('close')
    return
  }
  if (voiceNotes.hasActiveCapture) {
    notify.warningKey('auth.voiceNotes.sessionBusy')
    emit('close')
    return
  }
  const token = crypto.randomUUID()
  try {
    await claimSeminarFaceChat(sessionId, token)
  } catch (error) {
    const busy = error instanceof Error && error.message.includes('face_chat_busy')
    notify.warningKey(busy ? 'mindmate.faceChat.busy' : 'mindmate.faceChat.saveFailed')
    emit('close')
    return
  }
  if (mine !== sessionTicket) {
    try {
      await releaseSeminarFaceChat(sessionId, token)
    } catch {
      /* the lock expires on its own */
    }
    return
  }
  recorderToken = token
  if (voiceNotes.enabled) {
    await voiceNotes.exit()
  }
  if (mine !== sessionTicket) {
    await dropHold()
    return
  }
  step.value = 'record'
  draft.value = null
  fileId.value = ''
  startedAt.value = new Date().toISOString()
  filename.value = faceChatFilename(new Date(), t('mindmate.faceChat.notesTitle'))
  voiceNotes.setTranscriptSink(sink)
  await voiceNotes.enableAndOpen()
  const stillMine = mine === sessionTicket && !closed.value
  if (!stillMine || !voiceNotes.enabled) {
    voiceNotes.setTranscriptSink(null)
    await dropHold()
    if (stillMine) emit('close')
    return
  }
  startBeat()
  await voiceNotes.startRecording()
  if (mine !== sessionTicket || closed.value) {
    if (voiceNotes.enabled) await voiceNotes.exit()
    await dropHold()
  }
}

async function generateSummary(): Promise<void> {
  if (generating.value) return
  const transcript = voiceNotes.transcriptText.trim()
  if (!transcript) {
    notify.warningKey('mindmate.faceChat.empty')
    return
  }
  const sessionUser = authStore.user
  if (!sessionUser?.id) {
    notify.warningKey('mindmate.summary.failed')
    return
  }
  generating.value = true
  abort?.abort()
  abort = new AbortController()
  try {
    if (voiceNotes.hasActiveCapture) {
      await voiceNotes.stopRecording('user')
    }
    await voiceNotes.flushTranscriptIfEdited()
    const model = await draftFaceChatSummary({
      transcript: voiceNotes.transcriptText,
      topic: props.topic,
      goals: props.goals,
      speakers: speakerNames(),
      scope: t('mindmate.faceChat.scope'),
      author: t('mindmate.summary.author'),
      zh: isZh.value,
      userId: mindmateDifyUserIdFromSession(
        authStore.mode,
        String(sessionUser.id),
        sessionUser.phone
      ),
      startedAt: startedAt.value,
      signal: abort.signal,
    })
    if (!model) {
      notify.warningKey('mindmate.summary.failed')
      return
    }
    const saved = await persistSummary(model)
    if (!saved) return
    draft.value = model
    step.value = 'preview'
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') return
    notify.warningKey('mindmate.summary.failed')
  } finally {
    generating.value = false
  }
}

async function shutdown(): Promise<void> {
  if (closed.value) return
  closed.value = true
  sessionTicket += 1
  abort?.abort()
  const owned = recorderToken !== ''
  try {
    if (owned && voiceNotes.enabled) {
      if (step.value === 'record' && !voiceNotes.hasActiveCapture) {
        await voiceNotes.flushTranscriptIfEdited()
      }
      await voiceNotes.exit()
    }
  } finally {
    await dropHold()
  }
}

async function finish(send: boolean): Promise<void> {
  const model = draft.value
  if (model) {
    const saved = await persistSummary(model)
    if (!saved) return
    if (send) {
      emit(
        'send',
        seminarMinutesMessage({
          ...model,
          author: t('mindmate.summary.author'),
          structured: true,
        })
      )
    }
  }
  await shutdown()
  emit('close')
}

function onBeforeClose(done: () => void): void {
  void (async () => {
    if (closed.value) {
      done()
      return
    }
    if (voiceNotes.hasActiveCapture) {
      const ok = await confirmHideVoiceNotesWhileRecording((key) => t(key))
      if (!ok) return
    }
    if (step.value === 'preview' && draft.value) {
      const saved = await persistSummary(draft.value)
      if (!saved) return
    }
    await shutdown()
    done()
    emit('close')
  })()
}

function onEdit(model: SeminarSummaryCardModel): void {
  draft.value = model
}

watch(
  () => props.open,
  (isOpen, wasOpen) => {
    if (isOpen && !wasOpen) {
      closed.value = false
      void begin()
    } else if (!isOpen && wasOpen) {
      void shutdown()
    }
  }
)

onBeforeUnmount(() => {
  void shutdown()
})
</script>

<template>
  <ElDialog
    :model-value="open"
    width="min(480px, 96vw)"
    align-center
    append-to-body
    class="mm-face-session-dialog mm-seminar-swiss"
    :class="{ 'is-preview': step === 'preview' }"
    :before-close="onBeforeClose"
    :close-on-click-modal="false"
  >
    <template #header>
      <h2 class="mm-face-session__title">
        <I18nText k="mindmate.faceChat.title" />
      </h2>
    </template>
    <div
      v-if="step === 'record'"
      class="mm-face-session"
    >
      <MobileVoiceNotesSheet
        :session="sheetSession"
        generate-label-key="mindmate.faceChat.generate"
      />
    </div>
    <MindmateSeminarSummaryPreview
      v-else-if="draft"
      :model="draft"
      @update="onEdit"
    />
    <template
      v-if="step === 'preview'"
      #footer
    >
      <div class="mm-face-session__foot">
        <button
          type="button"
          class="mm-face-session__outline"
          @click="finish(false)"
        >
          <I18nText k="mindmate.summary.keep" />
        </button>
        <button
          type="button"
          class="mm-face-session__primary"
          @click="finish(true)"
        >
          <I18nText k="mindmate.summary.send" />
        </button>
      </div>
    </template>
  </ElDialog>
</template>

<style>
.mm-face-session-dialog.el-dialog {
  display: flex;
  flex-direction: column;
  height: min(760px, 92vh);
  border-radius: 12px;
  overflow: hidden;
  padding: 0;
}

.mm-face-session-dialog.is-preview.el-dialog {
  height: auto;
  max-height: 92vh;
}

.mm-face-session-dialog .el-dialog__header {
  margin: 0;
  padding: 16px 20px 8px;
}

.mm-face-session-dialog .el-dialog__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.mm-face-session-dialog.is-preview .el-dialog__body {
  overflow: auto;
  padding: 4px 16px 8px;
  background: #fafaf9;
}

.mm-face-session-dialog .el-dialog__footer {
  padding: 8px 16px 16px;
}

.mm-face-session {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.mm-face-session__title {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
  color: #1c1917;
}

.mm-face-session__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.mm-face-session__outline,
.mm-face-session__primary {
  min-height: 36px;
  padding: 8px 16px;
  border-radius: 9999px;
  font-size: 14px;
  cursor: pointer;
}

.mm-face-session__outline {
  border: 1px solid #d6d3d1;
  background: #fff;
  color: #1c1917;
}

.mm-face-session__primary {
  border: 1px solid #1c1917;
  background: #1c1917;
  color: #fafaf9;
}
</style>
