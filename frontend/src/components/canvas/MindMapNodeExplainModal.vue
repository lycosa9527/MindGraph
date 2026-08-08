<script setup lang="ts">
/**
 * Mind map node explain modal — Swiss stone shell, three accent panels.
 * Kitty sits beside the title with a stable speech bubble while streaming.
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { ElDialog } from 'element-plus'

import { HelpCircle, Lightbulb, Sparkles } from '@lucide/vue'

import KittyBlackCatMascot from '@/components/kitty/KittyBlackCatMascot.vue'

import { useLanguage } from '@/composables'
import type { KittyAgentState } from '@/composables/kitty/useKittyAgent'
import type {
  MindMapExplainFacet,
  MindMapExplainPanel,
  MindMapNodeExplainTarget,
} from '@/composables/mindMap/useMindMapNodeExplain'
import { isChineseUiLocale } from '@/types/sidebar-quotes'

import {
  type ExplainBubbleLine,
  pickExplainBubblePool,
  shuffleExplainBubbles,
} from './mindMapNodeExplainBubbles'

const BUBBLE_ROTATE_MS = 2600

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  target: MindMapNodeExplainTarget | null
  panels: MindMapExplainPanel[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t, currentLanguage } = useLanguage()

const nodeLabel = computed(() => props.target?.nodeLabel?.trim() || '')

const statusLabel = computed(() => {
  if (props.panels.some((panel) => panel.error && !panel.streaming)) {
    return t('canvas.mindMapNodeExplain.statusError')
  }
  if (props.loading) return t('canvas.mindMapNodeExplain.statusStreaming')
  return t('canvas.mindMapNodeExplain.statusReady')
})

const kittyAgentState = computed((): KittyAgentState => {
  if (props.panels.some((panel) => panel.error)) return 'error'
  const streaming = props.panels.find((panel) => panel.streaming)
  if (props.loading && (!streaming || !streaming.text)) return 'connecting'
  if (props.loading) return 'speaking'
  return 'idle'
})

const showKittyBubble = computed(() => props.loading)

const bubbleQueue = ref<ExplainBubbleLine[]>([])
const bubbleIndex = ref(0)
const bubbleTick = ref(0)
let bubbleTimer: ReturnType<typeof setInterval> | null = null

const activeBubble = computed((): ExplainBubbleLine | null => {
  if (!showKittyBubble.value || bubbleQueue.value.length === 0) return null
  return bubbleQueue.value[bubbleIndex.value % bubbleQueue.value.length] ?? null
})

function stopBubbleRotation(): void {
  if (bubbleTimer !== null) {
    clearInterval(bubbleTimer)
    bubbleTimer = null
  }
}

function startBubbleRotation(): void {
  stopBubbleRotation()
  const chinese = isChineseUiLocale(currentLanguage.value)
  bubbleQueue.value = shuffleExplainBubbles(pickExplainBubblePool(chinese))
  bubbleIndex.value = 0
  bubbleTick.value += 1
  bubbleTimer = setInterval(() => {
    if (bubbleQueue.value.length === 0) return
    bubbleIndex.value = (bubbleIndex.value + 1) % bubbleQueue.value.length
    bubbleTick.value += 1
  }, BUBBLE_ROTATE_MS)
}

watch(
  () => [visible.value, props.loading] as const,
  ([isOpen, isLoading]) => {
    if (isOpen && isLoading) {
      startBubbleRotation()
      return
    }
    stopBubbleRotation()
    if (!isOpen) {
      bubbleQueue.value = []
      bubbleIndex.value = 0
    }
  },
  { immediate: true }
)

watch(currentLanguage, () => {
  if (visible.value && props.loading) {
    startBubbleRotation()
  }
})

onUnmounted(() => {
  stopBubbleRotation()
})

const panelMeta: Record<
  MindMapExplainFacet,
  { titleKey: string; icon: typeof Lightbulb; accentClass: string }
> = {
  meaning: {
    titleKey: 'canvas.mindMapNodeExplain.panelMeaning',
    icon: Lightbulb,
    accentClass: 'ne-swiss-panel--meaning',
  },
  conflict: {
    titleKey: 'canvas.mindMapNodeExplain.panelConflict',
    icon: Sparkles,
    accentClass: 'ne-swiss-panel--conflict',
  },
  questions: {
    titleKey: 'canvas.mindMapNodeExplain.panelQuestions',
    icon: HelpCircle,
    accentClass: 'ne-swiss-panel--questions',
  },
}

function panelBody(panel: MindMapExplainPanel): string {
  if (!panel.text && panel.error) {
    return panel.error
  }
  return panel.text
}

function handleClose(): void {
  visible.value = false
  emit('close')
}
</script>

<template>
  <ElDialog
    v-model="visible"
    width="min(900px, 94vw)"
    append-to-body
    destroy-on-close
    align-center
    class="node-explain-swiss"
    @close="handleClose"
  >
    <template #header>
      <div class="ne-swiss__header">
        <span
          class="ne-swiss__glyph"
          aria-hidden="true"
          >◇</span
        >
        <span class="ne-swiss__title">{{ t('canvas.mindMapNodeExplain.titleFallback') }}</span>

        <div class="ne-swiss__kitty-cluster">
          <div class="ne-swiss__kitty-slot">
            <KittyBlackCatMascot
              class="ne-swiss__kitty"
              :agent-state="kittyAgentState"
            />
          </div>
          <!-- Stable shell (no remount) so style/text rotation cannot flash layout. -->
          <div
            v-show="activeBubble"
            class="ne-swiss__bubble"
            :class="activeBubble ? `ne-swiss__bubble--${activeBubble.style}` : undefined"
            role="status"
            aria-live="polite"
          >
            <span
              class="ne-swiss__bubble-tail"
              aria-hidden="true"
            />
            <p
              :key="bubbleTick"
              class="ne-swiss__bubble-text"
            >
              {{ activeBubble?.text }}
            </p>
          </div>
        </div>

        <span
          class="ne-swiss__divider"
          aria-hidden="true"
        />
        <span class="ne-swiss__note">
          <span
            v-if="nodeLabel"
            class="ne-swiss__node"
            >{{ nodeLabel }}</span
          >
          <span class="ne-swiss__status">{{ statusLabel }}</span>
        </span>
      </div>
    </template>

    <div
      class="ne-swiss__stack"
      role="region"
      :aria-label="t('canvas.mindMapNodeExplain.titleFallback')"
      :aria-busy="loading"
    >
      <div class="ne-swiss__grid">
        <section
          v-for="panel in panels"
          :key="panel.facet"
          class="ne-swiss-panel"
          :class="[
            panelMeta[panel.facet].accentClass,
            {
              'ne-swiss-panel--streaming': panel.streaming,
              'ne-swiss-panel--error': !!panel.error && !panel.streaming,
              'ne-swiss-panel--awaiting': panel.streaming && !panel.text && !panel.error,
            },
          ]"
        >
          <header class="ne-swiss-panel__head">
            <span class="ne-swiss-panel__accent" aria-hidden="true" />
            <component
              :is="panelMeta[panel.facet].icon"
              class="ne-swiss-panel__icon"
              :stroke-width="1.85"
            />
            <h3 class="ne-swiss-panel__title">
              {{ t(panelMeta[panel.facet].titleKey) }}
            </h3>
          </header>
          <div class="ne-swiss-panel__body">
            <template v-if="panelBody(panel)">{{ panelBody(panel) }}</template>
            <span
              v-else-if="panel.streaming"
              class="ne-swiss-panel__pulse"
              aria-hidden="true"
            />
          </div>
        </section>
      </div>
    </div>
  </ElDialog>
</template>

<style>
.node-explain-swiss.el-dialog {
  --ne-ink: var(--swiss-ink, #1c1917);
  --ne-body: var(--swiss-body, #44403c);
  --ne-muted: var(--swiss-muted, #78716c);
  --ne-subtle: var(--swiss-subtle, #a8a29e);
  --ne-border: var(--swiss-border, #e7e5e4);
  --ne-border-strong: var(--swiss-border-strong, #d6d3d1);
  --ne-surface: var(--swiss-surface, #ffffff);
  --ne-inset: var(--swiss-inset, #fafaf9);
  --ne-hover: var(--swiss-hover, #f5f5f4);

  border-radius: 10px;
  overflow: visible;
  border: 1px solid var(--ne-border);
  box-shadow:
    0 10px 15px -3px rgba(0, 0, 0, 0.08),
    0 4px 6px -4px rgba(0, 0, 0, 0.06);
  background: var(--ne-surface);
}

.node-explain-swiss .el-dialog__header {
  margin: 0;
  padding: 0.85rem 1.25rem 0.45rem;
  overflow: visible;
}

.node-explain-swiss .el-dialog__headerbtn {
  top: 0.85rem;
  right: 1rem;
}

.node-explain-swiss .el-dialog__headerbtn .el-dialog__close {
  color: var(--ne-muted);
}

.node-explain-swiss .el-dialog__headerbtn:hover .el-dialog__close {
  color: var(--ne-ink);
}

.node-explain-swiss .el-dialog__body {
  padding: 0 1.25rem 0.55rem;
  overflow: visible;
}
</style>

<style scoped>
.ne-swiss__header {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding-right: 1.75rem;
  min-width: 0;
  min-height: 2.5rem;
  overflow: visible;
}

.ne-swiss__glyph {
  color: var(--ne-muted, #78716c);
  font-size: 0.85rem;
  line-height: 1;
  flex-shrink: 0;
}

.ne-swiss__title {
  font-size: 1rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--ne-ink, #1c1917);
  white-space: nowrap;
  flex-shrink: 0;
}

.ne-swiss__kitty-cluster {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
  flex: 0 1 auto;
  max-width: min(22rem, 48%);
  overflow: visible;
}

.ne-swiss__kitty-slot {
  width: 2.35rem;
  height: 2.85rem;
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  overflow: visible;
}

.ne-swiss__kitty.kitty-black-cat-mascot,
.ne-swiss__kitty {
  width: 2.25rem;
  max-width: 2.25rem;
  height: 2.8rem;
  max-height: 2.8rem;
  margin: 0;
  aspect-ratio: 272 / 344;
  pointer-events: none;
}

.ne-swiss__kitty:deep(.black-cat-container) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.ne-swiss__kitty:deep(.black-cat-container .kitty-svg) {
  width: 100%;
  height: auto;
  max-height: 100%;
  overflow: visible;
  filter: drop-shadow(0 1px 2px rgb(28 25 23 / 0.12));
}

.ne-swiss__bubble {
  --bubble-bg: var(--ne-surface, #ffffff);
  --bubble-border: var(--ne-border-strong, #d6d3d1);
  --bubble-fg: var(--ne-ink, #1c1917);

  position: relative;
  flex: 0 1 auto;
  width: fit-content;
  max-width: 100%;
  min-width: 0;
  min-height: 1.85rem;
  padding: 0.32rem 0.6rem;
  color: var(--bubble-fg);
  background: var(--bubble-bg);
  border: 1px solid var(--bubble-border);
  border-radius: 0.75rem;
  box-shadow: 0 1px 4px rgb(28 25 23 / 0.05);
}

.ne-swiss__bubble-tail {
  position: absolute;
  left: -4px;
  top: 50%;
  width: 7px;
  height: 7px;
  margin-top: -3.5px;
  background: var(--bubble-bg);
  border-left: 1px solid var(--bubble-border);
  border-bottom: 1px solid var(--bubble-border);
  transform: rotate(45deg);
  z-index: 0;
}

.ne-swiss__bubble-text {
  position: relative;
  z-index: 1;
  margin: 0;
  font-size: 0.72rem;
  line-height: 1.35;
  font-weight: 550;
  width: fit-content;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  animation: ne-bubble-text-in 0.2s ease-out;
}

.ne-swiss__bubble--round {
  --bubble-bg: var(--ne-surface, #ffffff);
  --bubble-border: var(--ne-border-strong, #d6d3d1);
}

.ne-swiss__bubble--cloud {
  --bubble-bg: var(--ne-inset, #fafaf9);
  --bubble-border: var(--ne-border, #e7e5e4);
  border-radius: 1rem;
}

.ne-swiss__bubble--comic {
  --bubble-bg: #fffbeb;
  --bubble-border: var(--ne-ink, #1c1917);
  border-width: 1.5px;
  border-radius: 0.35rem;
  box-shadow: 1.5px 1.5px 0 rgb(28 25 23 / 0.85);
}

.ne-swiss__bubble--soft {
  --bubble-bg: color-mix(in srgb, var(--swiss-geek-amber-soft, #fffbeb) 78%, #fff);
  --bubble-border: color-mix(in srgb, var(--swiss-geek-amber-ui, #b45309) 28%, transparent);
  border-radius: 9999px;
  box-shadow: none;
}

.ne-swiss__bubble--ticket {
  --bubble-bg: var(--ne-surface, #ffffff);
  --bubble-border: var(--ne-border-strong, #d6d3d1);
  border-style: dashed;
  border-radius: 0.3rem;
  box-shadow: none;
}

.ne-swiss__bubble--whisper {
  --bubble-bg: color-mix(in srgb, var(--ne-inset, #fafaf9) 70%, transparent);
  --bubble-border: var(--ne-muted, #78716c);
  --bubble-fg: var(--ne-body, #44403c);
  border-style: dashed;
  box-shadow: none;
}

.ne-swiss__bubble--whisper .ne-swiss__bubble-text {
  font-style: italic;
  font-weight: 500;
}

.ne-swiss__bubble--tag {
  --bubble-bg: var(--ne-ink, #1c1917);
  --bubble-border: var(--ne-ink, #1c1917);
  --bubble-fg: #fafaf9;
  border-radius: 0.25rem 0.65rem 0.65rem 0.25rem;
  box-shadow: none;
}

.ne-swiss__bubble--tag .ne-swiss__bubble-text {
  font-size: 0.68rem;
  letter-spacing: 0.02em;
  font-weight: 600;
}

.ne-swiss__bubble--burst {
  --bubble-bg: color-mix(in srgb, var(--swiss-geek-cyan-soft, #ecfeff) 82%, #fff);
  --bubble-border: color-mix(in srgb, var(--swiss-geek-cyan-ui, #0e7490) 45%, #fff);
}

@keyframes ne-bubble-text-in {
  from {
    opacity: 0.35;
  }
  to {
    opacity: 1;
  }
}

.ne-swiss__divider {
  flex: 1 1 auto;
  height: 1px;
  background: var(--ne-border, #e7e5e4);
  min-width: 0.75rem;
}

.ne-swiss__note {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
  flex-shrink: 1;
  font-size: 0.75rem;
  color: var(--ne-muted, #78716c);
}

.ne-swiss__node {
  max-width: 8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ne-ink, #1c1917);
  font-weight: 650;
}

.ne-swiss__status {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  white-space: nowrap;
}

.ne-swiss__stack {
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.ne-swiss__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  padding-top: 0.1rem;
  overflow: visible;
}

.ne-swiss-panel {
  --panel-accent: var(--swiss-geek-amber-ui, #b45309);
  --panel-soft: var(--swiss-geek-amber-soft, #fffbeb);
  --panel-glow: rgba(251, 191, 36, 0.16);

  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 230px;
  max-height: min(52vh, 420px);
  border: 1px solid var(--ne-border, #e7e5e4);
  border-left: 4px solid var(--panel-accent);
  border-radius: 10px;
  background: var(--panel-soft);
  box-shadow: 0 1px 2px rgb(28 25 23 / 0.04);
  overflow: hidden;
}

.ne-swiss-panel--meaning {
  --panel-accent: var(--swiss-geek-amber-ui, #b45309);
  --panel-soft: var(--swiss-geek-amber-soft, #fffbeb);
  --panel-glow: rgba(251, 191, 36, 0.16);
}

.ne-swiss-panel--conflict {
  --panel-accent: var(--swiss-geek-violet-ui, #7c3aed);
  --panel-soft: var(--swiss-geek-violet-soft, #f5f3ff);
  --panel-glow: rgba(167, 139, 250, 0.16);
}

.ne-swiss-panel--questions {
  --panel-accent: var(--swiss-geek-cyan-ui, #0e7490);
  --panel-soft: var(--swiss-geek-cyan-soft, #ecfeff);
  --panel-glow: rgba(34, 211, 238, 0.14);
}

.ne-swiss-panel--streaming {
  border-color: var(--ne-border-strong, #d6d3d1);
  box-shadow:
    0 1px 2px rgb(28 25 23 / 0.04),
    0 0 0 1px color-mix(in srgb, var(--panel-accent) 18%, transparent),
    0 0 18px var(--panel-glow);
}

.ne-swiss-panel--error {
  --panel-accent: var(--swiss-geek-red-ui, #e30613);
  --panel-soft: var(--swiss-geek-red-soft, #fef2f2);
}

.ne-swiss-panel__head {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.8rem 0.9rem 0.65rem;
  border-bottom: 1px solid color-mix(in srgb, var(--panel-accent) 18%, var(--ne-border, #e7e5e4));
  background: color-mix(in srgb, var(--ne-surface, #fff) 72%, var(--panel-soft));
  border-radius: 10px 10px 0 0;
}

.ne-swiss-panel__accent {
  width: 0.35rem;
  height: 0.35rem;
  border-radius: 9999px;
  background: var(--panel-accent);
  flex-shrink: 0;
}

.ne-swiss-panel__icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  color: var(--panel-accent);
}

.ne-swiss-panel__title {
  margin: 0;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ne-ink, #1c1917);
  line-height: 1.3;
}

.ne-swiss-panel__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.85rem 0.95rem 1rem;
  font-size: 0.84rem;
  line-height: 1.6;
  color: var(--ne-body, #44403c);
  white-space: pre-wrap;
  word-break: break-word;
  background: color-mix(in srgb, var(--panel-soft) 55%, var(--ne-surface, #fff));
  border-radius: 0 0 10px 10px;
}

.ne-swiss-panel--awaiting .ne-swiss-panel__body {
  display: flex;
  align-items: flex-start;
}

.ne-swiss-panel__pulse {
  display: inline-block;
  width: 0.45rem;
  height: 0.45rem;
  margin-top: 0.35rem;
  border-radius: 9999px;
  background: color-mix(in srgb, var(--panel-accent) 55%, var(--ne-muted, #78716c));
  animation: ne-pulse 1.1s ease-in-out infinite;
}

@keyframes ne-pulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.85);
  }
  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

@media (max-width: 768px) {
  .ne-swiss__grid {
    grid-template-columns: 1fr;
  }

  .ne-swiss-panel {
    max-height: min(32vh, 260px);
    min-height: 150px;
  }

  .ne-swiss__kitty-cluster {
    max-width: min(12rem, 42%);
  }

  .ne-swiss__node {
    max-width: 5.5rem;
  }
}
</style>
