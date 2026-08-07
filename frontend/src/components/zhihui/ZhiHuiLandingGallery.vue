<script setup lang="ts">
/**
 * 图片生成 landing strip — always the bundled frontend seed images.
 */
import { computed, ref } from 'vue'

import { ImagePreviewModal } from '@/components/common'
import { useLanguage } from '@/composables'

import { ZHIHUI_SEED_IMAGE_URLS } from './zhihuiSeeds'

type GalleryTile = {
  key: string
  imageUrl: string
  title: string
}

const { t } = useLanguage()

const previewOpen = ref(false)
const previewIndex = ref(0)

const tiles = computed<GalleryTile[]>(() =>
  ZHIHUI_SEED_IMAGE_URLS.map((url, index) => ({
    key: `seed-${index + 1}`,
    imageUrl: url,
    title: String(t('zhihui.landingSeedAlt', { n: index + 1 })),
  }))
)

const sectionTitle = computed(() => String(t('zhihui.landingGallerySeed')))

const previewImages = computed(() =>
  tiles.value.map((row) => ({
    title: row.title,
    imageUrl: row.imageUrl,
  }))
)

function openTile(_tile: GalleryTile, index: number): void {
  previewIndex.value = index
  previewOpen.value = true
}
</script>

<template>
  <section
    class="zhihui-landing-gallery"
    aria-label="gallery"
  >
    <h3 class="zhihui-landing-gallery__title">
      {{ sectionTitle }}
    </h3>
    <div class="zhihui-landing-gallery__grid">
      <button
        v-for="(tile, index) in tiles"
        :key="tile.key"
        type="button"
        class="zhihui-landing-gallery__tile"
        :title="tile.title"
        @click="openTile(tile, index)"
      >
        <img
          :src="tile.imageUrl"
          :alt="tile.title"
          class="zhihui-landing-gallery__img"
          loading="lazy"
          decoding="async"
        />
      </button>
    </div>

    <ImagePreviewModal
      v-model:visible="previewOpen"
      :images="previewImages"
      :initial-index="previewIndex"
      :title="previewImages[previewIndex]?.title ?? ''"
      :image-url="previewImages[previewIndex]?.imageUrl ?? ''"
    />
  </section>
</template>

<style scoped>
.zhihui-landing-gallery {
  width: 100%;
  margin: 0 auto;
}

.zhihui-landing-gallery__title {
  margin: 0 0 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #a8a29e;
}

.zhihui-landing-gallery__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

@media (min-width: 768px) {
  .zhihui-landing-gallery__grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }
}

.zhihui-landing-gallery__tile {
  position: relative;
  display: block;
  width: 100%;
  min-height: 7.5rem;
  padding: 0;
  overflow: hidden;
  border: 1px solid #e7e5e4;
  border-radius: 0.85rem;
  background: #f5f5f4;
  aspect-ratio: 16 / 10;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}

@media (min-width: 768px) {
  .zhihui-landing-gallery__tile {
    min-height: 9.5rem;
  }
}

.zhihui-landing-gallery__tile:hover,
.zhihui-landing-gallery__tile:focus-visible {
  border-color: #d6d3d1;
  box-shadow: 0 16px 36px -20px rgb(28 25 23 / 0.5);
  transform: translateY(-2px);
  outline: none;
}

.zhihui-landing-gallery__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}
</style>
