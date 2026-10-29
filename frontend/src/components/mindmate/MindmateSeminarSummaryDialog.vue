<script setup lang="ts">
/**
 * Pick a seminar slice, draft an editable minutes card, then send it or keep it.
 * Sending is a separate step: the room posts the card as 教研助手.
 */
import { computed, ref, watch } from 'vue'

import { ElDialog } from 'element-plus'

import { Check, Clock, List, SquareCheck, Star } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import type { SeminarHighlight } from '@/composables/mindmate/mindmateSeminarChrome'
import type { MindmateSeminarMessage } from '@/composables/mindmate/useMindmateSeminar'
import { useAuthStore } from '@/stores/auth'
import { consumeSseDataLines } from '@/utils/mindMateSseStream'
import { collabMessageRowKey } from '@/utils/mindmateSeminarDisplay'
import { mindmateDifyUserIdFromSession } from '@/utils/mindmateDifyUserId'
import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'
import {
  type SeminarSummaryCardModel,
  emptySeminarSummary,
  parseSeminarBriefCard,
  parseSeminarSummaryCard,
  seminarMinutesMessage,
  seminarSummaryHasContent,
} from '@/utils/mindmateSeminarCards'
import type { SeminarGroupMember } from '@/utils/mindmateSeminarGroup'
import {
  type MinutesSource,
  type SeminarMinutesScope,
  alignMinutesGoals,
  buildMinutesPrompt,
  clearMinutesDraft,
  fallbackMinutes,
  latestSummaryStamp,
  loadMinutesDraft,
  mentionedFileNames,
  minutesPeople,
  minutesTimeRange,
  parseMinutesDraft,
  saveMinutesDraft,
  selectMinutesSources,
} from '@/utils/mindmateSeminarMinutes'

import MindmateSeminarSummaryPreview from './MindmateSeminarSummaryPreview.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    messages: MindmateSeminarMessage[]
    preselectKeys?: string[]
    topic?: string
    goals?: string[]
    members?: SeminarGroupMember[]
    highlights?: SeminarHighlight[]
    sessionId?: string
  }>(),
  {
    preselectKeys: () => [],
    topic: '',
    goals: () => [],
    members: () => [],
    highlights: () => [],
    sessionId: '',
  }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'send', content: string): void
}>()

const { t, isZh } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()

const step = ref<'pick' | 'preview'>('pick')
const mode = ref<SeminarMinutesScope>('all')
const picked = ref<Record<string, boolean>>({})
const working = ref(false)
const errorText = ref('')
const draft = ref<SeminarSummaryCardModel | null>(null)
let abort: AbortController | null = null
let suppressSave = false

const sources = computed<MinutesSource[]>(() =>
  props.messages
    .map((message, index) => ({ message, index }))
    .filter(({ message }) => !message.streaming)
    .filter(({ message }) => !parseSeminarBriefCard(message.content))
    .filter(({ message }) => !parseSeminarSummaryCard(message.content))
    .map(({ message, index }) => {
      const content = message.content.trim()
      return {
        key: collabMessageRowKey(message, index),
        author:
          message.role === 'assistant'
            ? 'MindMate'
            : message.username?.trim() || t('mindmate.highlights.you'),
        preview: content.replace(/\s+/g, ' ').slice(0, 72),
        content,
        createdAt: message.created_at || '',
        messageId: message.id ?? null,
        senderId: message.sender_user_id ?? null,
        assistant: message.role === 'assistant',
      }
    })
    .filter((row) => row.content.length > 0)
)

const sinceCutoff = computed(() => latestSummaryStamp(props.messages))

const selected = computed(() =>
  selectMinutesSources(sources.value, mode.value, picked.value, props.highlights, sinceCutoff.value)
)

const scopeLabel = computed(() => {
  const n = selected.value.length
  if (mode.value === 'part') {
    return t('mindmate.summary.scopePartCount', { n })
  }
  if (mode.value === 'highlights') {
    return t('mindmate.summary.scopeHighlightsCount', { n })
  }
  if (mode.value === 'since') {
    return t('mindmate.summary.scopeSinceCount', { n })
  }
  return t('mindmate.summary.scopeAllCount', { n })
})

const scopeChoices: Array<{
  id: SeminarMinutesScope
  title: string
  hint: string
  tone: 'violet' | 'slate' | 'amber' | 'blue'
}> = [
  { id: 'all', title: 'mindmate.summary.all', hint: 'mindmate.summary.allHint', tone: 'violet' },
  {
    id: 'since',
    title: 'mindmate.summary.since',
    hint: 'mindmate.summary.sinceHint',
    tone: 'slate',
  },
  {
    id: 'highlights',
    title: 'mindmate.summary.highlights',
    hint: 'mindmate.summary.highlightsHint',
    tone: 'amber',
  },
  { id: 'part', title: 'mindmate.summary.part', hint: 'mindmate.summary.partHint', tone: 'blue' },
]

function roleLabel(role: SeminarBriefRole): string {
  return t(`mindmate.home.brief.role.${role}`)
}

watch(
  () => props.open,
  (open) => {
    if (!open) {
      abort?.abort()
      return
    }
    mode.value = props.preselectKeys.length > 0 ? 'part' : 'all'
    const next: Record<string, boolean> = {}
    for (const key of props.preselectKeys) {
      next[key] = true
    }
    picked.value = next
    errorText.value = ''
    working.value = false
    draft.value = props.preselectKeys.length > 0 ? null : loadMinutesDraft(props.sessionId)
    step.value = draft.value ? 'preview' : 'pick'
  }
)

function toggle(key: string): void {
  picked.value = { ...picked.value, [key]: !picked.value[key] }
}

function setMode(next: SeminarMinutesScope): void {
  mode.value = next
}

async function generate(): Promise<void> {
  if (working.value) {
    return
  }
  if (selected.value.length === 0) {
    errorText.value =
      mode.value === 'highlights'
        ? t('mindmate.summary.noHighlights')
        : mode.value === 'part'
          ? t('mindmate.summary.pick')
          : t('mindmate.summary.empty')
    return
  }
  const sessionUser = authStore.user
  if (!sessionUser?.id) {
    errorText.value = t('mindmate.summary.failed')
    return
  }
  const userId = mindmateDifyUserIdFromSession(
    authStore.mode,
    String(sessionUser.id),
    sessionUser.phone
  )
  errorText.value = ''
  working.value = true
  abort?.abort()
  abort = new AbortController()
  const people = minutesPeople(selected.value, props.members, roleLabel)
  const files = [...new Set(selected.value.flatMap((row) => mentionedFileNames(row.content)))]
  const quotes = props.highlights
    .filter((item) => {
      if (item.messageId && selected.value.some((row) => row.messageId === item.messageId)) {
        return true
      }
      return selected.value.some((row) => item.text && row.content.includes(item.text))
    })
    .map((item) => `${item.authorName}：${item.text}`)
    .slice(0, 3)
  const transcript = selected.value
    .map((row) => `${row.author}：${row.content}`)
    .join('\n\n')
    .slice(-12000)
  const base = emptySeminarSummary(scopeLabel.value)
  base.topic = props.topic.trim()
  base.timeRange = minutesTimeRange(
    selected.value.map((row) => row.createdAt),
    isZh.value
  )
  base.speakers = people.speakers
  base.observers = people.observers
  base.author = t('mindmate.summary.author')
  base.goals = props.goals.filter(Boolean).map((goal) => ({ goal, status: 'open' as const }))
  const message = buildMinutesPrompt({
    zh: isZh.value,
    topic: base.topic,
    goals: props.goals,
    speakers: people.speakers
      .map((row) => (row.role ? `${row.name}（${row.role}）` : row.name))
      .join('、'),
    observers: people.observers.join('、'),
    files,
    quotes,
    transcript,
  })
  let body = ''
  try {
    const response = await fetch('/api/ai_assistant/stream', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, user_id: userId }),
      signal: abort.signal,
    })
    if (!response.ok || !response.body) {
      throw new Error('summary_failed')
    }
    await consumeSseDataLines(
      response.body.getReader(),
      (payload) => {
        const event = payload.event
        const answer = typeof payload.answer === 'string' ? payload.answer : ''
        if (event === 'message' && answer) {
          body += answer
        } else if (event === 'message_replace' && answer) {
          body = answer
        } else if (event === 'error') {
          throw new Error('summary_failed')
        }
      },
      abort.signal
    )
    const parsed = parseMinutesDraft(body)
    if (!parsed) {
      draft.value = fallbackMinutes(body, base)
    } else {
      draft.value = {
        ...base,
        ...parsed,
        goals: alignMinutesGoals(props.goals, parsed.goals || []),
        scope: base.scope,
        topic: base.topic,
        timeRange: base.timeRange,
        speakers: base.speakers,
        observers: base.observers,
        author: base.author,
        structured: true,
        body: '',
      }
    }
    if (!draft.value || !seminarSummaryHasContent(draft.value)) {
      errorText.value = t('mindmate.summary.failed')
      return
    }
    step.value = 'preview'
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return
    }
    errorText.value = t('mindmate.summary.failed')
  } finally {
    working.value = false
  }
}

function onEdit(model: SeminarSummaryCardModel): void {
  draft.value = model
}

function keep(): void {
  if (draft.value && seminarSummaryHasContent(draft.value)) {
    saveMinutesDraft(props.sessionId, draft.value)
    notify.successKey('mindmate.summary.kept')
  }
  suppressSave = true
  emit('close')
}

function send(): void {
  const model = draft.value
  if (!model || !seminarSummaryHasContent(model)) {
    return
  }
  suppressSave = true
  clearMinutesDraft(props.sessionId)
  emit(
    'send',
    seminarMinutesMessage({ ...model, author: t('mindmate.summary.author'), structured: true })
  )
}

function closeDialog(): void {
  if (!suppressSave && draft.value && seminarSummaryHasContent(draft.value)) {
    saveMinutesDraft(props.sessionId, draft.value)
  }
  suppressSave = false
  emit('close')
}
</script>

<template>
  <ElDialog
    :model-value="open"
    :width="step === 'preview' ? 'min(560px, 94vw)' : 'min(440px, 94vw)'"
    align-center
    append-to-body
    class="mm-sum-dialog"
    :class="{ 'is-preview': step === 'preview' }"
    @close="closeDialog"
  >
    <template #header>
      <div class="mm-sum__head">
        <h2>
          <I18nText
            v-if="step === 'preview'"
            k="mindmate.summary.previewTitle"
          /><I18nText
            v-else
            k="mindmate.summary.title"
          />
        </h2>
        <p>
          <I18nText
            v-if="step === 'preview'"
            k="mindmate.summary.previewHint"
          /><I18nText
            v-else
            k="mindmate.summary.pickHint"
          />
        </p>
      </div>
    </template>

    <div
      v-if="step === 'pick'"
      class="mm-sum"
    >
      <div
        class="mm-sum__choices"
        role="radiogroup"
      >
        <button
          v-for="choice in scopeChoices"
          :key="choice.id"
          type="button"
          class="mm-sum__choice"
          :class="{ 'is-on': mode === choice.id }"
          @click="setMode(choice.id)"
        >
          <span
            class="mm-sum__glyph"
            :class="`is-${choice.tone}`"
          >
            <List
              v-if="choice.id === 'all'"
              :size="16"
            />
            <Clock
              v-else-if="choice.id === 'since'"
              :size="16"
            />
            <Star
              v-else-if="choice.id === 'highlights'"
              :size="16"
            />
            <SquareCheck
              v-else
              :size="16"
            />
          </span>
          <span class="mm-sum__choice-copy">
            <span class="mm-sum__choice-title"><I18nText :k="choice.title" /></span>
            <span class="mm-sum__choice-hint"><I18nText :k="choice.hint" /></span>
          </span>
          <span
            v-if="mode === choice.id"
            class="mm-sum__check"
          >
            <Check :size="14" />
          </span>
        </button>
      </div>

      <ul
        v-if="mode === 'part'"
        class="mm-sum__list"
      >
        <li
          v-for="row in sources"
          :key="row.key"
        >
          <label>
            <input
              type="checkbox"
              :checked="Boolean(picked[row.key])"
              @change="toggle(row.key)"
            />
            <span class="mm-sum__who">{{ row.author }}</span>
            <span class="mm-sum__preview">{{ row.preview }}</span>
          </label>
        </li>
        <li
          v-if="sources.length === 0"
          class="mm-sum__empty"
        >
          <I18nText k="mindmate.summary.empty" />
        </li>
      </ul>
      <p
        v-if="errorText"
        class="mm-sum__error"
      >
        {{ errorText }}
      </p>
    </div>

    <MindmateSeminarSummaryPreview
      v-else-if="draft"
      :model="draft"
      @update="onEdit"
    />

    <template #footer>
      <div
        v-if="step === 'pick'"
        class="mm-sum__foot"
      >
        <button
          type="button"
          class="mm-sum__ghost"
          @click="closeDialog"
        >
          <I18nText k="common.cancel" />
        </button>
        <button
          type="button"
          class="mm-sum__primary"
          :disabled="working"
          @click="generate"
        >
          <I18nText
            v-if="working"
            k="mindmate.summary.working"
          /><I18nText
            v-else
            k="mindmate.summary.generate"
          />
        </button>
      </div>
      <div
        v-else
        class="mm-sum__foot"
      >
        <button
          type="button"
          class="mm-sum__outline"
          @click="keep"
        >
          <I18nText k="mindmate.summary.keep" />
        </button>
        <button
          type="button"
          class="mm-sum__primary"
          @click="send"
        >
          <I18nText k="mindmate.summary.send" />
        </button>
      </div>
    </template>
  </ElDialog>
</template>

<style>
.mm-sum-dialog.el-dialog {
  border-radius: 20px;
  overflow: hidden;
}

.mm-sum-dialog .el-dialog__header {
  margin: 0;
  padding: 18px 20px 8px;
}

.mm-sum-dialog .el-dialog__body {
  padding: 8px 20px 4px;
}

.mm-sum-dialog.is-preview .el-dialog__body {
  max-height: min(72vh, 760px);
  padding: 4px 16px 8px;
  overflow: auto;
  background: #f7f6fb;
}

.mm-sum-dialog .el-dialog__footer {
  padding: 12px 20px 16px;
}
</style>

<style scoped>
.mm-sum__head h2 {
  margin: 0;
  color: #1c1917;
  font-size: 18px;
  font-weight: 700;
}

.mm-sum__head p {
  margin: 4px 0 0;
  color: #a8a29e;
  font-size: 13px;
}

.mm-sum__choices {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mm-sum__choice {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px;
  border: 1px solid #eceaf1;
  border-radius: 14px;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.mm-sum__choice.is-on {
  border-color: #7c6cf0;
  background: #f7f5ff;
}

.mm-sum__glyph {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: #f3f1fb;
  color: #6d5efc;
}

.mm-sum__glyph.is-amber {
  background: #fff4e5;
  color: #f59e0b;
}

.mm-sum__glyph.is-blue {
  background: #eef2ff;
  color: #6366f1;
}

.mm-sum__choice-copy {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}

.mm-sum__choice-title {
  color: #1c1917;
  font-size: 14px;
  font-weight: 650;
}

.mm-sum__choice-hint {
  color: #a8a29e;
  font-size: 12px;
}

.mm-sum__check {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  background: #6d5efc;
  color: #fff;
}

.mm-sum__list {
  max-height: 180px;
  margin: 12px 0 0;
  padding: 4px;
  overflow: auto;
  list-style: none;
  border: 1px solid #f0eeec;
  border-radius: 12px;
  background: #fff;
}

.mm-sum__list label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 8px;
  cursor: pointer;
}

.mm-sum__who {
  flex: 0 0 auto;
  color: #6d5efc;
  font-size: 12px;
  font-weight: 650;
}

.mm-sum__preview {
  min-width: 0;
  overflow: hidden;
  color: #44403c;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-sum__empty,
.mm-sum__error {
  margin: 8px 0 0;
  color: #a8a29e;
  font-size: 13px;
}

.mm-sum__error {
  color: #b91c1c;
}

.mm-sum__foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.mm-sum__ghost,
.mm-sum__outline,
.mm-sum__primary {
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 14px;
  cursor: pointer;
}

.mm-sum__outline {
  border: 1px solid #e4e4e7;
  background: #fff;
  color: #3f3f46;
}

.mm-sum__ghost {
  border: none;
  background: #f4f4f5;
  color: #3f3f46;
}

.mm-sum__primary {
  border: none;
  background: #6d5efc;
  color: #fff;
}

.mm-sum__primary:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
