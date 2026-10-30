<script setup lang="ts">
/**
 * Compact minutes card posted by 教研助手.
 * Progress and tasks stay on the card; the full preview opens on demand.
 */
import { computed, ref } from 'vue'

import { ElDialog } from 'element-plus'

import { ArrowRight, Clock, Download, User } from '@lucide/vue'

import MindmateSeminarSummaryPreview from '@/components/mindmate/MindmateSeminarSummaryPreview.vue'
import { useLanguage } from '@/composables'
import { deliverExportFile } from '@/utils/deliverExportFile'
import {
  type SeminarMinutesGoalStatus,
  type SeminarSummaryCardModel,
} from '@/utils/mindmateSeminarCards'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const props = defineProps<{
  model: SeminarSummaryCardModel
}>()

const { t } = useLanguage()
const detailOpen = ref(false)

const topic = computed(() => props.model.topic.trim() || t('mindmate.summary.cardKicker'))

const people = computed(() => props.model.speakers.filter((row) => row.name.trim()))

const visiblePeople = computed(() => people.value.slice(0, 4))

const host = computed(() => {
  const rank = (role: string): number => {
    if (/组长|組長|主持|Lead/i.test(role)) {
      return 0
    }
    if (/主备人|主備人/.test(role)) {
      return 1
    }
    return 2
  }
  return people.value.find((row) => rank(row.role) < 2) ?? null
})

const overall = computed<'done' | 'active' | 'pending'>(() => {
  const goals = props.model.goals
  if (!goals.length || goals.every((row) => row.status === 'met')) {
    return 'done'
  }
  if (goals.every((row) => row.status === 'open')) {
    return 'pending'
  }
  return 'active'
})

const overallLabel = computed(() => {
  if (overall.value === 'active') {
    return t('mindmate.summary.cardActive')
  }
  if (overall.value === 'pending') {
    return t('mindmate.summary.cardPending')
  }
  return t('mindmate.summary.cardDone')
})

const progress = computed(() => props.model.goals.slice(0, 3))

const tasks = computed(() =>
  props.model.tasks
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 3)
)

const fallbackLines = computed(() => {
  if (progress.value.length || tasks.value.length || !props.model.body.trim()) {
    return []
  }
  return props.model.body
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 3)
})

function statusKey(status: SeminarMinutesGoalStatus): string {
  if (status === 'partial') {
    return 'mindmate.summary.cardActive'
  }
  if (status === 'open') {
    return 'mindmate.summary.cardPending'
  }
  return 'mindmate.summary.cardDone'
}

function taskParts(line: string): { lead: string; rest: string } {
  const match = line.match(/^(.{1,12})[:：]\s*(.+)$/)
  if (!match) {
    return { lead: '', rest: line }
  }
  return { lead: match[1], rest: match[2] }
}

function faceStyle(name: string): { background: string; color: string } {
  return seminarAvatarTone(name)
}

function goalStatusLabel(status: SeminarMinutesGoalStatus): string {
  if (status === 'met') {
    return t('mindmate.summary.status.met')
  }
  if (status === 'partial') {
    return t('mindmate.summary.status.partial')
  }
  return t('mindmate.summary.status.open')
}

function block(heading: string, lines: string[]): string {
  const rows = lines.map((line) => line.trim()).filter(Boolean)
  if (!rows.length) {
    return ''
  }
  return [heading, ...rows].join('\n')
}

function exportBody(): string {
  const model = props.model
  const speakers = model.speakers
    .map((row) => (row.role ? `${row.name}（${row.role}）` : row.name))
    .join('、')
  return [
    topic.value,
    model.scope,
    model.timeRange ? `${t('mindmate.summary.covered')} ${model.timeRange}` : '',
    speakers ? `${t('mindmate.summary.speakers')} ${speakers}` : '',
    model.observers.length
      ? `${t('mindmate.summary.observers')} ${model.observers.join('、')}`
      : '',
    block(
      t('mindmate.summary.section.goals'),
      model.goals.map((row) => `${goalStatusLabel(row.status)} ${row.goal}`)
    ),
    block(t('mindmate.summary.section.consensus'), model.consensus),
    block(t('mindmate.summary.section.open'), model.open),
    block(t('mindmate.summary.section.materials'), model.materials),
    block(t('mindmate.summary.section.tasks'), model.tasks),
    block(t('mindmate.summary.section.quotes'), model.quotes),
    model.structured ? '' : model.body.trim(),
  ]
    .filter(Boolean)
    .join('\n\n')
}

async function exportMinutes(): Promise<void> {
  const filename = `${topic.value}.txt`.replace(/[\\/:*?"<>|]/g, ' ')
  const blob = new Blob([`\uFEFF${exportBody()}`], { type: 'text/plain;charset=utf-8' })
  await deliverExportFile(blob, filename)
}
</script>

<template>
  <article class="mm-sum-card">
    <div class="mm-sum-card__pills">
      <span class="mm-sum-card__kind"><I18nText k="mindmate.summary.kind" /></span>
      <span
        class="mm-sum-card__state"
        :class="`is-${overall}`"
        >{{ overallLabel }}</span
      >
    </div>
    <h3 class="mm-sum-card__topic">{{ topic }}</h3>
    <p
      v-if="model.timeRange || host"
      class="mm-sum-card__meta"
    >
      <span v-if="model.timeRange">
        <Clock
          :size="14"
          aria-hidden="true"
        />
        {{ model.timeRange }}
      </span>
      <span v-if="host">
        <User
          :size="14"
          aria-hidden="true"
        />
        <I18nText k="mindmate.summary.host" /> {{ host.name }}
      </span>
    </p>
    <div
      v-if="people.length"
      class="mm-sum-card__people"
    >
      <span class="mm-sum-card__faces">
        <i
          v-for="person in visiblePeople"
          :key="person.name"
          :style="faceStyle(person.name)"
          >{{ seminarAvatarSurname(person.name) }}</i
        >
      </span>
      <span
        ><I18nText
          k="mindmate.summary.peopleCount"
          :params="{ n: people.length }"
      /></span>
    </div>

    <section
      v-if="progress.length"
      class="mm-sum-card__block"
    >
      <h4><I18nText k="mindmate.summary.progress" /></h4>
      <ul>
        <li
          v-for="(row, index) in progress"
          :key="`${row.goal}-${index}`"
        >
          <em :class="`is-${row.status}`"><I18nText :k="statusKey(row.status)" /></em>
          <span>{{ row.goal }}</span>
        </li>
      </ul>
    </section>
    <section
      v-else-if="fallbackLines.length"
      class="mm-sum-card__block"
    >
      <h4><I18nText k="mindmate.summary.progress" /></h4>
      <ul>
        <li
          v-for="(line, index) in fallbackLines"
          :key="index"
        >
          <span>{{ line }}</span>
        </li>
      </ul>
    </section>

    <section
      v-if="tasks.length"
      class="mm-sum-card__block"
    >
      <h4><I18nText k="mindmate.summary.section.tasks" /></h4>
      <ul class="is-tasks">
        <li
          v-for="(line, index) in tasks"
          :key="index"
        >
          <strong v-if="taskParts(line).lead">{{ taskParts(line).lead }}</strong>
          <span>{{ taskParts(line).lead ? `：${taskParts(line).rest}` : line }}</span>
        </li>
      </ul>
    </section>

    <footer class="mm-sum-card__foot">
      <button
        type="button"
        class="mm-sum-card__primary"
        @click="detailOpen = true"
      >
        <I18nText k="mindmate.summary.viewDetail" />
        <ArrowRight
          :size="14"
          aria-hidden="true"
        />
      </button>
    </footer>

    <ElDialog
      v-model="detailOpen"
      width="min(560px, 94vw)"
      align-center
      append-to-body
      class="mm-sum-detail mm-seminar-swiss"
    >
      <template #header>
        <div class="mm-sum-card__dialog-head">
          <h2 class="mm-sum-card__dialog-title">
            <I18nText k="mindmate.summary.previewTitle" />
          </h2>
          <button
            type="button"
            class="mm-sum-card__export"
            @click="exportMinutes"
          >
            <Download
              :size="14"
              aria-hidden="true"
            />
            <I18nText k="mindmate.summary.export" />
          </button>
        </div>
      </template>
      <MindmateSeminarSummaryPreview
        :model="model"
        readonly
      />
    </ElDialog>
  </article>
</template>

<style>
.mm-sum-detail.el-dialog {
  border-radius: 12px;
  overflow: hidden;
}

.mm-sum-detail .el-dialog__body {
  max-height: min(72vh, 760px);
  padding: 0 16px 16px;
  overflow: auto;
  background: #fafaf9;
}
</style>

<style scoped>
.mm-sum-card {
  width: 100%;
  box-sizing: border-box;
  padding: 14px 14px 12px;
  border: 1px solid #efedf3;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(28, 25, 23, 0.05);
}

.mm-sum-card__pills {
  display: flex;
  gap: 6px;
}

.mm-sum-card__kind,
.mm-sum-card__state,
.mm-sum-card__block em {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-style: normal;
  font-size: 12px;
  line-height: 1;
}

.mm-sum-card__kind {
  background: #f5f5f4;
  color: #44403c;
}

.mm-sum-card__state.is-done,
.mm-sum-card__block em.is-met {
  background: #ecfdf3;
  color: #15803d;
}

.mm-sum-card__state.is-active,
.mm-sum-card__block em.is-partial {
  background: #eef2ff;
  color: #4338ca;
}

.mm-sum-card__state.is-pending,
.mm-sum-card__block em.is-open {
  background: #f4f4f5;
  color: #71717a;
}

.mm-sum-card__topic {
  margin: 10px 0 0;
  color: #1c1917;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.45;
}

.mm-sum-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin: 8px 0 0;
  color: #78716c;
  font-size: 12px;
}

.mm-sum-card__meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.mm-sum-card__people {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: 12px;
  background: #f6f5f8;
  color: #57534e;
  font-size: 13px;
}

.mm-sum-card__faces {
  display: flex;
  align-items: center;
}

.mm-sum-card__faces i {
  display: grid;
  width: 26px;
  height: 26px;
  margin-left: -8px;
  place-items: center;
  border: 2px solid #fff;
  border-radius: 999px;
  font-style: normal;
  font-size: 12px;
  font-weight: 650;
}

.mm-sum-card__faces i:first-child {
  margin-left: 0;
}

.mm-sum-card__block {
  margin-top: 14px;
}

.mm-sum-card__block h4 {
  margin: 0 0 8px;
  color: #1c1917;
  font-size: 14px;
  font-weight: 700;
}

.mm-sum-card__block ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.mm-sum-card__block li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 8px;
  color: #44403c;
  font-size: 13px;
  line-height: 1.5;
}

.mm-sum-card__block em {
  flex: 0 0 auto;
  height: 20px;
  margin-top: 1px;
}

.mm-sum-card__block .is-tasks {
  padding-left: 1rem;
  list-style: disc;
}

.mm-sum-card__block .is-tasks li {
  display: list-item;
}

.mm-sum-card__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #f1f0f4;
}

.mm-sum-card__primary {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 34px;
  padding: 6px 14px;
  border: 1px solid #1c1917;
  border-radius: 9999px;
  background: #1c1917;
  color: #fafaf9;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.mm-sum-card__primary:hover {
  background: #292524;
  border-color: #292524;
}

.mm-sum-card__dialog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding-right: 28px;
}

.mm-sum-card__dialog-title {
  margin: 0;
  color: #1c1917;
  font-size: 18px;
  font-weight: 700;
}

.mm-sum-card__export {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 6px 12px;
  border: 1px solid #1c1917;
  border-radius: 9999px;
  background: #1c1917;
  color: #fafaf9;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.mm-sum-card__export:hover {
  background: #292524;
  border-color: #292524;
}
</style>
