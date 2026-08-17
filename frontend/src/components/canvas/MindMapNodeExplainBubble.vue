<script setup lang="ts">
/**
 * Short gloss bubble anchored beside a mind-map node (or a compact fallback card).
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { X } from '@lucide/vue'

import { useLanguage } from '@/composables'
import type { MindMapNodeExplainTarget } from '@/composables/mindMap/useMindMapNodeExplain'
import type {
  ExplainBubblePosition,
  ExplainBubbleSize,
} from '@/composables/canvasToolbar/useNodeExplainBubblePosition'

const visible = defineModel<boolean>('visible', { required: true })

const props = withDefaults(
  defineProps<{
    target: MindMapNodeExplainTarget | null
    text: string
    loading: boolean
    error?: string | null
    position: ExplainBubblePosition
    /** When false, wait for a node-anchored position (canvas). */
    allowFallback?: boolean
  }>(),
  { allowFallback: true }
)

const showBubble = computed(() => visible.value && (props.position.visible || props.allowFallback))

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'sizeChange', size: ExplainBubbleSize | null): void
}>()

const { t } = useLanguage()

const rootEl = ref<HTMLElement | null>(null)
let sizeObserver: ResizeObserver | null = null

const nodeLabel = computed(() => props.target?.nodeLabel?.trim() || '')

const bodyText = computed(() => {
  if (props.text.trim()) return props.text
  if (props.error) return props.error
  return ''
})

const awaiting = computed(() => props.loading && !bodyText.value)

const bubbleStyle = computed(() => {
  if (!props.position.visible) {
    return undefined
  }
  const { left, top, placement } = props.position
  const transform =
    placement === 'left'
      ? 'translate(-100%, -50%)'
      : placement === 'right'
        ? 'translate(0, -50%)'
        : placement === 'above'
          ? 'translate(-50%, -100%)'
          : 'translate(-50%, 0)'
  return {
    left: `${left}px`,
    top: `${top}px`,
    transform,
  }
})

function publishSize(el: HTMLElement | null): void {
  if (!el) {
    emit('sizeChange', null)
    return
  }
  const rect = el.getBoundingClientRect()
  if (rect.width < 1 || rect.height < 1) {
    emit('sizeChange', null)
    return
  }
  emit('sizeChange', { width: rect.width, height: rect.height })
}

watch(
  rootEl,
  (el) => {
    sizeObserver?.disconnect()
    sizeObserver = null
    if (!el) {
      publishSize(null)
      return
    }
    publishSize(el)
    sizeObserver = new ResizeObserver(() => publishSize(el))
    sizeObserver.observe(el)
  },
  { flush: 'post' }
)

function handleClose(): void {
  visible.value = false
  emit('close')
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && visible.value) {
    handleClose()
  }
}

watch(
  visible,
  (isOpen) => {
    if (isOpen) {
      document.addEventListener('keydown', onDocumentKeydown)
      return
    }
    document.removeEventListener('keydown', onDocumentKeydown)
  },
  { immediate: true }
)

onUnmounted(() => {
  sizeObserver?.disconnect()
  sizeObserver = null
  document.removeEventListener('keydown', onDocumentKeydown)
  emit('sizeChange', null)
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="showBubble"
      ref="rootEl"
      class="ne-bubble"
      :class="[
        position.visible ? `ne-bubble--${position.placement}` : 'ne-bubble--fallback',
        {
          'ne-bubble--streaming': loading,
          'ne-bubble--error': !!error && !loading,
        },
      ]"
      :style="bubbleStyle"
      role="dialog"
      :aria-label="t('canvas.mindMapNodeExplain.titleFallback')"
      :aria-busy="loading"
      @mousedown.stop
      @click.stop
    >
      <span
        v-if="position.visible"
        class="ne-bubble__tail"
        aria-hidden="true"
      />
      <header class="ne-bubble__head">
        <span
          v-if="nodeLabel"
          class="ne-bubble__node"
          >{{ nodeLabel }}</span
        >
        <button
          type="button"
          class="ne-bubble__close"
          :aria-label="t('common.close')"
          @click="handleClose"
        >
          <X
            :size="14"
            :stroke-width="2.2"
          />
        </button>
      </header>
      <p
        class="ne-bubble__body"
        aria-live="polite"
      >
        <template v-if="bodyText">{{ bodyText }}</template>
        <span
          v-else-if="awaiting"
          class="ne-bubble__pulse"
          aria-hidden="true"
        />
      </p>
    </div>
  </Teleport>
</template>

<style scoped>
.ne-bubble {
  --ne-ink: var(--swiss-ink, #1c1917);
  --ne-body: var(--swiss-body, #44403c);
  --ne-muted: var(--swiss-muted, #78716c);
  --ne-border: var(--swiss-border, #e7e5e4);
  --ne-border-strong: var(--swiss-border-strong, #d6d3d1);
  --ne-surface: var(--swiss-surface, #ffffff);
  --ne-soft: var(--swiss-geek-amber-soft, #fffbeb);
  --ne-accent: var(--swiss-geek-amber-ui, #b45309);

  position: fixed;
  z-index: 5100;
  width: min(17.5rem, calc(100vw - 1.5rem));
  padding: 0.55rem 0.7rem 0.65rem;
  color: var(--ne-body);
  background: var(--ne-surface);
  border: 1px solid var(--ne-border-strong);
  border-radius: 0.85rem;
  box-shadow:
    0 10px 15px -3px rgb(28 25 23 / 0.1),
    0 4px 6px -4px rgb(28 25 23 / 0.08);
}

.ne-bubble--fallback {
  left: 50%;
  top: 4.75rem;
  transform: translateX(-50%);
}

.ne-bubble--streaming {
  box-shadow:
    0 10px 15px -3px rgb(28 25 23 / 0.1),
    0 0 0 1px color-mix(in srgb, var(--ne-accent) 22%, transparent),
    0 0 16px rgb(251 191 36 / 0.18);
}

.ne-bubble--error {
  --ne-accent: var(--swiss-geek-red-ui, #e30613);
  --ne-soft: var(--swiss-geek-red-soft, #fef2f2);
  background: var(--ne-soft);
}

.ne-bubble__tail {
  position: absolute;
  width: 9px;
  height: 9px;
  background: var(--ne-surface);
  border-left: 1px solid var(--ne-border-strong);
  border-bottom: 1px solid var(--ne-border-strong);
  z-index: 0;
}

.ne-bubble--right .ne-bubble__tail {
  left: -5px;
  top: 50%;
  margin-top: -4.5px;
  transform: rotate(45deg);
}

.ne-bubble--left .ne-bubble__tail {
  right: -5px;
  top: 50%;
  margin-top: -4.5px;
  transform: rotate(-135deg);
}

.ne-bubble--above .ne-bubble__tail {
  left: 50%;
  bottom: -5px;
  margin-left: -4.5px;
  transform: rotate(-45deg);
}

.ne-bubble--below .ne-bubble__tail {
  left: 50%;
  top: -5px;
  margin-left: -4.5px;
  transform: rotate(135deg);
}

.ne-bubble__head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
  margin-bottom: 0.2rem;
}

.ne-bubble__node {
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.02em;
  color: var(--ne-ink);
}

.ne-bubble__close {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  margin-left: auto;
  border: 0;
  border-radius: 9999px;
  color: var(--ne-muted);
  background: transparent;
  cursor: pointer;
}

.ne-bubble__close:hover {
  color: var(--ne-ink);
  background: var(--swiss-hover, #f5f5f4);
}

.ne-bubble__body {
  position: relative;
  z-index: 1;
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.5;
  color: var(--ne-body);
  word-break: break-word;
}

.ne-bubble__pulse {
  display: inline-block;
  width: 0.45rem;
  height: 0.45rem;
  margin-top: 0.2rem;
  border-radius: 9999px;
  background: color-mix(in srgb, var(--ne-accent) 55%, var(--ne-muted));
  animation: ne-bubble-pulse 1.1s ease-in-out infinite;
}

@keyframes ne-bubble-pulse {
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
</style>
