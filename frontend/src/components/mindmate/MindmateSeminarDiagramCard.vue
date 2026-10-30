<script setup lang="ts">
/**
 * Seminar bubble preview of a shared library diagram.
 * Renders the saved spec the same way the learning-space review pane does.
 */
import { onBeforeUnmount, ref, watch } from 'vue'

import { Loader2, Maximize2, X } from '@lucide/vue'

import MindmateSeminarShelfMenu from '@/components/mindmate/MindmateSeminarShelfMenu.vue'
import ShowcaseInlineDiagramPreview from '@/components/showcase/ShowcaseInlineDiagramPreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import { seminarSpectator } from '@/composables/mindmate/mindmateSeminarChrome'
import {
  type SharedCanvasDiagramPreview,
  fetchSharedCanvasDiagramPreview,
} from '@/utils/mindmateSeminarDiagramLibrary'
import { shelveSeminarItem } from '@/utils/mindmateSeminarFolder'

const props = defineProps<{
  sessionId: string
  diagramId: string
  caption: string
  thumbnailUrl?: string | null
  opening: boolean
}>()

const emit = defineEmits<{
  open: []
}>()

const { t } = useLanguage()
const notify = useNotifications()
const shelving = ref(false)

const preview = ref<SharedCanvasDiagramPreview | null>(null)
const loading = ref(true)
const failed = ref(false)
const viewerOpen = ref(false)

function openViewer(): void {
  if (!preview.value) {
    return
  }
  viewerOpen.value = true
}

function closeViewer(): void {
  viewerOpen.value = false
}

function onViewerKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    closeViewer()
  }
}

watch(viewerOpen, (open) => {
  if (open) {
    window.addEventListener('keydown', onViewerKeydown)
    return
  }
  window.removeEventListener('keydown', onViewerKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onViewerKeydown)
})

watch(
  () => [props.sessionId, props.diagramId] as const,
  () => {
    void loadPreview()
  },
  { immediate: true }
)

async function loadPreview(): Promise<void> {
  loading.value = true
  failed.value = false
  preview.value = null
  const loaded = await fetchSharedCanvasDiagramPreview(props.sessionId, props.diagramId)
  if (!loaded) {
    failed.value = true
    loading.value = false
    return
  }
  preview.value = loaded
  loading.value = false
}

async function shelveDiagram(destination: 'resource' | 'artifact'): Promise<void> {
  if (shelving.value || !props.sessionId) {
    return
  }
  shelving.value = true
  try {
    await shelveSeminarItem(props.sessionId, {
      kind: 'diagram',
      destination,
      diagramId: props.diagramId,
      title: props.caption.trim() || t('mindmate.artifacts.diagramFallback'),
    })
    notify.successKey(
      destination === 'resource' ? 'mindmate.shelf.savedResource' : 'mindmate.shelf.savedArtifact'
    )
  } catch {
    notify.errorKey('mindmate.shelf.failed')
  } finally {
    shelving.value = false
  }
}
</script>

<template>
  <div class="mm-shared-diagram">
    <p
      v-if="caption"
      class="mm-shared-diagram__caption"
    >
      {{ caption }}
    </p>
    <div
      class="mm-shared-diagram__stage"
      :class="{ 'mm-shared-diagram__stage--openable': Boolean(preview) }"
      :role="preview ? 'button' : undefined"
      :tabindex="preview ? 0 : undefined"
      :aria-label="preview ? t('mindmate.docViewer.fullscreen') : undefined"
      @click.stop="openViewer"
      @keydown.enter.prevent.stop="openViewer"
      @keydown.space.prevent.stop="openViewer"
    >
      <div
        v-if="loading"
        class="mm-shared-diagram__status"
      >
        <Loader2
          class="animate-spin"
          :size="18"
        />
      </div>
      <ShowcaseInlineDiagramPreview
        v-else-if="preview"
        class="mm-shared-diagram__fit"
        browse
        tight-fit
        :spec="preview.spec"
        :diagram-type="preview.diagramType"
        :thumbnail-url="thumbnailUrl"
      />
      <div
        v-else
        class="mm-shared-diagram__status"
      >
        <img
          v-if="thumbnailUrl"
          :src="thumbnailUrl"
          alt=""
        />
        <span v-else-if="failed"><I18nText k="showcase.detail.diagramPreviewFailed" /></span>
      </div>
      <span
        v-if="preview"
        class="mm-shared-diagram__zoom"
        aria-hidden="true"
      >
        <Maximize2 :size="14" />
      </span>
    </div>
    <div class="mm-shared-diagram__actions">
      <MindmateSeminarShelfMenu
        v-if="!seminarSpectator"
        :busy="shelving"
        @pick="shelveDiagram"
      />
      <button
        type="button"
        :disabled="opening"
        @click.stop="emit('open')"
      >
        <I18nText k="mindmate.openInCanvas" />
      </button>
    </div>
  </div>
  <Teleport to="body">
    <div
      v-if="viewerOpen && preview"
      class="mm-diagram-viewer"
      @click.self="closeViewer"
    >
      <div
        class="mm-diagram-viewer__panel"
        role="dialog"
        aria-modal="true"
        :aria-label="caption || t('mindmate.docViewer.fullscreen')"
      >
        <div class="mm-diagram-viewer__bar">
          <p class="mm-diagram-viewer__title">{{ caption }}</p>
          <button
            type="button"
            class="mm-diagram-viewer__close"
            :aria-label="t('common.close')"
            @click="closeViewer"
          >
            <X
              :size="16"
              aria-hidden="true"
            />
          </button>
        </div>
        <div
          class="mm-diagram-viewer__stage"
          @wheel.stop
        >
          <ShowcaseInlineDiagramPreview
            browse
            tight-fit
            :spec="preview.spec"
            :diagram-type="preview.diagramType"
            :thumbnail-url="thumbnailUrl"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mm-shared-diagram {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  width: 100%;
}

.mm-shared-diagram__caption {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.mm-shared-diagram__stage {
  position: relative;
  width: 100%;
  min-width: 280px;
  aspect-ratio: 7 / 5;
  height: auto;
  overflow: hidden;
  border-radius: 12px;
  background: #f9fafb;
  border: 1px solid rgba(255, 255, 255, 0.8);
}

.mm-shared-diagram__stage--openable {
  cursor: zoom-in;
}

.mm-shared-diagram__fit {
  pointer-events: none;
}

.mm-shared-diagram__zoom {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  color: #44403c;
  pointer-events: none;
  box-shadow: 0 1px 2px rgba(28, 25, 23, 0.12);
}

.mm-shared-diagram__stage :deep(.showcase-inline-diagram-preview),
.mm-shared-diagram__status {
  position: absolute;
  inset: 0;
}

.mm-shared-diagram__status {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  text-align: center;
  color: #78716c;
  font-size: 12px;
  line-height: 1.4;
}

.mm-shared-diagram__status img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.mm-shared-diagram__actions {
  display: flex;
  align-items: center;
  align-self: flex-start;
  gap: 8px;
}

.mm-shared-diagram button {
  align-self: flex-start;
  min-height: 28px;
  padding: 4px 12px;
  border: 1px solid #e7e5e4;
  border-radius: 9999px;
  background: #f5f5f4;
  color: #44403c;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.mm-shared-diagram button:disabled {
  opacity: 0.6;
  cursor: default;
}

.mm-diagram-viewer {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(28, 25, 23, 0.45);
}

.mm-diagram-viewer__panel {
  display: flex;
  flex-direction: column;
  width: min(960px, 100%);
  height: min(720px, calc(100vh - 48px));
  overflow: hidden;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 24px 64px rgba(28, 25, 23, 0.28);
}

.mm-diagram-viewer__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 48px;
  padding: 0 8px 0 16px;
  border-bottom: 1px solid #e7e5e4;
}

.mm-diagram-viewer__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mm-diagram-viewer__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #44403c;
  cursor: pointer;
}

.mm-diagram-viewer__close:hover {
  background: #f5f5f4;
}

.mm-diagram-viewer__stage {
  position: relative;
  flex: 1;
  min-height: 0;
  background: #f9fafb;
}

.mm-diagram-viewer__stage :deep(.showcase-inline-diagram-preview) {
  position: absolute;
  inset: 0;
}
</style>
