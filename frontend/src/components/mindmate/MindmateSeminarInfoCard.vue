<script setup lang="ts">
/**
 * Opening seminar brief, pinned above the chat.
 * The host can fill in goals and materials after the seminar has started.
 */
import { computed, ref } from 'vue'

import { ChevronDown, GraduationCap, Pencil, Plus, Target, Trash2 } from '@lucide/vue'

import { useLanguage } from '@/composables'
import { SEMINAR_BRIEF_ROW_MAX, SEMINAR_BRIEF_TOPIC_MAX } from '@/utils/mindmateSeminarBrief'
import type { SeminarBriefCardModel, SeminarBriefEditPayload } from '@/utils/mindmateSeminarCards'
import { seminarAvatarSurname, seminarAvatarTone } from '@/utils/seminarAvatarSurname'

const props = defineProps<{
  model: SeminarBriefCardModel
  editable?: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'save', payload: SeminarBriefEditPayload, done: (ok: boolean) => void): void
}>()

const { t } = useLanguage()

interface GoalDraft {
  id: number
  text: string
}

const GOAL_CAP = 12
let draftSeq = 0

const editing = ref(false)
const peopleOpen = ref(false)
const topicDraft = ref('')
const goalRows = ref<GoalDraft[]>([])

const showGoals = computed(
  () => editing.value || Boolean(props.editable) || props.model.goals.length > 0
)
const hasPeople = computed(
  () => props.model.participants.length > 0 || Boolean(props.model.visibility)
)
const topicReady = computed(() => topicDraft.value.trim().length > 0)

function nextDraftId(): number {
  draftSeq += 1
  return draftSeq
}

function beginEdit(): void {
  if (!props.editable || props.saving) {
    return
  }
  const goals = props.model.goals.length ? props.model.goals : ['']
  topicDraft.value = props.model.topic
  goalRows.value = goals.map((text) => ({ id: nextDraftId(), text }))
  editing.value = true
}

function addGoal(): void {
  if (goalRows.value.length >= GOAL_CAP) {
    return
  }
  goalRows.value = [...goalRows.value, { id: nextDraftId(), text: '' }]
}

function removeGoal(id: number): void {
  const next = goalRows.value.filter((row) => row.id !== id)
  goalRows.value = next.length ? next : [{ id: nextDraftId(), text: '' }]
}

function cancelEdit(): void {
  if (props.saving) {
    return
  }
  editing.value = false
}

function isLeaderRole(role: string): boolean {
  const head = role.split('·')[0]?.trim() ?? ''
  if (!head) {
    return false
  }
  const leader = t('mindmate.home.brief.role.leader').trim()
  return head === leader || head === '组长' || head === '組長' || head === 'Lead'
}

function saveEdit(): void {
  if (props.saving) {
    return
  }
  const topic = topicDraft.value.trim()
  if (!topic) {
    return
  }
  const goals = goalRows.value.map((row) => row.text.trim()).filter(Boolean)
  emit(
    'save',
    {
      topic,
      goals,
    },
    (ok: boolean) => {
      if (ok) {
        editing.value = false
      }
    }
  )
}
</script>

<template>
  <article class="mm-info-card">
    <span
      class="mm-info-card__wash"
      aria-hidden="true"
    />
    <span
      class="mm-info-card__ring mm-info-card__ring--corner"
      aria-hidden="true"
    />
    <span
      class="mm-info-card__ring mm-info-card__ring--left"
      aria-hidden="true"
    />
    <span
      class="mm-info-card__dots"
      aria-hidden="true"
    />
    <div class="mm-info-card__head">
      <p class="mm-info-card__kicker">
        <GraduationCap
          :size="15"
          :stroke-width="2"
        />
        <span><I18nText k="mindmate.briefCard.kicker" /></span>
      </p>
      <button
        v-if="editable && !editing"
        type="button"
        class="mm-info-card__edit"
        @click="beginEdit"
      >
        <Pencil
          :size="14"
          :stroke-width="2"
        />
        <I18nText k="common.edit" />
      </button>
    </div>
    <input
      v-if="editing"
      v-model="topicDraft"
      type="text"
      class="mm-info-card__topic-input"
      :maxlength="SEMINAR_BRIEF_TOPIC_MAX"
      :placeholder="t('mindmate.home.brief.topicPlaceholder')"
      :disabled="saving"
    />
    <h3
      v-else
      class="mm-info-card__topic"
    >
      {{ model.topic }}
    </h3>
    <div
      class="mm-info-card__rule"
      aria-hidden="true"
    />

    <section
      v-if="showGoals"
      class="mm-info-card__block"
    >
      <h4>
        <I18nText k="mindmate.home.brief.goals" />
        <span
          v-if="editing"
          class="mm-info-card__optional"
        >
          <I18nText k="mindmate.home.brief.optional" />
        </span>
      </h4>
      <div
        v-if="editing"
        class="mm-info-card__editor"
      >
        <div
          v-for="row in goalRows"
          :key="row.id"
          class="mm-info-card__line"
        >
          <input
            v-model="row.text"
            type="text"
            class="mm-info-card__input"
            :maxlength="SEMINAR_BRIEF_ROW_MAX"
            :placeholder="t('mindmate.home.brief.goalPlaceholder')"
            :disabled="saving"
          />
          <button
            type="button"
            class="mm-info-card__icon"
            :aria-label="t('mindmate.home.brief.remove')"
            :disabled="saving"
            @click="removeGoal(row.id)"
          >
            <Trash2 :size="15" />
          </button>
        </div>
        <button
          v-if="goalRows.length < GOAL_CAP"
          type="button"
          class="mm-info-card__add"
          :disabled="saving"
          @click="addGoal"
        >
          <Plus :size="15" />
          <I18nText k="mindmate.home.brief.add" />
        </button>
      </div>
      <ol v-else-if="model.goals.length">
        <li
          v-for="(goal, index) in model.goals"
          :key="index"
        >
          {{ goal }}
        </li>
      </ol>
      <button
        v-else
        type="button"
        class="mm-info-card__empty"
        @click="beginEdit"
      >
        <Target
          :size="16"
          :stroke-width="2"
        />
        <I18nText k="mindmate.briefCard.emptyGoals" />
      </button>
    </section>

    <section
      v-if="hasPeople"
      class="mm-info-card__block"
    >
      <button
        type="button"
        class="mm-info-card__fold"
        :aria-expanded="peopleOpen"
        @click="peopleOpen = !peopleOpen"
      >
        <span><I18nText k="mindmate.home.brief.participants" /></span>
        <span
          v-if="model.visibility"
          class="mm-info-card__tag"
        >
          {{ model.visibility }}
        </span>
        <ChevronDown
          class="mm-info-card__chevron"
          :class="{ 'is-open': peopleOpen }"
          :size="16"
        />
      </button>
      <ul
        v-show="peopleOpen"
        class="mm-info-card__people"
      >
        <li
          v-for="(person, index) in model.participants"
          :key="`${person.name}-${index}`"
        >
          <span
            class="mm-info-card__avatar"
            :style="{
              background: seminarAvatarTone(person.name).background,
              color: seminarAvatarTone(person.name).color,
            }"
          >
            {{ seminarAvatarSurname(person.name) }}
          </span>
          <span class="mm-info-card__name">{{ person.name }}</span>
          <em
            v-if="person.role"
            :class="{ 'is-leader': isLeaderRole(person.role) }"
          >
            {{ person.role }}
          </em>
        </li>
      </ul>
    </section>

    <div
      v-if="editing"
      class="mm-info-card__actions"
    >
      <button
        type="button"
        class="mm-info-card__cancel"
        :disabled="saving"
        @click="cancelEdit"
      >
        <I18nText k="common.cancel" />
      </button>
      <button
        type="button"
        class="mm-info-card__save"
        :disabled="saving || !topicReady"
        @click="saveEdit"
      >
        <I18nText k="common.save" />
      </button>
    </div>
  </article>
</template>

<style scoped>
.mm-info-card {
  position: relative;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
  padding: 18px 22px 20px;
  border: 1px solid #e6e6ec;
  border-radius: 16px;
  background: #fff;
  box-shadow:
    0 1px 2px rgba(24, 25, 28, 0.05),
    0 4px 12px rgba(24, 25, 28, 0.05);
  color: #18191c;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.mm-info-card__wash,
.mm-info-card__ring,
.mm-info-card__dots {
  position: absolute;
  pointer-events: none;
}

.mm-info-card__wash {
  top: 0;
  right: 0;
  left: 0;
  height: 156px;
  background: linear-gradient(180deg, rgba(80, 70, 229, 0.16), rgba(80, 70, 229, 0));
}

.mm-info-card__ring--corner {
  top: -42px;
  right: -36px;
  width: 168px;
  height: 168px;
  border-radius: 50%;
  background:
    radial-gradient(circle, transparent 22%, rgba(80, 70, 229, 0.16) 23% 25%, transparent 26%),
    radial-gradient(circle, transparent 46%, rgba(80, 70, 229, 0.12) 47% 50%, transparent 51%),
    radial-gradient(circle, transparent 70%, rgba(80, 70, 229, 0.1) 71% 75%, transparent 76%);
}

.mm-info-card__ring--left {
  top: 42%;
  left: -52px;
  width: 96px;
  height: 96px;
  border: 1px solid rgba(192, 132, 252, 0.45);
  border-radius: 50%;
}

.mm-info-card__dots {
  right: 16px;
  bottom: 14px;
  width: 42px;
  height: 28px;
  background:
    radial-gradient(circle at 6px 10px, rgba(192, 132, 252, 0.7) 2px, transparent 2.6px),
    radial-gradient(circle at 16px 4px, rgba(80, 70, 229, 0.28) 1.5px, transparent 2.2px),
    radial-gradient(circle at 26px 16px, rgba(139, 133, 217, 0.75) 2.2px, transparent 2.8px),
    radial-gradient(circle at 36px 8px, rgba(192, 132, 252, 0.45) 1.6px, transparent 2.2px);
}

.mm-info-card__head,
.mm-info-card__topic,
.mm-info-card__topic-input,
.mm-info-card__rule,
.mm-info-card__block,
.mm-info-card__actions {
  position: relative;
  z-index: 1;
}

.mm-info-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mm-info-card__kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  color: #57534e;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.14em;
}

.mm-info-card__edit {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  border-radius: 999px;
  padding: 5px 12px;
  background: #f5f5f4;
  color: #44403c;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
  cursor: pointer;
}

.mm-info-card__edit:hover {
  background: #e7e5e4;
  color: #1c1917;
}

.mm-info-card__add,
.mm-info-card__cancel {
  border: none;
  background: transparent;
  color: #44403c;
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}

.mm-info-card__add:hover,
.mm-info-card__cancel:hover {
  color: #1c1917;
}

.mm-info-card__topic,
.mm-info-card__topic-input {
  margin: 16px 0 0;
  color: #18191c;
  font-size: 24px;
  line-height: 1.35;
  font-weight: 700;
}

.mm-info-card__topic-input {
  display: block;
  width: 100%;
  box-sizing: border-box;
  border: none;
  border-bottom: 1px solid #e7e5e4;
  padding: 0 0 6px;
  background: transparent;
  font-family: inherit;
}

.mm-info-card__topic-input:focus {
  outline: none;
  border-bottom-color: #1c1917;
}

.mm-info-card__rule {
  height: 1px;
  margin: 14px 0 0;
  background: #ececf1;
}

.mm-info-card__block {
  margin-top: 16px;
}

.mm-info-card__block h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
  color: #6b6b76;
  font-size: 13px;
  font-weight: 500;
}

.mm-info-card__block h4::before,
.mm-info-card__fold::before {
  content: '';
  width: 3px;
  height: 14px;
  flex: 0 0 auto;
  border-radius: 2px;
  background: #1c1917;
}

.mm-info-card__fold {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  color: #6b6b76;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
}

.mm-info-card__chevron {
  margin-left: auto;
  color: #a8a29e;
  transition: transform 0.15s ease;
  transform: rotate(-90deg);
}

.mm-info-card__chevron.is-open {
  transform: rotate(0deg);
}

.mm-info-card__optional {
  color: #a8a29e;
  font-size: 12px;
  font-weight: 500;
}

.mm-info-card__tag {
  padding: 2px 8px;
  border-radius: 999px;
  background: #f5f5f4;
  color: #44403c;
  font-style: normal;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0;
}

.mm-info-card ol,
.mm-info-card ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.mm-info-card ol {
  display: flex;
  flex-direction: column;
  gap: 6px;
  counter-reset: goal;
}

.mm-info-card ol li {
  counter-increment: goal;
  color: #18191c;
  font-size: 14px;
  line-height: 1.55;
}

.mm-info-card ol li::before {
  content: counter(goal) '. ';
  color: #57534e;
  font-weight: 650;
}

.mm-info-card__people {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.mm-info-card__people li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px 4px 4px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #ececf1;
  font-size: 13px;
  color: #18191c;
}

.mm-info-card__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  flex: 0 0 auto;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 650;
  line-height: 1;
}

.mm-info-card__name {
  font-weight: 650;
}

.mm-info-card__people em {
  color: #6b6b76;
  font-style: normal;
  font-size: 12px;
  font-weight: 500;
}

.mm-info-card__people em.is-leader {
  color: #1c1917;
}

.mm-info-card__files {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mm-info-card__files li {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #18191c;
  font-size: 13px;
  line-height: 1.45;
}

.mm-info-card__files li span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-info-card__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  border: 1px solid rgba(192, 132, 252, 0.55);
  border-radius: 12px;
  background: rgba(80, 70, 229, 0.05);
  color: #a8a29e;
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
}

.mm-info-card__empty:hover {
  background: rgba(80, 70, 229, 0.09);
}

.mm-info-card__editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mm-info-card__line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mm-info-card__input {
  flex: 1;
  min-width: 0;
  border: 1px solid #e6e6ec;
  border-radius: 10px;
  padding: 7px 10px;
  background: #fff;
  color: #18191c;
  font: inherit;
  font-size: 14px;
}

.mm-info-card__input:focus {
  outline: 2px solid rgba(28, 25, 23, 0.12);
  border-color: #a8a29e;
}

.mm-info-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #a8a29e;
  cursor: pointer;
}

.mm-info-card__icon:hover {
  color: #1c1917;
  background: #f5f5f4;
}

.mm-info-card__add {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
  padding: 0;
  font-size: 13px;
}

.mm-info-card__file {
  display: none;
}

.mm-info-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 14px;
}

.mm-info-card__cancel {
  font-size: 13px;
}

.mm-info-card__save {
  border: none;
  border-radius: 999px;
  padding: 6px 16px;
  background: #1c1917;
  color: #fafaf9;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.mm-info-card__save:hover {
  background: #292524;
}

.mm-info-card__save:disabled,
.mm-info-card__cancel:disabled,
.mm-info-card__add:disabled,
.mm-info-card__icon:disabled,
.mm-info-card__input:disabled {
  cursor: default;
  opacity: 0.6;
}
</style>
