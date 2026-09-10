<script setup lang="ts">
/**
 * Element Plus dialog wrapped in Swiss glass chrome + compact hero.
 */
import { type Component, computed } from 'vue'

import { ElDialog } from 'element-plus'

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
    width?: string
    top?: string
    appendToBody?: boolean
    destroyOnClose?: boolean
    closeOnClickModal?: boolean
    showClose?: boolean
    dialogClass?: string
    beforeClose?: (done: () => void) => void
  }>(),
  {
    line2: '',
    width: 'min(480px, 92vw)',
    top: '12vh',
    appendToBody: true,
    destroyOnClose: true,
    closeOnClickModal: true,
    showClose: true,
    dialogClass: '',
  }
)

const emit = defineEmits<{ close: [] }>()

const plateIcon = computed(() => props.icon ?? Sparkles)

const dialogClassName = computed(() =>
  ['swiss-glass-dialog', 'mm-canvas-upper-dialog', 'ai-gen-shell', props.dialogClass]
    .filter(Boolean)
    .join(' ')
)

function close(): void {
  visible.value = false
  emit('close')
}

function onUpdate(next: boolean): void {
  visible.value = next
  if (!next) {
    emit('close')
  }
}
</script>

<template>
  <ElDialog
    :model-value="visible"
    :width="width"
    :top="top"
    :append-to-body="appendToBody"
    :destroy-on-close="destroyOnClose"
    :close-on-click-modal="closeOnClickModal"
    :show-close="false"
    :class="dialogClassName"
    :before-close="beforeClose"
    @update:model-value="onUpdate"
  >
    <template #header>
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
    </template>
    <slot />
    <template
      v-if="$slots.footer"
      #footer
    >
      <slot name="footer" />
    </template>
  </ElDialog>
</template>
