<script setup lang="ts">
/**
 * Slide voiceover: edit the line, set the speed, then generate Cherry's reading.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { Check, Mic, Sparkles, X } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables'
import { useNotifications } from '@/composables/core/useNotifications'
import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  open: boolean
  line: string
  rate: number
  voiceUrl: string
  courseId: string
}>()

const emit = defineEmits<{
  close: []
  apply: [value: { line: string; rate: number; asset: { id: string; url: string } | null }]
}>()

const { t } = useLanguage()
const notify = useNotifications()
const visible = computed({
  get: () => props.open,
  set: (value: boolean) => {
    if (!value) emit('close')
  },
})
const draft = ref('')
const speed = ref(1)
const busy = ref(false)
const saving = ref(false)
const preview = ref('')
const pending = ref<Blob | null>(null)
let ownedUrl = ''

function revoke(): void {
  if (!ownedUrl) return
  URL.revokeObjectURL(ownedUrl)
  ownedUrl = ''
}

function reset(): void {
  draft.value = props.line
  speed.value = props.rate
  pending.value = null
  revoke()
  preview.value = props.voiceUrl
}

watch(
  () => props.open,
  (on) => {
    if (on) reset()
  }
)

function onDraft(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLTextAreaElement)) return
  draft.value = target.value
  pending.value = null
  revoke()
  preview.value = props.voiceUrl
}

function onSpeed(event: Event): void {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) return
  speed.value = Number(target.value)
  pending.value = null
  revoke()
  preview.value = props.voiceUrl
}

async function generate(): Promise<void> {
  const text = draft.value.trim()
  if (!text || busy.value) return
  busy.value = true
  try {
    const response = await apiRequest('/api/training/voiceover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, rate: speed.value }),
    })
    if (!response.ok) throw new Error('tts')
    const blob = await response.blob()
    pending.value = blob
    revoke()
    ownedUrl = URL.createObjectURL(blob)
    preview.value = ownedUrl
  } catch {
    notify.errorKey('training.builder.glassVoiceFailed')
  } finally {
    busy.value = false
  }
}

async function apply(): Promise<void> {
  if (saving.value) return
  saving.value = true
  try {
    let asset: { id: string; url: string } | null = null
    if (pending.value) {
      const file = new File([pending.value], 'voiceover.mp3', { type: 'audio/mpeg' })
      asset = await uploadTrainingFile(props.courseId, 'voice', file)
    }
    emit('apply', { line: draft.value.trim(), rate: speed.value, asset })
    emit('close')
  } catch {
    notify.errorKey('training.builder.uploadFailed')
  } finally {
    saving.value = false
  }
}

onUnmounted(revoke)
</script>

<template>
  <SwissGlassDialog
    v-model="visible"
    :ribbon="t('training.builder.ribbonGlass')"
    ribbon-key="training.builder.ribbonGlass"
    :title="t('training.builder.glassVoiceover')"
    title-key="training.builder.glassVoiceover"
    :line1="t('training.builder.glassVoiceName')"
    line1-key="training.builder.glassVoiceName"
    :icon="Mic"
    width="min(440px, 92vw)"
  >
    <div class="swiss-glass-stack">
      <label class="swiss-glass-field">
        <span class="swiss-glass-field__kicker">
          <I18nText k="training.builder.glassLine" />
        </span>
        <textarea
          class="swiss-glass-field__input"
          maxlength="400"
          rows="4"
          :value="draft"
          @input="onDraft"
        />
      </label>
      <label class="swiss-glass-field">
        <span class="swiss-glass-field__kicker">
          <I18nText k="training.builder.glassSpeed" />
          {{ speed.toFixed(1) }}
        </span>
        <input
          class="voice-modal__range"
          type="range"
          min="0.7"
          max="1.4"
          step="0.1"
          :value="speed"
          @input="onSpeed"
        />
      </label>
      <div class="voice-modal__row">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
          :disabled="busy || !draft.trim() || !courseId"
          @click="generate"
        >
          <Sparkles
            :size="15"
            aria-hidden="true"
          />
          <I18nText k="training.builder.glassGenerate" />
        </button>
        <audio
          v-if="preview"
          class="voice-modal__play"
          :src="preview"
          controls
          preload="none"
        />
      </div>
      <p
        v-if="!courseId"
        class="swiss-glass-error"
      >
        <I18nText k="training.builder.glassNeedSave" />
      </p>
    </div>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="emit('close')"
        >
          <X
            :size="15"
            aria-hidden="true"
          />
          <I18nText k="common.cancel" />
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="saving || !courseId"
          @click="apply"
        >
          <Check
            :size="15"
            aria-hidden="true"
          />
          <I18nText k="training.builder.glassDone" />
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.voice-modal__range {
  width: 100%;
  accent-color: #1c1917;
}
.voice-modal__row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.voice-modal__play {
  width: 12rem;
  height: 2rem;
}
</style>
