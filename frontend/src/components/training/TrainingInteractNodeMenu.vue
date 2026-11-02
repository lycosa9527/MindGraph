<script setup lang="ts">
/**
 * Walk-node menu. Each row places the same mark the annotate tab would:
 * a text bubble, a mascot, a library video, or an uploaded picture.
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { ElDropdown, ElDropdownItem, ElDropdownMenu } from 'element-plus'

import { Check, MoreHorizontal } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import '@/components/mindgraph/mindgraphLangSwitcher.css'
import TrainingBuilderPickButton from '@/components/training/TrainingBuilderPickButton.vue'
import { useLanguage } from '@/composables'
import { useNotifications } from '@/composables/core/useNotifications'
import {
  builderDiagramNodes,
  focusBuilderDiagramNode,
} from '@/composables/training/builderDiagramBridge'
import { addOverlay } from '@/composables/training/trainingBuilderSteps'
import { openTrainingDragHint } from '@/composables/training/trainingDragKnock'
import {
  interactReadCursor,
  nodeHasLink,
  nodeVodId,
  orderedReadNodes,
  readInteract,
  setNodeVideo,
} from '@/composables/training/trainingInteract'
import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'
import type { TrainingCourseStep, TrainingInteractExtraKind } from '@/types/training'
import { type TrainingVodItem, fetchTrainingVodLibrary } from '@/utils/trainingVodApi'

const props = withDefaults(
  defineProps<{
    step: TrainingCourseStep
    nodeId: string
    explainOnly?: boolean
  }>(),
  { explainOnly: false }
)

const emit = defineEmits<{
  awake: []
}>()

const NODE_EXTRAS = [
  { id: 'note', label: 'training.builder.interactExtraNote' },
  { id: 'mascot', label: 'training.builder.interactExtraMascot' },
  { id: 'video', label: 'training.builder.interactExtraVideo' },
  { id: 'image', label: 'training.builder.interactExtraImage' },
] as const satisfies readonly { id: TrainingInteractExtraKind; label: string }[]

const { t } = useLanguage()
const notify = useNotifications()
const builder = useTrainingBuilderStore()
const mascotInput = ref<HTMLInputElement | null>(null)
const imageInput = ref<HTMLInputElement | null>(null)
const anchor = ref<HTMLButtonElement | null>(null)
const sheetRef = ref<HTMLElement | null>(null)
const videoOpen = ref(false)
const videos = ref<TrainingVodItem[]>([])
const loaded = ref(false)
const sheetTop = ref(0)
const sheetLeft = ref(0)

const videoOptions = computed(() => [
  { value: '', label: String(t('training.builder.vodNone')) },
  ...videos.value.map((item) => ({ value: item.id, label: item.title })),
])
const currentVod = computed(() => nodeVodId(props.step, props.nodeId) || '')

function showNode(): void {
  const order = orderedReadNodes(
    builderDiagramNodes.value,
    readInteract(props.step)?.read_order ?? []
  )
  const index = order.findIndex((node) => node.id === props.nodeId)
  if (index >= 0) interactReadCursor.value = index
  focusBuilderDiagramNode(props.nodeId, props.step)
}

function onCommand(command: string | number | object): void {
  if (command === 'explain') {
    const hint =
      readInteract(props.step)?.blanks.find((row) => row.node_id === props.nodeId)?.hint ?? ''
    openTrainingDragHint(props.nodeId, hint, true)
    return
  }
  if (command === 'note') {
    emit('awake')
    addOverlay(props.step, 'text', { node_id: props.nodeId, text: '' })
    showNode()
    return
  }
  if (command === 'mascot') {
    mascotInput.value?.click()
    return
  }
  if (command === 'image') {
    imageInput.value?.click()
    return
  }
  if (command === 'video') void openVideo()
}

function placeSheet(): void {
  const box = anchor.value?.getBoundingClientRect()
  if (!box) return
  sheetTop.value = box.bottom + 6
  sheetLeft.value = Math.max(8, box.left - 220)
}

async function openVideo(): Promise<void> {
  videoOpen.value = true
  placeSheet()
  if (loaded.value) return
  try {
    const library = await fetchTrainingVodLibrary()
    videos.value = library.items
  } catch {
    videos.value = []
  } finally {
    loaded.value = true
  }
}

function onVideo(value: string): void {
  emit('awake')
  setNodeVideo(props.step, props.nodeId, value || null)
  videoOpen.value = false
  showNode()
}

async function placeFile(kind: 'mascot' | 'image', event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  const file = input.files?.[0]
  input.value = ''
  if (!file || !builder.courseId) return
  emit('awake')
  try {
    const uploaded = await uploadTrainingFile(
      builder.courseId,
      kind === 'mascot' ? 'mascot' : 'slide',
      file
    )
    addOverlay(props.step, 'role', {
      asset_id: uploaded.id,
      src: uploaded.url,
      node_id: props.nodeId,
      depth: 'front',
      x: kind === 'image' ? 18 : 88,
      y: kind === 'image' ? 70 : 64,
      ...(kind === 'image' ? { link: 'image' as const } : {}),
    })
    showNode()
  } catch {
    notify.errorKey('training.builder.uploadFailed')
  }
}

function onDocPointer(event: PointerEvent): void {
  const target = event.target
  if (!(target instanceof Node)) return
  if (anchor.value?.contains(target) || sheetRef.value?.contains(target)) return
  videoOpen.value = false
}

watch(videoOpen, (open) => {
  if (open) document.addEventListener('pointerdown', onDocPointer, true)
  else document.removeEventListener('pointerdown', onDocPointer, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocPointer, true)
})
</script>

<template>
  <div
    class="interact-node-menu"
    @click.stop
    @pointerdown.stop
    @keydown.stop
  >
    <ElDropdown
      trigger="click"
      placement="bottom-end"
      popper-class="builder-pick-popper mindgraph-lang-switcher-popper"
      @command="onCommand"
    >
      <button
        ref="anchor"
        type="button"
        class="interact-node-menu__more"
        draggable="false"
        :aria-label="t('training.builder.interactNodeMenu')"
      >
        <MoreHorizontal
          class="interact-node-menu__icon"
          aria-hidden="true"
        />
      </button>
      <template #dropdown>
        <ElDropdownMenu class="mindgraph-lang-switcher__menu">
          <ElDropdownItem
            v-if="explainOnly"
            command="explain"
          >
            <span class="mindgraph-lang-switcher__row">
              <span class="mindgraph-lang-switcher__label">
                <I18nText k="canvas.floatingToolbar.explain" />
              </span>
            </span>
          </ElDropdownItem>
          <ElDropdownItem
            v-for="extra in explainOnly ? [] : NODE_EXTRAS"
            :key="extra.id"
            :command="extra.id"
          >
            <span class="mindgraph-lang-switcher__row">
              <span class="mindgraph-lang-switcher__label">
                <I18nText :k="extra.label" />
              </span>
              <Check
                v-if="nodeHasLink(step, nodeId, extra.id)"
                class="mindgraph-lang-switcher__check"
                :size="16"
                aria-hidden="true"
              />
            </span>
          </ElDropdownItem>
        </ElDropdownMenu>
      </template>
    </ElDropdown>
    <Teleport to="body">
      <div
        v-if="videoOpen"
        ref="sheetRef"
        class="interact-node-menu__sheet"
        :style="{ top: `${sheetTop}px`, left: `${sheetLeft}px` }"
      >
        <TrainingBuilderPickButton
          :model-value="currentVod"
          :options="videoOptions"
          :ariaLabel="String(t('training.builder.vodVideo'))"
          @change="onVideo"
        />
        <span
          v-if="loaded && videos.length === 0"
          class="interact-node-menu__empty"
        >
          <I18nText k="training.builder.vodEmpty" />
        </span>
      </div>
    </Teleport>
    <input
      ref="mascotInput"
      class="interact-node-menu__file"
      type="file"
      accept="image/webp,.webp"
      :aria-label="t('training.builder.mascot')"
      @change="placeFile('mascot', $event)"
    />
    <input
      ref="imageInput"
      class="interact-node-menu__file"
      type="file"
      accept="image/png,image/jpeg,image/webp"
      :aria-label="t('training.builder.toolImage')"
      @change="placeFile('image', $event)"
    />
  </div>
</template>

<style scoped>
.interact-node-menu {
  flex: none;
}
.interact-node-menu__more {
  display: flex;
  width: 1.4rem;
  height: 1.4rem;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
}
.interact-node-menu__more:hover {
  background: #f3f4f6;
  color: #1f2937;
}
.interact-node-menu__icon {
  width: 14px;
  height: 14px;
}
.interact-node-menu__file {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.interact-node-menu__sheet {
  position: fixed;
  z-index: 5000;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  border: 1px solid #e7e5e4;
  border-radius: 10px;
  background: #fff;
  padding: 0.45rem;
  box-shadow: 0 10px 28px rgb(28 25 23 / 0.12);
}
.interact-node-menu__empty {
  color: #78716c;
  font-size: 12px;
}
</style>
