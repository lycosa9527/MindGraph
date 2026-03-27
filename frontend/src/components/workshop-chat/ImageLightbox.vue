<script setup lang="ts">
/**
 * ImageLightbox - Full-screen image viewer overlay.
 *
 * Shows the image at full resolution with Close, Download, and
 * Open-in-new-tab actions. Esc or clicking the backdrop closes it.
 */
import { onBeforeUnmount, onMounted } from 'vue'

import { Close, Download } from '@element-plus/icons-vue'

import { Link } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'

const { t } = useLanguage()

const props = defineProps<{
  src: string
  filename: string
}>()

const emit = defineEmits<{
  close: []
}>()

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm"
      @click.self="emit('close')"
    >
      <!-- Action bar -->
      <div class="absolute top-4 right-4 flex items-center gap-2 z-10">
        <a
          :href="props.src"
          target="_blank"
          rel="noopener noreferrer"
          class="w-9 h-9 flex items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 transition-colors"
          title="Open in new tab"
        >
          <Link :size="16" />
        </a>
        <a
          :href="props.src"
          :download="props.filename"
          class="w-9 h-9 flex items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 transition-colors"
          :title="t('workshop.download')"
        >
          <el-icon :size="16"><Download /></el-icon>
        </a>
        <button
          class="w-9 h-9 flex items-center justify-center rounded-full bg-white/20 text-white hover:bg-white/30 transition-colors"
          @click="emit('close')"
        >
          <el-icon :size="16"><Close /></el-icon>
        </button>
      </div>

      <!-- Image -->
      <img
        :src="props.src"
        :alt="props.filename"
        class="max-w-[90vw] max-h-[90vh] object-contain rounded shadow-2xl"
      />

      <!-- Filename label -->
      <div
        class="absolute bottom-4 left-1/2 -translate-x-1/2 text-white/70 text-sm truncate max-w-md"
      >
        {{ props.filename }}
      </div>
    </div>
  </Teleport>
</template>
