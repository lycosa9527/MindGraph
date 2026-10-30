<script setup lang="ts">
/**
 * Editable minutes preview. Each section stays readable until its edit button is used.
 */
import { computed, ref } from 'vue'

import { FileText, Image as ImageIcon, Pencil } from '@lucide/vue'

import { useLanguage } from '@/composables'
import {
  type SeminarMinutesGoalStatus,
  type SeminarSummaryCardModel,
} from '@/utils/mindmateSeminarCards'

const props = defineProps<{
  model: SeminarSummaryCardModel
  readonly?: boolean
}>()

const emit = defineEmits<{
  (e: 'update', model: SeminarSummaryCardModel): void
}>()

const { t } = useLanguage()
const editing = ref<string | null>(null)

const docTitle = computed(() => {
  const topic = props.model.topic.trim()
  if (!topic) {
    return t('mindmate.summary.cardKicker')
  }
  if (topic.includes('《')) {
    return topic.endsWith('纪要') ? topic : `${topic}纪要`
  }
  return `《${topic}》纪要`
})

const hostLine = computed(() => {
  const speakers = props.model.speakers
  const host =
    speakers.find((person) => /组长|組長|主持|Lead/i.test(person.role)) ??
    speakers.find((person) => /主备人|主備人/.test(person.role))
  if (!host) {
    return ''
  }
  return host.role ? `${host.name}（${host.role}）` : host.name
})

const speakerLine = computed(() =>
  props.model.speakers
    .filter((person) => !hostLine.value.startsWith(person.name))
    .map((person) => (person.role ? `${person.name}（${person.role}）` : person.name))
    .join('、')
)

const observerText = computed(() => {
  const role = t('mindmate.home.brief.role.observer')
  return props.model.observers.map((name) => `${name}（${role}）`).join('、')
})

function patch(partial: Partial<SeminarSummaryCardModel>): void {
  emit('update', { ...props.model, ...partial, structured: true })
}

function onLines(
  key: 'consensus' | 'open' | 'materials' | 'tasks' | 'quotes',
  value: string
): void {
  const items = value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  const capped = key === 'quotes' ? items.slice(0, 3) : items
  patch({ [key]: capped })
}

function onGoalText(index: number, value: string): void {
  const goals = props.model.goals.map((row, rowIndex) =>
    rowIndex === index ? { ...row, goal: value } : row
  )
  patch({ goals: goals.filter((row) => row.goal.trim()) })
}

function onGoalStatus(index: number, status: SeminarMinutesGoalStatus): void {
  const goals = props.model.goals.map((row, rowIndex) =>
    rowIndex === index ? { ...row, status } : row
  )
  patch({ goals })
}

function toggleEdit(key: string): void {
  editing.value = editing.value === key ? null : key
}

function quoteParts(line: string): { text: string; by: string } {
  const match = line.match(/^(.{1,16})[:：]\s*(.+)$/)
  if (!match) {
    return { text: line, by: '' }
  }
  return { text: match[2], by: match[1] }
}

function taskLead(line: string): { lead: string; rest: string } {
  const match = line.match(/^(\S{1,8})\s+(.+)$/)
  if (!match) {
    return { lead: '', rest: line }
  }
  return { lead: match[1], rest: match[2] }
}

function materialKind(line: string): 'image' | 'file' {
  return /\.(png|jpe?g|gif|webp|svg)\b/i.test(line) ? 'image' : 'file'
}

function statusLabel(status: SeminarMinutesGoalStatus): string {
  if (status === 'met') {
    return t('mindmate.summary.status.met')
  }
  if (status === 'partial') {
    return t('mindmate.summary.status.partial')
  }
  return t('mindmate.summary.status.open')
}
</script>

<template>
  <article class="mm-doc">
    <header class="mm-doc__banner">
      <span
        class="mm-doc__blob"
        aria-hidden="true"
      />
      <span
        class="mm-doc__blob is-second"
        aria-hidden="true"
      />
      <h2>{{ docTitle }}</h2>
      <p v-if="model.scope">{{ model.scope }}</p>
    </header>
    <div class="mm-doc__body">
      <div
        v-if="model.timeRange || hostLine || speakerLine || model.observers.length"
        class="mm-doc__grid"
      >
        <div v-if="model.timeRange">
          <span><I18nText k="mindmate.summary.covered" /></span>
          <strong>{{ model.timeRange }}</strong>
        </div>
        <div v-if="hostLine">
          <span><I18nText k="mindmate.summary.host" /></span>
          <strong>{{ hostLine }}</strong>
        </div>
        <div v-if="speakerLine">
          <span><I18nText k="mindmate.summary.speakers" /></span>
          <strong>{{ speakerLine }}</strong>
        </div>
        <div v-if="model.observers.length">
          <span><I18nText k="mindmate.summary.observers" /></span>
          <strong>{{ observerText }}</strong>
        </div>
      </div>

      <section
        v-if="model.goals.length || !readonly"
        class="mm-doc__section"
      >
        <header>
          <h3><I18nText k="mindmate.summary.section.goals" /></h3>
          <button
            v-if="!readonly"
            type="button"
            class="mm-preview__edit"
            @click="toggleEdit('goals')"
          >
            <Pencil
              v-if="editing !== 'goals'"
              :size="13"
            />
            <I18nText
              v-if="editing === 'goals'"
              k="mindmate.summary.done"
            /><I18nText
              v-else
              k="mindmate.summary.edit"
            />
          </button>
        </header>
        <ul v-if="editing === 'goals'">
          <li
            v-for="(row, index) in model.goals"
            :key="`${row.goal}-${index}`"
          >
            <input
              class="mm-preview__input"
              :value="row.goal"
              @change="onGoalText(index, ($event.target as HTMLInputElement).value)"
            />
            <select
              class="mm-preview__input"
              :value="row.status"
              @change="
                onGoalStatus(
                  index,
                  ($event.target as HTMLSelectElement).value as SeminarMinutesGoalStatus
                )
              "
            >
              <option value="met"><I18nText k="mindmate.summary.status.met" /></option>
              <option value="partial"><I18nText k="mindmate.summary.status.partial" /></option>
              <option value="open"><I18nText k="mindmate.summary.status.open" /></option>
            </select>
          </li>
        </ul>
        <ul
          v-else
          class="mm-preview__goals"
        >
          <li
            v-for="(row, index) in model.goals"
            :key="`${row.goal}-${index}`"
          >
            <em
              class="mm-preview__pill"
              :class="`is-${row.status}`"
              >{{ statusLabel(row.status) }}</em
            >
            {{ row.goal }}
          </li>
        </ul>
      </section>

      <section
        v-if="model.consensus.length || !readonly"
        class="mm-doc__section"
      >
        <header>
          <h3><I18nText k="mindmate.summary.section.consensus" /></h3>
          <button
            v-if="!readonly"
            type="button"
            class="mm-preview__edit"
            @click="toggleEdit('consensus')"
          >
            <Pencil
              v-if="editing !== 'consensus'"
              :size="13"
            />
            <I18nText
              v-if="editing === 'consensus'"
              k="mindmate.summary.done"
            /><I18nText
              v-else
              k="mindmate.summary.edit"
            />
          </button>
        </header>
        <textarea
          v-if="editing === 'consensus'"
          class="mm-preview__input"
          :value="model.consensus.join('\n')"
          rows="4"
          @change="onLines('consensus', ($event.target as HTMLTextAreaElement).value)"
        />
        <ol
          v-else
          class="mm-doc__points"
        >
          <li
            v-for="(item, index) in model.consensus"
            :key="index"
          >
            <span>{{ index + 1 }}</span>
            {{ item }}
          </li>
        </ol>
      </section>

      <section
        v-if="model.open.length || !readonly"
        class="mm-doc__section"
      >
        <header>
          <h3><I18nText k="mindmate.summary.section.open" /></h3>
          <button
            v-if="!readonly"
            type="button"
            class="mm-preview__edit"
            @click="toggleEdit('open')"
          >
            <Pencil
              v-if="editing !== 'open'"
              :size="13"
            />
            <I18nText
              v-if="editing === 'open'"
              k="mindmate.summary.done"
            /><I18nText
              v-else
              k="mindmate.summary.edit"
            />
          </button>
        </header>
        <textarea
          v-if="editing === 'open'"
          class="mm-preview__input"
          :value="model.open.join('\n')"
          rows="3"
          @change="onLines('open', ($event.target as HTMLTextAreaElement).value)"
        />
        <div
          v-else
          class="mm-doc__note"
        >
          <p
            v-for="(item, index) in model.open"
            :key="index"
          >
            {{ item }}
          </p>
        </div>
      </section>

      <section
        v-if="model.materials.length || !readonly"
        class="mm-doc__section"
      >
        <header>
          <h3><I18nText k="mindmate.summary.section.materials" /></h3>
          <button
            v-if="!readonly"
            type="button"
            class="mm-preview__edit"
            @click="toggleEdit('materials')"
          >
            <Pencil
              v-if="editing !== 'materials'"
              :size="13"
            />
            <I18nText
              v-if="editing === 'materials'"
              k="mindmate.summary.done"
            /><I18nText
              v-else
              k="mindmate.summary.edit"
            />
          </button>
        </header>
        <textarea
          v-if="editing === 'materials'"
          class="mm-preview__input"
          :value="model.materials.join('\n')"
          rows="3"
          @change="onLines('materials', ($event.target as HTMLTextAreaElement).value)"
        />
        <p
          v-for="(item, index) in model.materials"
          v-else
          :key="index"
          class="mm-preview__file"
        >
          <ImageIcon
            v-if="materialKind(item) === 'image'"
            :size="14"
          />
          <FileText
            v-else
            :size="14"
          />
          {{ item }}
        </p>
      </section>

      <section
        v-if="model.tasks.length || !readonly"
        class="mm-doc__section"
      >
        <header>
          <h3><I18nText k="mindmate.summary.section.tasks" /></h3>
          <button
            v-if="!readonly"
            type="button"
            class="mm-preview__edit"
            @click="toggleEdit('tasks')"
          >
            <Pencil
              v-if="editing !== 'tasks'"
              :size="13"
            />
            <I18nText
              v-if="editing === 'tasks'"
              k="mindmate.summary.done"
            /><I18nText
              v-else
              k="mindmate.summary.edit"
            />
          </button>
        </header>
        <textarea
          v-if="editing === 'tasks'"
          class="mm-preview__input"
          :value="model.tasks.join('\n')"
          rows="3"
          @change="onLines('tasks', ($event.target as HTMLTextAreaElement).value)"
        />
        <ul
          v-else
          class="mm-doc__tasks"
        >
          <li
            v-for="(item, index) in model.tasks"
            :key="index"
          >
            <i aria-hidden="true" />
            <span>
              <strong v-if="taskLead(item).lead">{{ taskLead(item).lead }}</strong>
              {{ taskLead(item).lead ? taskLead(item).rest : item }}
            </span>
          </li>
        </ul>
      </section>

      <section
        v-if="model.quotes.length || !readonly"
        class="mm-doc__section"
      >
        <header>
          <h3>
            <I18nText k="mindmate.summary.section.quotes" />
            <small
              ><I18nText
                k="mindmate.summary.quoteCount"
                :params="{ n: model.quotes.length }"
            /></small>
          </h3>
          <button
            v-if="!readonly"
            type="button"
            class="mm-preview__edit"
            @click="toggleEdit('quotes')"
          >
            <Pencil
              v-if="editing !== 'quotes'"
              :size="13"
            />
            <I18nText
              v-if="editing === 'quotes'"
              k="mindmate.summary.done"
            /><I18nText
              v-else
              k="mindmate.summary.edit"
            />
          </button>
        </header>
        <textarea
          v-if="editing === 'quotes'"
          class="mm-preview__input"
          :value="model.quotes.join('\n')"
          rows="4"
          @change="onLines('quotes', ($event.target as HTMLTextAreaElement).value)"
        />
        <blockquote
          v-for="(item, index) in model.quotes"
          v-else
          :key="index"
        >
          <p>「{{ quoteParts(item).text }}」</p>
          <footer v-if="quoteParts(item).by">— {{ quoteParts(item).by }}</footer>
        </blockquote>
      </section>
    </div>
  </article>
</template>

<style scoped>
.mm-doc {
  overflow: hidden;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 10px 28px rgba(28, 25, 23, 0.08);
}

.mm-doc__banner {
  position: relative;
  overflow: hidden;
  padding: 28px 22px 22px;
  background: #1c1917;
  color: #fff;
}

.mm-doc__blob {
  position: absolute;
  top: 14px;
  left: 22px;
  width: 54px;
  height: 16px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.28);
}

.mm-doc__blob.is-second {
  left: 84px;
  width: 36px;
  background: rgba(255, 255, 255, 0.18);
}

.mm-doc__banner h2 {
  position: relative;
  margin: 22px 0 0;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.45;
}

.mm-doc__banner p {
  position: relative;
  margin: 8px 0 0;
  color: rgba(255, 255, 255, 0.82);
  font-size: 13px;
}

.mm-doc__body {
  padding: 8px 22px 20px;
}

.mm-doc__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px 20px;
  padding: 16px 0;
  border-bottom: 1px solid #f1f0f4;
}

.mm-doc__grid span {
  display: block;
  color: #a8a29e;
  font-size: 12px;
}

.mm-doc__grid strong {
  display: block;
  margin-top: 4px;
  color: #1c1917;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.45;
}

.mm-doc__section {
  margin-top: 18px;
}

.mm-doc__section header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.mm-doc__section h3 {
  margin: 0;
  color: #1c1917;
  font-size: 15px;
  font-weight: 700;
}

.mm-doc__section h3 small {
  margin-left: 6px;
  color: #a8a29e;
  font-size: 12px;
  font-weight: 500;
}

.mm-preview__edit {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 26px;
  height: auto;
  padding: 2px 10px;
  border: 1px solid #e7e5e4;
  border-radius: 9999px;
  background: #f5f5f4;
  color: #57534e;
  font-size: 12px;
  cursor: pointer;
}

.mm-preview__goals,
.mm-doc__section ul,
.mm-doc__points {
  margin: 0;
  padding: 0;
  list-style: none;
}

.mm-preview__goals li {
  margin-top: 8px;
  color: #44403c;
  font-size: 14px;
  line-height: 1.65;
}

.mm-preview__pill {
  margin-right: 6px;
  color: #57534e;
  font-style: normal;
  font-size: 12px;
}

.mm-doc__points li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 10px;
  color: #44403c;
  font-size: 14px;
  line-height: 1.6;
}

.mm-doc__points span {
  display: grid;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 999px;
  background: #e7e5e4;
  color: #44403c;
  font-size: 12px;
  font-weight: 700;
}

.mm-doc__note {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f5f5f4;
}

.mm-doc__note p,
.mm-preview__file {
  margin: 0;
  color: #44403c;
  font-size: 14px;
  line-height: 1.6;
}

.mm-doc__note p + p,
.mm-preview__file + .mm-preview__file {
  margin-top: 6px;
}

.mm-preview__file {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mm-preview__file svg {
  flex: 0 0 auto;
  color: #57534e;
}

.mm-doc__tasks li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 10px;
  color: #44403c;
  font-size: 14px;
  line-height: 1.55;
}

.mm-doc__tasks i {
  flex: 0 0 auto;
  width: 16px;
  height: 16px;
  margin-top: 2px;
  border: 1.5px solid #d6d3d1;
  border-radius: 4px;
}

.mm-doc__tasks strong {
  margin-right: 4px;
}

.mm-doc blockquote {
  margin: 8px 0 0;
  padding: 10px 12px;
  border-left: 3px solid #d6d3d1;
  border-radius: 8px;
  background: #fafafa;
}

.mm-doc blockquote p {
  margin: 0;
  color: #1c1917;
  font-size: 14px;
  line-height: 1.6;
}

.mm-doc blockquote footer {
  margin-top: 6px;
  color: #a8a29e;
  font-size: 12px;
}

.mm-preview__input {
  width: 100%;
  box-sizing: border-box;
  margin-top: 6px;
  padding: 8px 10px;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  background: #fff;
  color: #1c1917;
  font: inherit;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}

.mm-doc__section ul .mm-preview__input {
  margin-top: 0;
}
</style>
