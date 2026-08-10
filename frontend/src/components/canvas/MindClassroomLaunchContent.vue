<script setup lang="ts">
/**
 * Mind Classroom launch settings — readable modal / panel layout.
 */
import { computed } from 'vue'

import { storeToRefs } from 'pinia'

import {
  BookOpenCheck,
  Check,
  GraduationCap,
  Presentation,
  Route,
  Sparkles,
  Trophy,
} from '@lucide/vue'

import ProfessionalContentAudienceBanner from '@/components/canvas/ProfessionalContentAudienceBanner.vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useMindClassroomLecture } from '@/composables/mindMap/useMindClassroomLecture'
import {
  MIND_CLASSROOM_MASTERY_IDS,
  MIND_CLASSROOM_PRESENTATION_IDS,
  MIND_CLASSROOM_SLIDE_STYLE_IDS,
  MIND_CLASSROOM_TONE_IDS,
  MIND_CLASSROOM_TOUR_SCOPE_IDS,
  type MindClassroomMasteryId,
  type MindClassroomPresentationId,
  type MindClassroomSlideStyleId,
  type MindClassroomToneId,
  type MindClassroomTourScopeId,
} from '@/config/mindClassroom'
import { useMindClassroomStore } from '@/stores'

const props = withDefaults(
  defineProps<{
    variant?: 'panel' | 'modal'
  }>(),
  { variant: 'panel' }
)

const emit = defineEmits<{
  started: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const classroomStore = useMindClassroomStore()
const { mastery, presentation, tourScope, slideStyle, tone } = storeToRefs(classroomStore)
const { startLecture } = useMindClassroomLecture()

const masteryIcons = {
  first_look: Sparkles,
  review: BookOpenCheck,
  teach: Trophy,
} as const

const presentationIcons = {
  canvas_tour: Route,
  slide_deck: Presentation,
} as const

const masteryOptions = computed(() =>
  MIND_CLASSROOM_MASTERY_IDS.map((id) => ({
    id,
    title: t(`canvas.mindClassroom.settings.mastery.${id}.title`),
    icon: masteryIcons[id],
  }))
)

const presentationOptions = computed(() =>
  MIND_CLASSROOM_PRESENTATION_IDS.map((id) => ({
    id,
    title: t(`canvas.mindClassroom.settings.presentation.${id}.title`),
    desc: t(`canvas.mindClassroom.settings.presentation.${id}.desc`),
    icon: presentationIcons[id],
  }))
)

const tourScopeOptions = computed(() =>
  MIND_CLASSROOM_TOUR_SCOPE_IDS.map((id) => ({
    id,
    title: t(`canvas.mindClassroom.settings.tourScope.${id}.title`),
    desc: t(`canvas.mindClassroom.settings.tourScope.${id}.desc`),
  }))
)

const slideStyleOptions = computed(() =>
  MIND_CLASSROOM_SLIDE_STYLE_IDS.map((id) => ({
    id,
    title: t(`canvas.mindClassroom.settings.slideStyle.${id}.title`),
  }))
)

const toneOptions = computed(() =>
  MIND_CLASSROOM_TONE_IDS.map((id) => ({
    id,
    title: t(`canvas.mindClassroom.settings.tone.${id}`),
  }))
)

function pickMastery(id: MindClassroomMasteryId): void {
  classroomStore.setMastery(id)
}

function pickPresentation(id: MindClassroomPresentationId): void {
  classroomStore.setPresentation(id)
}

function pickTourScope(id: MindClassroomTourScopeId): void {
  classroomStore.setTourScope(id)
}

function pickSlideStyle(id: MindClassroomSlideStyleId): void {
  classroomStore.setSlideStyle(id)
}

function pickTone(id: MindClassroomToneId): void {
  classroomStore.setTone(id)
}

function handleStart(): void {
  const result = startLecture()
  if (!result.ok) {
    notify.warning(
      result.reason === 'no_diagram'
        ? t('canvas.mindClassroom.lecture.needDiagram')
        : t('canvas.mindClassroom.lecture.emptySteps')
    )
    return
  }
  emit('started')
}
</script>

<template>
  <div
    class="mc-launch"
    :class="`mc-launch--${props.variant}`"
  >
    <div class="mc-launch__body">
      <p
        v-if="props.variant === 'modal'"
        class="mc-launch__lead"
      >
        {{ t('canvas.mindClassroom.lead') }}
      </p>

      <!-- 1. Mastery -->
      <section class="mc-block">
        <header class="mc-block__head">
          <span class="mc-block__index">1</span>
          <h3 class="mc-block__title">
            {{ t('canvas.mindClassroom.settings.masteryTitle') }}
          </h3>
        </header>
        <div
          class="mc-seg"
          role="radiogroup"
        >
          <button
            v-for="option in masteryOptions"
            :key="option.id"
            type="button"
            role="radio"
            class="mc-seg__item"
            :class="{ 'is-active': mastery === option.id }"
            :aria-checked="mastery === option.id"
            @click="pickMastery(option.id)"
          >
            <component
              :is="option.icon"
              class="mc-seg__icon"
              :stroke-width="2"
            />
            <span>{{ option.title }}</span>
          </button>
        </div>
      </section>

      <!-- 2. Presentation -->
      <section class="mc-block">
        <header class="mc-block__head">
          <span class="mc-block__index">2</span>
          <h3 class="mc-block__title">
            {{ t('canvas.mindClassroom.settings.presentationTitle') }}
          </h3>
        </header>

        <div class="mc-mode-grid">
          <button
            v-for="option in presentationOptions"
            :key="option.id"
            type="button"
            class="mc-mode"
            :class="{ 'is-active': presentation === option.id }"
            @click="pickPresentation(option.id)"
          >
            <span class="mc-mode__top">
              <span class="mc-mode__icon">
                <component
                  :is="option.icon"
                  class="h-4 w-4"
                  :stroke-width="2"
                />
              </span>
              <Check
                v-if="presentation === option.id"
                class="mc-mode__check"
                :stroke-width="2.5"
              />
            </span>
            <span class="mc-mode__title">{{ option.title }}</span>
            <span class="mc-mode__desc">{{ option.desc }}</span>
          </button>
        </div>

        <div
          v-if="presentation === 'canvas_tour'"
          class="mc-sub"
        >
          <p class="mc-sub__label">
            {{ t('canvas.mindClassroom.settings.tourScopeTitle') }}
          </p>
          <div class="mc-sub__row">
            <button
              v-for="option in tourScopeOptions"
              :key="option.id"
              type="button"
              class="mc-sub__btn"
              :class="{ 'is-active': tourScope === option.id }"
              @click="pickTourScope(option.id)"
            >
              <span class="mc-sub__btn-title">{{ option.title }}</span>
              <span class="mc-sub__btn-desc">{{ option.desc }}</span>
            </button>
          </div>
        </div>

        <div
          v-else
          class="mc-sub"
        >
          <p class="mc-sub__label">
            {{ t('canvas.mindClassroom.settings.slideStyleTitle') }}
          </p>
          <div class="mc-skins">
            <button
              v-for="option in slideStyleOptions"
              :key="option.id"
              type="button"
              class="mc-skin"
              :class="[`mc-skin--${option.id}`, { 'is-active': slideStyle === option.id }]"
              @click="pickSlideStyle(option.id)"
            >
              <span
                class="mc-skin__swatch"
                aria-hidden="true"
              />
              <span class="mc-skin__name">{{ option.title }}</span>
            </button>
          </div>
        </div>
      </section>

      <!-- 3. Tone -->
      <section class="mc-block">
        <header class="mc-block__head">
          <span class="mc-block__index">3</span>
          <h3 class="mc-block__title">
            {{ t('canvas.mindClassroom.settings.toneTitle') }}
          </h3>
        </header>
        <div class="mc-tones">
          <button
            v-for="option in toneOptions"
            :key="option.id"
            type="button"
            class="mc-tone"
            :class="{ 'is-active': tone === option.id }"
            @click="pickTone(option.id)"
          >
            {{ option.title }}
          </button>
        </div>
      </section>
    </div>

    <footer class="mc-launch__footer">
      <ProfessionalContentAudienceBanner />
      <button
        type="button"
        class="mc-launch__start"
        @click="handleStart"
      >
        <GraduationCap
          class="h-4 w-4"
          :stroke-width="2.25"
          aria-hidden="true"
        />
        {{ t('canvas.mindClassroom.start') }}
      </button>
    </footer>
  </div>
</template>

<style scoped>
.mc-launch {
  display: flex;
  flex-direction: column;
  min-height: 0;
  color: #0f172a;
}

.mc-launch--panel {
  height: 100%;
  flex: 1 1 auto;
}

.mc-launch__body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
}

.mc-launch--panel .mc-launch__body {
  flex: 1 1 auto;
  overflow-x: hidden;
  overflow-y: auto;
  padding-bottom: 8px;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.mc-launch--modal .mc-launch__body {
  gap: 22px;
  max-height: min(62vh, 560px);
  overflow-y: auto;
  padding-right: 2px;
  scrollbar-gutter: stable;
}

.mc-launch__lead {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #64748b;
}

.mc-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mc-block__head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mc-block__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 11px;
  font-weight: 800;
  flex-shrink: 0;
}

.mc-block__title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  letter-spacing: 0.01em;
}

/* Segmented mastery */
.mc-seg {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 2px;
  padding: 3px;
  border-radius: 12px;
  background: #f1f5f9;
}

.mc-seg__item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 32px;
  padding: 5px 4px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 650;
  line-height: 1.15;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.mc-launch--panel .mc-seg__item {
  gap: 3px;
  min-height: 30px;
  font-size: 11px;
}

.mc-seg__item:hover {
  color: #334155;
}

.mc-seg__item.is-active {
  background: #fff;
  color: #0f172a;
  box-shadow: 0 1px 3px rgb(15 23 42 / 0.08);
}

.mc-seg__icon {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  opacity: 0.75;
}

.mc-seg__item.is-active .mc-seg__icon {
  color: #2563eb;
  opacity: 1;
}

/* Presentation modes */
.mc-mode-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.mc-launch--modal .mc-mode-grid {
  grid-template-columns: 1fr 1fr;
}

.mc-mode {
  display: grid;
  grid-template-columns: auto 1fr auto;
  grid-template-rows: auto auto;
  column-gap: 10px;
  row-gap: 2px;
  align-items: start;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.mc-mode:hover {
  border-color: #cbd5e1;
  background: #f8fafc;
}

.mc-mode.is-active {
  border-color: transparent;
  background: #eff6ff;
  box-shadow: inset 0 0 0 1.5px #2563eb;
}

.mc-mode__top {
  display: contents;
}

.mc-mode__icon {
  grid-column: 1;
  grid-row: 1 / span 2;
  align-self: center;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: #0f766e;
  background: #ecfdf5;
}

.mc-mode.is-active .mc-mode__icon {
  color: #1d4ed8;
  background: #dbeafe;
}

.mc-mode__check {
  grid-column: 3;
  grid-row: 1 / span 2;
  align-self: center;
  width: 15px;
  height: 15px;
  color: #2563eb;
}

.mc-mode__title {
  grid-column: 2;
  grid-row: 1;
  font-size: 13px;
  font-weight: 750;
  color: #0f172a;
  line-height: 1.25;
}

.mc-mode__desc {
  grid-column: 2;
  grid-row: 2;
  font-size: 11px;
  line-height: 1.35;
  color: #64748b;
}

.mc-launch--panel .mc-mode {
  padding: 9px 10px;
}

.mc-launch--panel .mc-mode__desc {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Sub options — flat, no nested frame */
.mc-sub {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 2px;
}

.mc-sub__label {
  margin: 0;
  font-size: 12px;
  font-weight: 650;
  color: #64748b;
}

.mc-sub__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mc-sub__btn {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border: none;
  border-radius: 12px;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.15s ease,
    box-shadow 0.15s ease;
}

.mc-sub__btn:hover {
  background: #f1f5f9;
}

.mc-sub__btn.is-active {
  background: #eff6ff;
  box-shadow: inset 0 0 0 1.5px #2563eb;
}

.mc-sub__btn-title {
  font-size: 12px;
  font-weight: 700;
  color: #1e293b;
}

.mc-sub__btn.is-active .mc-sub__btn-title {
  color: #1d4ed8;
}

.mc-sub__btn-desc {
  font-size: 11px;
  line-height: 1.35;
  color: #94a3b8;
}

/* Slide skins */
.mc-skins {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.mc-launch--panel .mc-skins {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
}

.mc-launch--panel .mc-skin {
  flex: 0 0 72px;
  width: 72px;
}

.mc-skin {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: center;
}

.mc-skin__swatch {
  display: block;
  height: 48px;
  border-radius: 10px;
  box-shadow: inset 0 0 0 1px rgb(15 23 42 / 0.06);
  transition:
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.mc-skin:hover .mc-skin__swatch {
  transform: translateY(-1px);
}

.mc-skin.is-active .mc-skin__swatch {
  box-shadow:
    inset 0 0 0 1px rgb(37 99 235 / 0.2),
    0 0 0 2px #2563eb;
}

.mc-skin--general .mc-skin__swatch {
  background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
}

.mc-skin--chalkboard .mc-skin__swatch {
  background: linear-gradient(160deg, #1f2937 0%, #111827 100%);
}

.mc-skin--comic .mc-skin__swatch {
  background:
    linear-gradient(135deg, #fef08a 0%, #fdba74 45%, #f472b6 100%);
}

.mc-skin--handdrawn .mc-skin__swatch {
  background-color: #fffbeb;
  background-image:
    radial-gradient(circle at 20% 30%, rgb(120 53 15 / 0.12) 1.2px, transparent 1.5px),
    radial-gradient(circle at 70% 60%, rgb(120 53 15 / 0.1) 1px, transparent 1.4px),
    linear-gradient(180deg, #fff7ed 0%, #ffedd5 100%);
  background-size: 10px 10px, 14px 14px, auto;
}

.mc-skin__name {
  font-size: 11px;
  font-weight: 650;
  color: #64748b;
  line-height: 1.2;
}

.mc-skin.is-active .mc-skin__name {
  color: #1d4ed8;
  font-weight: 750;
}

/* Tone chips */
.mc-tones {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mc-tone {
  padding: 7px 12px;
  border: none;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.mc-tone:hover {
  background: #e2e8f0;
  color: #1e293b;
}

.mc-tone.is-active {
  background: #2563eb;
  color: #fff;
}

/* Footer — pinned under scroll body in panel */
.mc-launch__footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex-shrink: 0;
  margin-top: auto;
  padding: 12px 0 14px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.mc-launch--panel .mc-launch__footer {
  margin-top: 0;
  padding-left: 0;
  padding-right: 0;
}

.mc-launch--modal .mc-launch__footer {
  margin-top: 14px;
}

.mc-launch__start {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 44px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 750;
  color: #fff;
  background: #2563eb;
  box-shadow: 0 8px 20px rgb(37 99 235 / 0.22);
  cursor: pointer;
}

.mc-launch__start:hover {
  background: #1d4ed8;
}

.mc-launch--panel .mc-block {
  gap: 8px;
}
</style>
