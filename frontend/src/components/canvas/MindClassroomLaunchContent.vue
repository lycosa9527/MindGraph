<script setup lang="ts">
/**
 * Mind Classroom launch settings — readable modal / panel layout.
 */
import { computed, nextTick, onMounted, watch } from 'vue'

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
import {
  requestClassroomRestart,
  requestClassroomRestorePrepared,
  requestClassroomStart,
} from '@/composables/mindMap/classroomCommands'
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
import { useAiContentLevelStore, useAuthStore, useMindClassroomStore } from '@/stores'
import {
  isMindClassroomQueueBusy,
  mindClassroomProgressStats,
  mindClassroomStartFillPercent,
  mindClassroomStartLabelKey,
  shouldShowMindClassroomRestart,
} from '@/utils/mindClassroomLaunchState'

const props = withDefaults(
  defineProps<{
    variant?: 'panel' | 'modal'
  }>(),
  { variant: 'panel' }
)

const { t } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()
const classroomStore = useMindClassroomStore()
const {
  mastery,
  presentation,
  tourScope,
  slideStyle,
  tone,
  jobStatus,
  jobProgress,
  jobError,
  preparedSteps,
  voiceWarmup,
  startInFlight,
} = storeToRefs(classroomStore)
const aiLevelStore = useAiContentLevelStore()
const { level: audienceLevel } = storeToRefs(aiLevelStore)

const hasPrepared = computed(() => preparedSteps.value.length > 0)
const queueBusy = computed(() =>
  isMindClassroomQueueBusy(jobStatus.value, startInFlight.value, voiceWarmup.value)
)
const startLocked = computed(() => queueBusy.value || !authStore.isAuthenticated)
const showRestart = computed(() =>
  shouldShowMindClassroomRestart({
    jobStatus: jobStatus.value,
    hasPrepared: hasPrepared.value,
    authenticated: authStore.isAuthenticated,
  })
)
const progressStats = computed(() => mindClassroomProgressStats(jobProgress.value))
const startLabelKey = computed(() =>
  mindClassroomStartLabelKey({
    jobStatus: jobStatus.value,
    starting: startInFlight.value,
    hasPrepared: hasPrepared.value,
    presentation: presentation.value,
    voiceWarmup: voiceWarmup.value,
    branchName: progressStats.value.branchName,
    ttsReady: progressStats.value.ttsReady,
    remaining: progressStats.value.inFlight,
  })
)
const startLabel = computed(() =>
  t(startLabelKey.value, {
    name: progressStats.value.branchName,
    done: progressStats.value.done,
    total: progressStats.value.total,
  })
)
const startFillPercent = computed(() =>
  mindClassroomStartFillPercent(progressStats.value.done, progressStats.value.total)
)
const startFailed = computed(() => jobStatus.value === 'failed' && !hasPrepared.value)

watch([mastery, presentation, tourScope, slideStyle, tone, audienceLevel], () => {
  if (queueBusy.value) return
  classroomStore.clearPrepared()
  requestClassroomRestorePrepared()
})

onMounted(() => {
  requestClassroomRestorePrepared()
})

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
  if (queueBusy.value) return
  classroomStore.setMastery(id)
}

function pickPresentation(id: MindClassroomPresentationId): void {
  if (queueBusy.value) return
  classroomStore.setPresentation(id)
}

function pickTourScope(id: MindClassroomTourScopeId): void {
  if (queueBusy.value) return
  classroomStore.setTourScope(id)
}

function pickSlideStyle(id: MindClassroomSlideStyleId): void {
  if (queueBusy.value) return
  classroomStore.setSlideStyle(id)
}

function pickTone(id: MindClassroomToneId): void {
  if (queueBusy.value) return
  classroomStore.setTone(id)
}

function handleRadioGroupKeydown<T extends string>(
  event: KeyboardEvent,
  ids: readonly T[],
  current: T,
  pick: (id: T) => void
): void {
  const currentIndex = ids.indexOf(current)
  let nextIndex: number | null = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = (currentIndex + 1) % ids.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = (currentIndex - 1 + ids.length) % ids.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = ids.length - 1
  }
  if (nextIndex === null) return
  event.preventDefault()
  const nextId = ids[nextIndex]
  if (!nextId) return
  pick(nextId)
  const group = (event.currentTarget as HTMLElement).closest('[role="radiogroup"]')
  void nextTick(() => {
    group?.querySelectorAll<HTMLElement>('[role="radio"]')[nextIndex]?.focus()
  })
}

function handleStart(): void {
  if (startLocked.value) return
  if (!authStore.isAuthenticated) {
    notify.warning(t('canvas.mindClassroom.queue.loginRequired'))
    return
  }
  requestClassroomStart()
}

function handleRestart(): void {
  if (!authStore.isAuthenticated) {
    notify.warning(t('canvas.mindClassroom.queue.loginRequired'))
    return
  }
  requestClassroomRestart()
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
            :disabled="queueBusy"
            :tabindex="mastery === option.id ? 0 : -1"
            @click="pickMastery(option.id)"
            @keydown="
              handleRadioGroupKeydown($event, MIND_CLASSROOM_MASTERY_IDS, mastery, pickMastery)
            "
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

        <div
          class="mc-mode-grid"
          role="radiogroup"
          :aria-label="t('canvas.mindClassroom.settings.presentationTitle')"
        >
          <button
            v-for="option in presentationOptions"
            :key="option.id"
            type="button"
            class="mc-mode"
            :class="{ 'is-active': presentation === option.id }"
            role="radio"
            :aria-checked="presentation === option.id"
            :disabled="queueBusy"
            :tabindex="presentation === option.id ? 0 : -1"
            @click="pickPresentation(option.id)"
            @keydown="
              handleRadioGroupKeydown(
                $event,
                MIND_CLASSROOM_PRESENTATION_IDS,
                presentation,
                pickPresentation
              )
            "
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
          <div
            class="mc-sub__row"
            role="radiogroup"
            :aria-label="t('canvas.mindClassroom.settings.tourScopeTitle')"
          >
            <button
              v-for="option in tourScopeOptions"
              :key="option.id"
              type="button"
              class="mc-sub__btn"
              :class="{ 'is-active': tourScope === option.id }"
              role="radio"
              :aria-checked="tourScope === option.id"
              :disabled="queueBusy"
              :tabindex="tourScope === option.id ? 0 : -1"
              @click="pickTourScope(option.id)"
              @keydown="
                handleRadioGroupKeydown(
                  $event,
                  MIND_CLASSROOM_TOUR_SCOPE_IDS,
                  tourScope,
                  pickTourScope
                )
              "
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
          <div
            class="mc-skins"
            role="radiogroup"
            :aria-label="t('canvas.mindClassroom.settings.slideStyleTitle')"
          >
            <button
              v-for="option in slideStyleOptions"
              :key="option.id"
              type="button"
              class="mc-skin"
              :class="[`mc-skin--${option.id}`, { 'is-active': slideStyle === option.id }]"
              role="radio"
              :aria-checked="slideStyle === option.id"
              :disabled="queueBusy"
              :tabindex="slideStyle === option.id ? 0 : -1"
              @click="pickSlideStyle(option.id)"
              @keydown="
                handleRadioGroupKeydown(
                  $event,
                  MIND_CLASSROOM_SLIDE_STYLE_IDS,
                  slideStyle,
                  pickSlideStyle
                )
              "
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
        <div
          class="mc-tones"
          role="radiogroup"
          :aria-label="t('canvas.mindClassroom.settings.toneTitle')"
        >
          <button
            v-for="option in toneOptions"
            :key="option.id"
            type="button"
            class="mc-tone"
            :class="{ 'is-active': tone === option.id }"
            role="radio"
            :aria-checked="tone === option.id"
            :disabled="queueBusy"
            :tabindex="tone === option.id ? 0 : -1"
            @click="pickTone(option.id)"
            @keydown="handleRadioGroupKeydown($event, MIND_CLASSROOM_TONE_IDS, tone, pickTone)"
          >
            {{ option.title }}
          </button>
        </div>
      </section>
    </div>

    <footer class="mc-launch__footer">
      <ProfessionalContentAudienceBanner />
      <p
        v-if="!authStore.isAuthenticated"
        class="mc-launch__hint"
      >
        {{ t('canvas.mindClassroom.queue.loginRequired') }}
      </p>
      <div class="mc-launch__actions">
        <button
          type="button"
          class="mc-launch__start"
          :class="{
            'is-busy': queueBusy,
            'is-ready': hasPrepared && !startLocked,
            'is-failed': startFailed,
          }"
          :style="
            queueBusy ? { '--mc-launch-fill': `${startFillPercent}%` } : undefined
          "
          :disabled="startLocked"
          :title="startFailed ? jobError || startLabel : undefined"
          :role="queueBusy && progressStats.total > 0 ? 'progressbar' : undefined"
          :aria-valuemin="queueBusy && progressStats.total > 0 ? 0 : undefined"
          :aria-valuemax="queueBusy && progressStats.total > 0 ? 100 : undefined"
          :aria-valuenow="queueBusy && progressStats.total > 0 ? startFillPercent : undefined"
          :aria-valuetext="
            queueBusy && progressStats.total > 0
              ? `${progressStats.done}/${progressStats.total}`
              : undefined
          "
          :aria-live="queueBusy || hasPrepared || startFailed ? 'polite' : undefined"
          @click="handleStart"
        >
          <GraduationCap
            class="h-4 w-4 shrink-0"
            :stroke-width="2.25"
            aria-hidden="true"
          />
          <span class="mc-launch__start-label">{{ startLabel }}</span>
        </button>
        <button
          v-if="showRestart"
          type="button"
          class="mc-launch__restart"
          :disabled="!authStore.isAuthenticated"
          :title="t('canvas.mindClassroom.queue.restartHint')"
          @click="handleRestart"
        >
          {{ t('canvas.mindClassroom.queue.restart') }}
        </button>
      </div>
    </footer>
  </div>
</template>

<style scoped src="./mindClassroomLaunchContent.css"></style>
