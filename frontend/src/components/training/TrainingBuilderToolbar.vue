<script setup lang="ts">
import { computed, ref } from 'vue'

import { ElButton, ElCheckbox, ElOption, ElSelect } from 'element-plus'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { useLanguage } from '@/composables'
import TrainingArrowPicker from '@/components/training/TrainingArrowPicker.vue'
import TrainingEmojiPicker from '@/components/training/TrainingEmojiPicker.vue'
import TrainingRolePicker from '@/components/training/TrainingRolePicker.vue'
import TrainingMarkStepsBar from '@/components/training/TrainingMarkStepsBar.vue'
import TrainingTopicOptionsPanel from '@/components/training/TrainingTopicOptionsPanel.vue'
import { TRAINING_PAGES, type TrainingPageKey } from '@/config/trainingPages'
import type { TrainingArrowColor, TrainingArrowLine } from '@/config/trainingMarkPalettes'
import { stepSpotlight } from '@/composables/training/trainingBuilderSteps'
import {
  clampSpotlightScale,
  spotlightRadius,
  spotlightShape,
} from '@/composables/training/trainingOverlayDrag'
import type { TrainingCourseStep, TrainingSpotlightShape } from '@/types/training'
import type { MindMapCanvasMode } from '@/stores/ui'
import {
  readEffectiveMindMapCanvasMode,
  resolveSessionMindMapCanvasMode,
} from '@/utils/mindMapCanvasMode'

const BUILDER_DIAGRAM_TYPES = VALID_DIAGRAM_TYPES.filter((type) => type !== 'mind_map')

const props = defineProps<{
  step: TrainingCourseStep
}>()

function mindmapMode(step: TrainingCourseStep): MindMapCanvasMode {
  return resolveSessionMindMapCanvasMode(
    step.mindmap_canvas_mode ?? readEffectiveMindMapCanvasMode()
  )
}

const emit = defineEmits<{
  page: [key: TrainingPageKey]
  text: []
  emoji: [glyph: string]
  arrow: [opts: { color: TrainingArrowColor; line: TrainingArrowLine }]
  spotlight: []
  role: [role: string]
  image: [file: File]
  awake: []
}>()

const { t } = useLanguage()
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
  { value: 'circle' as const, label: t('training.builder.spotlightCircle') },
  { value: 'rect' as const, label: t('training.builder.spotlightRect') },
])

const isCanvas = computed(
  () => props.step.page_key === 'canvas' || props.step.type === 'canvas'
)
const canvasMode = computed({
  get: () => mindmapMode(props.step),
  set: (mode: MindMapCanvasMode) => onCanvasMode(mode),
})
const canvasModeOptions = computed(() => [
  { value: 'legacy' as const, label: t('settings.language.mindMapCanvasV1') },
  { value: 'v2' as const, label: t('settings.language.mindMapCanvasV2') },
])

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
  props.step.diagram_type = value === 'mind_map' ? 'mindmap' : value
}

function onCanvasMode(mode: MindMapCanvasMode): void {
  emit('awake')
  props.step.mindmap_canvas_mode = mode
}

function onImage(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('image', file)
  input.value = ''
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
}

function onSpotRadius(event: Event): void {
  const overlay = spotlight.value
  const input = event.target
  if (!overlay || !(input instanceof HTMLInputElement)) return
  overlay.r = clampSpotlightScale(Number(input.value))
}

function clearSpotlight(): void {
  const spot = spotlight.value
  props.step.overlays = (props.step.overlays || []).filter((overlay) => overlay !== spot)
  spotOpen.value = false
}
</script>

<template>
  <div class="builder-toolbar">
    <div class="builder-toolbar__row">
      <span class="builder-toolbar__label">{{ t('training.builder.groupFollow') }}</span>
      <ElSelect
        class="admin-swiss-select builder-toolbar__page"
        :model-value="step.page_key || 'mindgraph'"
        size="small"
        filterable
        :placeholder="t('training.builder.pageSelect')"
        @change="onPage"
      >
        <ElOption
          v-for="page in TRAINING_PAGES"
          :key="page.key"
          :label="t(page.labelKey)"
          :value="page.key"
        />
      </ElSelect>
      <template v-if="isCanvas">
        <ElSelect
          class="admin-swiss-select builder-toolbar__page"
          :model-value="step.diagram_type === 'mind_map' ? 'mindmap' : step.diagram_type || 'double_bubble_map'"
          size="small"
          @change="onDiagram"
        >
          <ElOption
            v-for="type in BUILDER_DIAGRAM_TYPES"
            :key="type"
            :label="t(`sidebar.diagramType.${type}`)"
            :value="type"
          />
        </ElSelect>
        <AdminSwissSegmented
          v-model="canvasMode"
          equal
          :options="canvasModeOptions"
          :ariaLabel="t('training.builder.groupCanvas')"
        />
        <TrainingTopicOptionsPanel :step="step" />
      </template>
      <label class="builder-toolbar__pull">
        <ElCheckbox
          :model-value="Boolean(step.pull_users)"
          @change="(value: boolean | string | number) => { step.pull_users = Boolean(value) }"
        />
        <span>{{ t('training.builder.pullUsers') }}</span>
      </label>
    </div>
    <TrainingMarkStepsBar
      :step="step"
      @awake="emit('awake')"
    />
    <div class="builder-toolbar__row">
      <span class="builder-toolbar__label">{{ t('training.builder.groupMarks') }}</span>
      <ElButton
        size="small"
        class="admin-swiss-btn"
        @click="addTextBubble"
      >
        {{ t('training.builder.toolText') }}
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
          {{ t('training.builder.overlayArrow') }}
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
          {{ t('training.builder.toolEmoji') }}
        </ElButton>
        <div
          v-if="emojiOpen"
          class="builder-toolbar__sheet"
        >
          <TrainingEmojiPicker @pick="pickEmoji" />
        </div>
      </div>
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
          {{ t('training.builder.toolSpotlight') }}
        </ElButton>
        <div
          v-if="spotOpen && spotlight"
          class="builder-toolbar__sheet builder-toolbar__sheet--spot"
        >
          <AdminSwissSegmented
            v-model="spotShape"
            equal
            :options="spotShapeOptions"
            :ariaLabel="t('training.builder.spotlightShape')"
          />
          <label class="builder-toolbar__slider">
            <span>{{ t('training.builder.spotlightRadius') }}</span>
            <input
              type="range"
              min="0.5"
              max="2.5"
              step="0.1"
              :value="spotlightRadius(spotlight)"
              @input="onSpotRadius($event)"
            >
          </label>
          <button
            type="button"
            class="builder-toolbar__clear"
            @click="clearSpotlight"
          >
            {{ t('training.builder.spotlightClear') }}
          </button>
        </div>
      </div>
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
          {{ t('training.builder.toolRoles') }}
        </ElButton>
        <div
          v-if="roleOpen"
          class="builder-toolbar__sheet builder-toolbar__sheet--roles"
        >
          <TrainingRolePicker @pick="pickRole" />
        </div>
      </div>
      <label class="builder-toolbar__upload">
        {{ t('training.builder.toolImage') }}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          @change="onImage"
        >
      </label>
    </div>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.builder-toolbar {
  position: relative;
  z-index: 5;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.builder-toolbar__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
@media (max-width: 768px) {
  .builder-toolbar__row {
    flex-direction: column;
    align-items: stretch;
  }
}
.builder-toolbar__label {
  min-width: 2.5rem;
  color: #78716c;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.04em;
}
.builder-toolbar__page.el-select {
  width: 11.5rem;
  max-width: 11.5rem;
  flex-shrink: 0;
}
.builder-toolbar__pull {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: #1c1917;
  font-size: 0.78rem;
  font-weight: 500;
}
.builder-toolbar__menu {
  position: relative;
}
.builder-toolbar__sheet {
  position: absolute;
  top: calc(100% + 0.35rem);
  left: 0;
  z-index: 20;
  border: 1px solid #e7e5e4;
  background: #fff;
  padding: 0.55rem;
  box-shadow: 0 10px 28px rgb(28 25 23 / 0.12);
}
.builder-toolbar__sheet--spot {
  display: flex;
  width: 12.5rem;
  flex-direction: column;
  gap: 0.45rem;
}
.builder-toolbar__sheet--roles {
  overflow: visible;
}
.builder-toolbar__menu :deep(.is-on.el-button) {
  border-color: #ca8a04;
  color: #854d0e;
}
.builder-toolbar__slider {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  color: #57534e;
  font-size: 0.72rem;
}
.builder-toolbar__slider input {
  width: 100%;
  accent-color: #ca8a04;
}
.builder-toolbar__clear {
  align-self: flex-end;
  border: 0;
  background: transparent;
  color: #78716c;
  font-size: 0.72rem;
  cursor: pointer;
}
.builder-toolbar__upload {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #57534e;
  font-size: 0.75rem;
}
.builder-toolbar__upload input {
  max-width: 9rem;
  font-size: 0.7rem;
}
</style>
