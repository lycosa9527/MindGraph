<script setup lang="ts">
/**
 * Voice notes transcript modal — Swiss stone shell, pill actions.
 * Closing does not stop an active recording.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import { ArrowUpRight, Copy, Mic, Pause, Square } from '@lucide/vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useVoiceNotesStore } from '@/stores/voiceNotes'

const { t } = useLanguage()
const notify = useNotifications()
const voiceNotes = useVoiceNotesStore()
const {
  modalOpen,
  recording,
  paused,
  connecting,
  ingesting,
  stopping,
  bootstrapping,
  sessionStatus,
  transcriptText,
  elapsedMs,
  liveText,
  lines,
} = storeToRefs(voiceNotes)

const statusLabel = computed(() => {
  switch (sessionStatus.value) {
    case 'ingesting':
      return t('auth.voiceNotes.ingesting')
    case 'stopping':
      return t('auth.voiceNotes.stopping')
    case 'connecting':
      return t('auth.voiceNotes.connecting')
    case 'starting':
      return t('auth.voiceNotes.starting')
    case 'paused':
      return t('auth.voiceNotes.paused')
    case 'recording':
      return t('auth.voiceNotes.recording')
    default:
      return t('auth.voiceNotes.idle')
  }
})

const elapsedLabel = computed(() => {
  const totalSec = Math.floor(elapsedMs.value / 1000)
  const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
  const ss = String(totalSec % 60).padStart(2, '0')
  return `${mm}:${ss}`
})

const canStart = computed(
  () => !recording.value && !paused.value && !connecting.value && !stopping.value
)
const canPause = computed(() => recording.value && !paused.value && !stopping.value)
const canResume = computed(() => recording.value && paused.value && !stopping.value)
const canStop = computed(() => (recording.value || paused.value) && !stopping.value)
const canCopy = computed(() => Boolean(transcriptText.value.trim()))

function onClose(): void {
  voiceNotes.closeModal()
}

function onStart(): void {
  void voiceNotes.startRecording()
}

function onPause(): void {
  voiceNotes.pauseRecording()
}

function onResume(): void {
  voiceNotes.resumeRecording()
}

function onStop(): void {
  void voiceNotes.stopRecording()
}

function onJump(): void {
  void voiceNotes.jumpToMindmap()
}

async function onCopy(): Promise<void> {
  const text = transcriptText.value.trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    notify.success(t('auth.voiceNotes.copied'))
  } catch {
    notify.warning(t('auth.voiceNotes.genericError'))
  }
}
</script>

<template>
  <el-dialog
    :model-value="modalOpen"
    width="min(520px, 92vw)"
    append-to-body
    destroy-on-close
    align-center
    class="voice-notes-swiss"
    @close="onClose"
  >
    <template #header>
      <div class="vn-swiss__header">
        <span
          class="vn-swiss__glyph"
          aria-hidden="true"
          >◇</span
        >
        <span class="vn-swiss__title">{{ t('auth.voiceNotes.modalTitle') }}</span>
        <span
          class="vn-swiss__divider"
          aria-hidden="true"
        />
        <span class="vn-swiss__note">
          <span class="vn-swiss__status">{{ statusLabel }}</span>
          <span class="vn-swiss__elapsed">{{ elapsedLabel }}</span>
        </span>
      </div>
    </template>

    <div class="vn-swiss__stack">
      <div class="vn-swiss__kicker">
        <span>{{ t('auth.voiceNotes.viewTranscript') }}</span>
      </div>

      <div
        class="vn-swiss__body"
        role="log"
        aria-live="polite"
      >
        <p
          v-for="(line, index) in lines"
          :key="`${index}-${line.slice(0, 12)}`"
          class="vn-swiss__line"
        >
          {{ line }}
        </p>
        <p
          v-if="liveText.trim()"
          class="vn-swiss__line vn-swiss__line--live"
        >
          {{ liveText }}
        </p>
        <p
          v-if="!lines.length && !liveText.trim()"
          class="vn-swiss__empty"
        >
          {{ t('auth.voiceNotes.empty') }}
        </p>
      </div>
    </div>

    <template #footer>
      <div class="vn-swiss__footer">
        <div class="vn-swiss__footer-left">
          <button
            type="button"
            class="vn-pill vn-pill--ghost"
            :disabled="!canCopy"
            @click="onCopy"
          >
            <Copy
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.copy') }}
          </button>
          <button
            type="button"
            class="vn-pill vn-pill--ghost"
            :disabled="bootstrapping"
            @click="onJump"
          >
            <span>{{ t('auth.voiceNotes.jumpToMindmap') }}</span>
            <ArrowUpRight
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
          </button>
        </div>

        <div class="vn-swiss__footer-right">
          <button
            v-if="canStart"
            type="button"
            class="vn-pill vn-pill--solid"
            :disabled="connecting"
            @click="onStart"
          >
            <Mic
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.start') }}
          </button>
          <button
            v-if="canPause"
            type="button"
            class="vn-pill vn-pill--ghost"
            @click="onPause"
          >
            <Pause
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.pause') }}
          </button>
          <button
            v-if="canResume"
            type="button"
            class="vn-pill vn-pill--solid"
            @click="onResume"
          >
            <Mic
              class="vn-pill__icon"
              :size="14"
              :stroke-width="2"
            />
            {{ t('auth.voiceNotes.resume') }}
          </button>
          <button
            v-if="canStop"
            type="button"
            class="vn-pill vn-pill--danger"
            :disabled="ingesting"
            @click="onStop"
          >
            <Square
              class="vn-pill__icon"
              :size="12"
              :stroke-width="2.5"
            />
            {{ t('auth.voiceNotes.stop') }}
          </button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<style>
.voice-notes-swiss.el-dialog {
  --vn-ink: #1c1917;
  --vn-body: #44403c;
  --vn-muted: #78716c;
  --vn-subtle: #a8a29e;
  --vn-border: #e7e5e4;
  --vn-border-strong: #d6d3d1;
  --vn-surface: #ffffff;
  --vn-inset: #fafaf9;
  --vn-hover: #f5f5f4;
  --vn-danger: #b91c1c;

  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--vn-border);
  box-shadow:
    0 10px 15px -3px rgba(0, 0, 0, 0.08),
    0 4px 6px -4px rgba(0, 0, 0, 0.06);
}

.voice-notes-swiss .el-dialog__header {
  margin: 0;
  padding: 1rem 1.25rem 0.75rem;
}

.voice-notes-swiss .el-dialog__headerbtn {
  top: 1rem;
  right: 1rem;
}

.voice-notes-swiss .el-dialog__headerbtn .el-dialog__close {
  color: var(--vn-muted);
}

.voice-notes-swiss .el-dialog__headerbtn:hover .el-dialog__close {
  color: var(--vn-ink);
}

.voice-notes-swiss .el-dialog__body {
  padding: 0.25rem 1.25rem 1rem;
}

.voice-notes-swiss .el-dialog__footer {
  padding: 0.75rem 1.25rem 1.15rem;
  border-top: 1px solid var(--vn-border);
}
</style>

<style scoped>
.vn-swiss__header {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding-right: 1.75rem;
  min-width: 0;
}

.vn-swiss__glyph {
  color: var(--vn-muted, #78716c);
  font-size: 0.85rem;
  line-height: 1;
}

.vn-swiss__title {
  font-size: 1rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--vn-ink, #1c1917);
  white-space: nowrap;
}

.vn-swiss__divider {
  flex: 1;
  height: 1px;
  background: var(--vn-border, #e7e5e4);
  min-width: 0.75rem;
}

.vn-swiss__note {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 0.75rem;
  color: var(--vn-muted, #78716c);
  white-space: nowrap;
}

.vn-swiss__status {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.vn-swiss__elapsed {
  font-variant-numeric: tabular-nums;
  color: var(--vn-ink, #1c1917);
  font-weight: 650;
}

.vn-swiss__stack {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.vn-swiss__kicker {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--vn-muted, #78716c);
}

.vn-swiss__kicker::before {
  content: '';
  width: 0.35rem;
  height: 0.35rem;
  border-radius: 9999px;
  background: var(--vn-ink, #1c1917);
}

.vn-swiss__body {
  max-height: min(48vh, 26rem);
  min-height: 10rem;
  overflow-y: auto;
  padding: 0.9rem 1rem;
  border: 1px solid var(--vn-border, #e7e5e4);
  border-radius: 10px;
  background: var(--vn-inset, #fafaf9);
}

.vn-swiss__line {
  margin: 0 0 0.55rem;
  color: var(--vn-ink, #1c1917);
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.vn-swiss__line--live {
  color: var(--vn-muted, #78716c);
}

.vn-swiss__empty {
  margin: 0;
  color: var(--vn-subtle, #a8a29e);
  line-height: 1.55;
}

.vn-swiss__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.vn-swiss__footer-left,
.vn-swiss__footer-right {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.vn-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-height: 2.15rem;
  padding: 0 1rem;
  border-radius: 9999px;
  border: 1px solid var(--vn-ink, #1c1917);
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease,
    opacity 0.15s ease;
}

.vn-pill:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.vn-pill__icon {
  flex-shrink: 0;
}

.vn-pill--ghost {
  background: transparent;
  color: var(--vn-ink, #1c1917);
}

.vn-pill--ghost:hover:not(:disabled) {
  background: var(--vn-hover, #f5f5f4);
}

.vn-pill--solid {
  background: var(--vn-ink, #1c1917);
  color: var(--vn-surface, #ffffff);
}

.vn-pill--solid:hover:not(:disabled) {
  background: #292524;
  border-color: #292524;
}

.vn-pill--danger {
  background: transparent;
  color: var(--vn-danger, #b91c1c);
  border-color: var(--vn-danger, #b91c1c);
}

.vn-pill--danger:hover:not(:disabled) {
  background: #fef2f2;
}
</style>
