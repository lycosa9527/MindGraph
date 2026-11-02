<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { ElButton, ElCheckbox } from 'element-plus'

import {
  AppWindow,
  ArrowUpRight,
  Eraser,
  Image,
  Layers,
  Lock,
  LockOpen,
  MessageSquare,
  PanelsTopLeft,
  Repeat,
  ShieldCheck,
  Smile,
  Sun,
  UserRound,
  Users,
  Waypoints,
} from '@lucide/vue'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import TrainingArrowPicker from '@/components/training/TrainingArrowPicker.vue'
import TrainingBuilderAudioField from '@/components/training/TrainingBuilderAudioField.vue'
import TrainingBuilderMascotField from '@/components/training/TrainingBuilderMascotField.vue'
import TrainingBuilderPickButton from '@/components/training/TrainingBuilderPickButton.vue'
import TrainingBuilderRibbonBar from '@/components/training/TrainingBuilderRibbonBar.vue'
import TrainingBuilderVodPicker from '@/components/training/TrainingBuilderVodPicker.vue'
import TrainingEmojiPicker from '@/components/training/TrainingEmojiPicker.vue'
import TrainingInteractBar from '@/components/training/TrainingInteractBar.vue'
import TrainingMarkStepsBar from '@/components/training/TrainingMarkStepsBar.vue'
import TrainingRolePicker from '@/components/training/TrainingRolePicker.vue'
import TrainingTopicOptionsPanel from '@/components/training/TrainingTopicOptionsPanel.vue'
import { swissGlassConfirm, useLanguage } from '@/composables'
import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import {
  BUILDER_CANVAS_TOOLS_TARGET,
  builderCanvasRibbonHosted,
  builderRibbonToolOwner,
} from '@/composables/training/builderCanvasRibbon'
import { applyModalKey, stepSpotlight } from '@/composables/training/trainingBuilderSteps'
import { currentMarkStep } from '@/composables/training/trainingMarkSteps'
import {
  clampSpotlightScale,
  spotlightRadius,
  spotlightShape,
} from '@/composables/training/trainingOverlayDrag'
import type { TrainingArrowColor, TrainingArrowLine } from '@/config/trainingMarkPalettes'
import { TRAINING_PAGES, type TrainingPageKey } from '@/config/trainingPages'
import { trainingModalsForPage } from '@/config/trainingUiTargets'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import type {
  TrainingCourseStep,
  TrainingRoleDepth,
  TrainingSpotlightShape,
} from '@/types/training'
import { isTrainingBuilderPath } from '@/utils/trainingClient'
import { assignTrainingStepField } from '@/utils/trainingStepPatch'

const route = useRoute()
const inCourseBuilder = computed(() => isTrainingBuilderPath(route.path))
const showCourseTools = computed(
  () =>
    inCourseBuilder.value &&
    (!builderCanvasRibbonHosted.value || builderRibbonToolOwner.value === 'course')
)
const showCanvasTools = computed(
  () =>
    inCourseBuilder.value &&
    builderCanvasRibbonHosted.value &&
    builderRibbonToolOwner.value === 'canvas'
)

const BUILDER_DIAGRAM_TYPES = VALID_DIAGRAM_TYPES.filter((type) => type !== 'mind_map')

const props = withDefaults(
  defineProps<{
    step: TrainingCourseStep
    previewing?: boolean
    readonly?: boolean
    saveLabel?: string
    saveTone?: 'saving' | 'dirty' | 'saved' | 'error'
  }>(),
  {
    previewing: false,
    readonly: false,
    saveLabel: '',
    saveTone: 'saved',
  }
)

const emit = defineEmits<{
  page: [key: TrainingPageKey]
  text: []
  emoji: [glyph: string]
  arrow: [opts: { color: TrainingArrowColor; line: TrainingArrowLine }]
  spotlight: []
  role: [role: string]
  roleAsset: [file: { id: string; url: string }]
  image: [file: File]
  awake: []
  lockArm: []
  lock: []
  save: []
  info: []
  preview: []
}>()

const { t } = useLanguage()
const flags = useFeatureFlagsStore()
const showVod = computed(() => flags.getFeatureVod())

onMounted(() => {
  if (!flags.getFeatureVod()) void flags.fetchFlags()
})

const RIBBON_TABS = [
  { id: 'slide', labelKey: 'training.builder.ribbonSlide' },
  { id: 'marks', labelKey: 'training.builder.groupMarks' },
  { id: 'media', labelKey: 'training.builder.ribbonMedia' },
  { id: 'steps', labelKey: 'training.builder.groupSteps' },
  { id: 'interact', labelKey: 'training.builder.groupInteract' },
] as const

type BuilderRibbonTab = (typeof RIBBON_TABS)[number]['id']

const roleDepth = ref<TrainingRoleDepth>('front')
const ribbonTab = ref<BuilderRibbonTab>('slide')
const emojiOpen = ref(false)
const arrowOpen = ref(false)
const spotOpen = ref(false)
const roleOpen = ref(false)
const spotlight = computed(() => stepSpotlight(props.step))
const spotShape = computed({
  get: (): TrainingSpotlightShape => spotlightShape(spotlight.value),
  set: (shape: TrainingSpotlightShape) => {
    const overlay = spotlight.value
    if (overlay) overlay.shape = shape
  },
})
const spotShapeOptions = computed(() => [
  {
    value: 'circle' as const,
    label: t('training.builder.spotlightCircle'),
    labelKey: 'training.builder.spotlightCircle',
  },
  {
    value: 'rect' as const,
    label: t('training.builder.spotlightRect'),
    labelKey: 'training.builder.spotlightRect',
  },
])

const isCanvas = computed(() => props.step.page_key === 'canvas' || props.step.type === 'canvas')
const pageModals = computed(() => trainingModalsForPage(props.step.page_key || 'mindgraph'))
const pageOptions = computed(() =>
  TRAINING_PAGES.map((page) => ({ value: page.key, label: String(t(page.labelKey)) }))
)
const modalOptions = computed(() => [
  { value: '', label: String(t('training.builder.modalNone')) },
  ...pageModals.value.map((modal) => ({ value: modal.key, label: String(t(modal.labelKey)) })),
])
const diagramValue = computed(() =>
  props.step.diagram_type === 'mind_map'
    ? 'mindmap'
    : props.step.diagram_type || 'double_bubble_map'
)
const diagramOptions = computed(() =>
  BUILDER_DIAGRAM_TYPES.map((type) => ({
    value: type,
    label: String(t(`sidebar.diagramType.${type}`)),
  }))
)

function onModal(value: string): void {
  emit('awake')
  applyModalKey(props.step, value || null)
}

function addTextBubble(): void {
  emit('awake')
  emit('text')
}

function onPage(value: string): void {
  emit('awake')
  emit('page', value as TrainingPageKey)
}

function onDiagram(value: string): void {
  emit('awake')
  assignTrainingStepField(props.step, 'diagram_type', value === 'mind_map' ? 'mindmap' : value)
}

async function onMandatory(value: boolean | string | number): Promise<void> {
  const next = Boolean(value)
  if (!next) {
    assignTrainingStepField(props.step, 'mandatory', false)
    return
  }
  if (props.step.mandatory) return
  try {
    await swissGlassConfirm(
      String(t('training.builder.mandatoryConfirm')),
      String(t('training.builder.mandatory')),
      { type: 'warning' }
    )
    assignTrainingStepField(props.step, 'mandatory', true)
  } catch {
    assignTrainingStepField(props.step, 'mandatory', false)
  }
}

async function onAlwaysPlay(value: boolean | string | number): Promise<void> {
  const next = Boolean(value)
  if (!next) {
    assignTrainingStepField(props.step, 'always_play', false)
    return
  }
  if (props.step.always_play) return
  try {
    await swissGlassConfirm(
      String(t('training.builder.alwaysPlayConfirm')),
      String(t('training.builder.alwaysPlay')),
      { type: 'warning' }
    )
    assignTrainingStepField(props.step, 'always_play', true)
  } catch {
    assignTrainingStepField(props.step, 'always_play', false)
  }
}

function onImage(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('image', file)
  input.value = ''
}

function onVodVideo(id: string | null): void {
  assignTrainingStepField(props.step, 'vod_media_id', id)
  if (id) return
  assignTrainingStepField(props.step, 'vod_autoplay', false)
  assignTrainingStepField(props.step, 'vod_width', null)
  assignTrainingStepField(props.step, 'vod_height', null)
}

function onPullUsers(value: boolean | string | number): void {
  assignTrainingStepField(props.step, 'pull_users', Boolean(value))
}

function onVodAutoplay(value: boolean): void {
  assignTrainingStepField(props.step, 'vod_autoplay', value)
}

function pickEmoji(glyph: string): void {
  emit('awake')
  emit('emoji', glyph)
  emojiOpen.value = false
}

function pickArrow(opts: { color: TrainingArrowColor; line: TrainingArrowLine }): void {
  emit('awake')
  emit('arrow', opts)
  arrowOpen.value = false
}

function closeMenus(): void {
  emojiOpen.value = false
  arrowOpen.value = false
  spotOpen.value = false
  roleOpen.value = false
}

function selectRibbonTab(id: BuilderRibbonTab): void {
  ribbonTab.value = id
  builderRibbonToolOwner.value = 'course'
  closeMenus()
}

function onRibbonSelect(id: string): void {
  const tab = RIBBON_TABS.find((item) => item.id === id)
  if (tab) selectRibbonTab(tab.id)
}

function toggleEmoji(): void {
  const next = !emojiOpen.value
  closeMenus()
  emojiOpen.value = next
}

function toggleArrow(): void {
  emit('awake')
  const next = !arrowOpen.value
  closeMenus()
  arrowOpen.value = next
}

function toggleSpotlight(): void {
  emit('awake')
  const next = !spotOpen.value
  closeMenus()
  if (!spotlight.value) {
    emit('spotlight')
    spotOpen.value = true
    return
  }
  spotOpen.value = next
}

function toggleRoles(): void {
  emit('awake')
  const next = !roleOpen.value
  closeMenus()
  roleOpen.value = next
}

function pickRole(role: string): void {
  emit('awake')
  emit('role', role)
  roleOpen.value = false
  setRoleDepth(roleDepth.value)
}

function onMascot(file: { id: string; url: string }): void {
  emit('awake')
  emit('roleAsset', file)
  setRoleDepth(roleDepth.value)
}

function setRoleDepth(depth: TrainingRoleDepth): void {
  roleDepth.value = depth
  const at = currentMarkStep(props.step)
  for (const overlay of props.step.overlays || []) {
    if (overlay.kind === 'role' && (overlay.step || 1) === at) overlay.depth = depth
  }
}

function onSpotRadius(event: Event): void {
  const overlay = spotlight.value
  const input = event.target
  if (!overlay || !(input instanceof HTMLInputElement)) return
  overlay.r = clampSpotlightScale(Number(input.value))
}

function clearSpotlight(): void {
  const spot = spotlight.value
  assignTrainingStepField(
    props.step,
    'overlays',
    (props.step.overlays || []).filter((overlay) => overlay !== spot)
  )
  spotOpen.value = false
}
</script>

<template>
  <div
    v-if="inCourseBuilder"
    class="builder-ribbon"
  >
    <TrainingBuilderRibbonBar
      :tabs="RIBBON_TABS"
      :active="ribbonTab"
      :previewing="props.previewing"
      :readonly="props.readonly"
      :save-label="props.saveLabel"
      :save-tone="props.saveTone"
      @select="onRibbonSelect"
      @save="emit('save')"
      @info="emit('info')"
      @preview="emit('preview')"
    />
    <div
      v-show="showCourseTools"
      id="builder-ribbon-panel"
      class="builder-ribbon__panel"
      role="tabpanel"
      :aria-labelledby="`builder-ribbon-tab-${ribbonTab}`"
    >
      <div
        v-show="ribbonTab === 'slide'"
        class="builder-ribbon__pane"
      >
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <TrainingBuilderPickButton
              :model-value="step.page_key || 'mindgraph'"
              :options="pageOptions"
              :ariaLabel="String(t('training.builder.pageSelect'))"
              @change="onPage"
            >
              <template #icon>
                <AppWindow
                  class="builder-ribbon__icon"
                  aria-hidden="true"
                />
              </template>
            </TrainingBuilderPickButton>
            <TrainingBuilderPickButton
              :model-value="step.modal_key || ''"
              :options="modalOptions"
              :ariaLabel="String(t('training.builder.modal'))"
              @change="onModal"
            >
              <template #icon>
                <PanelsTopLeft
                  class="builder-ribbon__icon"
                  aria-hidden="true"
                />
              </template>
            </TrainingBuilderPickButton>
          </div>
        </section>
        <section
          v-if="isCanvas"
          class="builder-ribbon__group"
        >
          <div class="builder-ribbon__tools">
            <TrainingBuilderPickButton
              :model-value="diagramValue"
              :options="diagramOptions"
              :ariaLabel="String(t('training.builder.groupCanvas'))"
              @change="onDiagram"
            >
              <template #icon>
                <Waypoints
                  class="builder-ribbon__icon"
                  aria-hidden="true"
                />
              </template>
            </TrainingBuilderPickButton>
            <TrainingTopicOptionsPanel :step="step" />
          </div>
        </section>
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <label class="builder-toolbar__pull">
              <Users
                class="builder-ribbon__icon"
                aria-hidden="true"
              />
              <ElCheckbox
                :model-value="Boolean(step.pull_users)"
                @change="onPullUsers"
              />
              <span><I18nText k="training.builder.pullUsers" /></span>
            </label>
            <ElButton
              size="small"
              class="admin-swiss-btn"
              :class="{ 'is-on': Boolean(step.ui_lock || step.modal_key) }"
              :aria-pressed="Boolean(step.ui_lock || step.modal_key)"
              @pointerdown="emit('lockArm')"
              @click="emit('lock')"
            >
              <LockOpen
                v-if="step.ui_lock || step.modal_key"
                class="builder-ribbon__icon"
                aria-hidden="true"
              />
              <Lock
                v-else
                class="builder-ribbon__icon"
                aria-hidden="true"
              />
              <I18nText
                :k="
                  step.ui_lock || step.modal_key
                    ? 'training.builder.unlock'
                    : 'training.builder.lock'
                "
              />
            </ElButton>
          </div>
        </section>
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <label class="builder-toolbar__pull">
              <ShieldCheck
                class="builder-ribbon__icon"
                aria-hidden="true"
              />
              <ElCheckbox
                :model-value="Boolean(step.mandatory)"
                @change="onMandatory"
              />
              <span :title="t('training.builder.mandatoryHint')">
                <I18nText k="training.builder.mandatory" />
              </span>
            </label>
            <label class="builder-toolbar__pull">
              <Repeat
                class="builder-ribbon__icon"
                aria-hidden="true"
              />
              <ElCheckbox
                :model-value="Boolean(step.always_play)"
                @change="onAlwaysPlay"
              />
              <span :title="t('training.builder.alwaysPlayHint')">
                <I18nText k="training.builder.alwaysPlay" />
              </span>
            </label>
          </div>
        </section>
      </div>
      <div
        v-show="ribbonTab === 'marks'"
        class="builder-ribbon__pane"
      >
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <ElButton
              size="small"
              class="admin-swiss-btn"
              @click="addTextBubble"
            >
              <MessageSquare
                class="builder-ribbon__icon"
                aria-hidden="true"
              />
              <I18nText k="training.builder.toolText" />
            </ElButton>
            <div
              class="builder-toolbar__menu"
              @click.stop
            >
              <ElButton
                size="small"
                class="admin-swiss-btn"
                @click="toggleArrow"
              >
                <ArrowUpRight
                  class="builder-ribbon__icon"
                  aria-hidden="true"
                />
                <I18nText k="training.builder.overlayArrow" />
              </ElButton>
              <div
                v-if="arrowOpen"
                class="builder-toolbar__sheet"
              >
                <TrainingArrowPicker @pick="pickArrow" />
              </div>
            </div>
            <div
              class="builder-toolbar__menu"
              @click.stop
            >
              <ElButton
                size="small"
                class="admin-swiss-btn"
                @click="toggleEmoji"
              >
                <Smile
                  class="builder-ribbon__icon"
                  aria-hidden="true"
                />
                <I18nText k="training.builder.toolEmoji" />
              </ElButton>
              <div
                v-if="emojiOpen"
                class="builder-toolbar__sheet"
              >
                <TrainingEmojiPicker @pick="pickEmoji" />
              </div>
            </div>
            <label class="builder-toolbar__upload">
              <Image
                class="builder-ribbon__icon"
                aria-hidden="true"
              />
              <I18nText k="training.builder.toolImage" />
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                @change="onImage"
              />
            </label>
          </div>
        </section>
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <div
              class="builder-toolbar__menu"
              @click.stop
            >
              <ElButton
                size="small"
                class="admin-swiss-btn"
                :class="{ 'is-on': Boolean(spotlight) }"
                @click="toggleSpotlight"
              >
                <Sun
                  class="builder-ribbon__icon"
                  aria-hidden="true"
                />
                <I18nText k="training.builder.toolSpotlight" />
              </ElButton>
              <div
                v-if="spotOpen && spotlight"
                class="builder-toolbar__sheet builder-toolbar__sheet--spot"
              >
                <AdminSwissSegmented
                  v-model="spotShape"
                  equal
                  :options="spotShapeOptions"
                  :aria-label="t('training.builder.spotlightShape')"
                />
                <label class="builder-toolbar__slider">
                  <span><I18nText k="training.builder.spotlightRadius" /></span>
                  <input
                    type="range"
                    min="0.5"
                    max="2.5"
                    step="0.1"
                    :value="spotlightRadius(spotlight)"
                    @input="onSpotRadius($event)"
                  />
                </label>
                <button
                  type="button"
                  class="builder-toolbar__clear"
                  @click="clearSpotlight"
                >
                  <Eraser
                    class="builder-ribbon__icon"
                    aria-hidden="true"
                  />
                  <I18nText k="training.builder.spotlightClear" />
                </button>
              </div>
            </div>
          </div>
        </section>
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <div
              class="builder-toolbar__menu"
              @click.stop
            >
              <ElButton
                size="small"
                class="admin-swiss-btn"
                :class="{ 'is-on': roleOpen }"
                @click="toggleRoles"
              >
                <Users
                  class="builder-ribbon__icon"
                  aria-hidden="true"
                />
                <I18nText k="training.builder.toolRoles" />
              </ElButton>
              <div
                v-if="roleOpen"
                class="builder-toolbar__sheet builder-toolbar__sheet--roles"
              >
                <TrainingRolePicker @pick="pickRole" />
                <div class="builder-toolbar__depth">
                  <ElButton
                    size="small"
                    class="admin-swiss-btn"
                    :class="{ 'is-on': roleDepth === 'behind' }"
                    @click="setRoleDepth('behind')"
                  >
                    <Layers
                      class="builder-ribbon__icon"
                      aria-hidden="true"
                    />
                    <I18nText k="training.builder.roleBehind" />
                  </ElButton>
                  <ElButton
                    size="small"
                    class="admin-swiss-btn"
                    :class="{ 'is-on': roleDepth === 'front' }"
                    @click="setRoleDepth('front')"
                  >
                    <UserRound
                      class="builder-ribbon__icon"
                      aria-hidden="true"
                    />
                    <I18nText k="training.builder.roleFront" />
                  </ElButton>
                </div>
              </div>
            </div>
            <TrainingBuilderMascotField @placed="onMascot" />
          </div>
        </section>
      </div>
      <div
        v-show="ribbonTab === 'media'"
        class="builder-ribbon__pane"
      >
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <TrainingBuilderAudioField kind="voice" />
            <TrainingBuilderAudioField kind="music" />
          </div>
        </section>
        <section
          v-if="showVod"
          class="builder-ribbon__group"
        >
          <div class="builder-ribbon__tools">
            <TrainingBuilderVodPicker
              :step="step"
              @video="onVodVideo"
              @autoplay="onVodAutoplay"
            />
          </div>
        </section>
      </div>
      <div
        v-show="ribbonTab === 'steps'"
        class="builder-ribbon__pane"
      >
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <TrainingMarkStepsBar
              :step="step"
              @awake="emit('awake')"
            />
          </div>
        </section>
      </div>
      <div
        v-show="ribbonTab === 'interact'"
        class="builder-ribbon__pane"
      >
        <section class="builder-ribbon__group">
          <div class="builder-ribbon__tools">
            <TrainingInteractBar
              :step="step"
              @awake="emit('awake')"
            />
          </div>
        </section>
      </div>
    </div>
    <div
      v-show="showCanvasTools"
      :id="BUILDER_CANVAS_TOOLS_TARGET"
      class="builder-ribbon__panel"
    />
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped src="./trainingBuilderRibbon.css"></style>
