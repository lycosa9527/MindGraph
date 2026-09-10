<script setup lang="ts">
/**
 * Teleport overlay card with the same Swiss glass hero as SwissGlassDialog.
 */
import { type Component, computed, ref } from 'vue'

import { Sparkles } from '@lucide/vue'

import AiGenerateGlassHero from '@/components/canvas/AiGenerateGlassHero.vue'
import '@/components/canvas/aiGenerateGlass.css'
import '@/styles/mind-map-side-rail-panel.css'
import '@/styles/swissGlassControls.css'

const visible = defineModel<boolean>({ required: true })

const props = withDefaults(
  defineProps<{
    ribbon: string
    title: string
    line1: string
    line2?: string
    icon?: Component
    badge?: Component
    showClose?: boolean
    persistent?: boolean
    lightBackdrop?: boolean
    teleportDisabled?: boolean
    cardClass?: string
    overlayClass?: string
  }>(),
  {
    line2: '',
    showClose: true,
    persistent: false,
    lightBackdrop: false,
    teleportDisabled: false,
    cardClass: '',
    overlayClass: '',
  }
)

const emit = defineEmits<{ close: []; pointerenter: []; pointerleave: [] }>()

const overlayEl = ref<HTMLElement | null>(null)
const cardEl = ref<HTMLElement | null>(null)

const plateIcon = computed(() => props.icon ?? Sparkles)

function getOverlayEl(): HTMLElement | null {
  return overlayEl.value
}

function getCardEl(): HTMLElement | null {
  return cardEl.value
}

defineExpose({ getCardEl, getOverlayEl })

const overlayClassName = computed(() =>
  [
    'swiss-glass-card-overlay',
    props.lightBackdrop ? 'swiss-glass-card-overlay--light' : '',
    props.overlayClass,
  ]
    .filter(Boolean)
    .join(' ')
)

const cardClassName = computed(() =>
  ['ai-gen-shell', 'swiss-glass-card', props.cardClass].filter(Boolean).join(' ')
)

function close(): void {
  visible.value = false
  emit('close')
}

function onBackdrop(): void {
  if (!props.persistent) {
    close()
  }
}
</script>

<template>
  <Teleport
    to="body"
    :disabled="teleportDisabled"
  >
    <div
      v-if="visible"
      ref="overlayEl"
      :class="overlayClassName"
      @click.self="onBackdrop"
      @pointerenter="emit('pointerenter')"
      @pointerleave="emit('pointerleave')"
    >
      <div
        ref="cardEl"
        :class="cardClassName"
        role="dialog"
        aria-modal="true"
      >
        <AiGenerateGlassHero
          compact
          :ribbon="ribbon"
          :title="title"
          :line1="line1"
          :line2="line2"
          :icon="plateIcon"
          :badge="badge"
          :show-close="showClose"
          @close="close"
        />
        <div class="swiss-glass-card__body">
          <slot />
        </div>
        <div
          v-if="$slots.footer"
          class="swiss-glass-card__footer"
        >
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.swiss-glass-card-overlay--light {
  background: transparent;
  backdrop-filter: none;
}

.swiss-glass-card-overlay--contained {
  position: absolute;
}

.swiss-glass-card-overlay--auth-pad {
  padding-bottom: max(6.5rem, env(safe-area-inset-bottom, 0px));
}
</style>
