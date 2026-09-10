<script setup lang="ts">
/**
 * ImageLightbox - Swiss glass full-bleed image viewer.
 *
 * Photo fills the card body. Esc or backdrop/close dismisses it.
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Download } from '@element-plus/icons-vue'

import { Image, Link } from '@lucide/vue'

import SwissGlassCard from '@/components/common/SwissGlassCard.vue'
import { useLanguage } from '@/composables/core/useLanguage'

const { t } = useLanguage()

const props = defineProps<{
  src: string
  filename: string
}>()

const emit = defineEmits<{
  close: []
}>()

const open = ref(true)

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

watch(open, (isOpen) => {
  if (!isOpen) emit('close')
})

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
  <SwissGlassCard
    v-model="open"
    :ribbon="t('swissGlass.hero.lightbox.ribbon')"
    :title="t('swissGlass.hero.lightbox.title')"
    :line1="t('swissGlass.hero.lightbox.line1')"
    :icon="Image"
    card-class="swiss-glass-card--xl"
    overlay-class="image-lightbox-overlay"
    @close="emit('close')"
  >
    <div class="lightbox-bleed">
      <div class="lightbox-bleed__actions">
        <a
          :href="props.src"
          target="_blank"
          rel="noopener noreferrer"
          class="lightbox-bleed__action"
          title="Open in new tab"
        >
          <Link :size="16" />
        </a>
        <a
          :href="props.src"
          :download="props.filename"
          class="lightbox-bleed__action"
          :title="t('workshop.download')"
        >
          <el-icon :size="16"><Download /></el-icon>
        </a>
      </div>
      <img
        :src="props.src"
        :alt="props.filename"
        class="lightbox-bleed__photo"
      />
      <p class="lightbox-bleed__name">{{ props.filename }}</p>
    </div>
  </SwissGlassCard>
</template>

<style scoped>
.image-lightbox-overlay {
  z-index: 9999;
}

.lightbox-bleed {
  position: relative;
  margin: 0 -18px -12px;
  overflow: hidden;
  background: #0f172a;
}

.lightbox-bleed__actions {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 8px;
}

.lightbox-bleed__action {
  display: flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  background: rgb(255 255 255 / 0.2);
  color: #fff;
  transition: background-color 0.15s ease;
}

.lightbox-bleed__action:hover {
  background: rgb(255 255 255 / 0.3);
}

.lightbox-bleed__photo {
  display: block;
  width: 100%;
  max-height: min(72vh, 760px);
  object-fit: contain;
}

.lightbox-bleed__name {
  margin: 0;
  padding: 8px 16px 12px;
  color: rgb(255 255 255 / 0.7);
  font-size: 0.875rem;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
