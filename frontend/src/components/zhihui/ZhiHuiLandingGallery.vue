<script setup lang="ts">
/**
 * Landing strip — up to 6 recent generations, or COS/local seed images when empty.
 */
import { computed, onMounted, ref } from 'vue'

import { ImagePreviewModal } from '@/components/common'
import { useLanguage } from '@/composables'
import {
  type ZhihuiConversationItem,
  useZhihuiHistoryStore,
  zhihuiConversationTitle,
} from '@/stores/zhihuiHistory'
import { apiGet } from '@/utils/apiClient'

import {
  ZHIHUI_LANDING_GALLERY_LIMIT,
  ZHIHUI_SEED_IMAGE_URLS,
} from './zhihuiSeeds'

type GalleryTile = {
  key: string
  imageUrl: string
  title: string
  historyId: string | null
  isSeed: boolean
}

const { t } = useLanguage()
const historyStore = useZhihuiHistoryStore()

const previewOpen = ref(false)
const previewIndex = ref(0)
const remoteSeedUrls = ref<string[]>([])

const localSeedTiles = computed<GalleryTile[]>(() =>
  ZHIHUI_SEED_IMAGE_URLS.map((url, index) => ({
    key: `seed-local-${index + 1}`,
    imageUrl: url,
    title: String(t('zhihui.landingSeedAlt', { n: index + 1 })),
    historyId: null,
    isSeed: true,
  }))
)

const seedTiles = computed<GalleryTile[]>(() => {
  if (remoteSeedUrls.value.length > 0) {
    return remoteSeedUrls.value.map((url, index) => ({
      key: `seed-remote-${index + 1}`,
      imageUrl: url,
      title: String(t('zhihui.landingSeedAlt', { n: index + 1 })),
      historyId: null,
      isSeed: true,
    }))
  }
  return localSeedTiles.value
})

const tiles = computed<GalleryTile[]>(() => {
  const recent = historyStore.sortedItems.slice(0, ZHIHUI_LANDING_GALLERY_LIMIT)
  if (recent.length > 0) {
    return recent
      .filter((item: ZhihuiConversationItem) => Boolean(item.cover_image_url))
      .map((item: ZhihuiConversationItem) => ({
        key: item.id,
        imageUrl: item.cover_image_url || '',
        title: zhihuiConversationTitle(item) || String(t('zhihui.prompt')),
        historyId: item.id,
        isSeed: false,
      }))
  }
  return seedTiles.value
})

const sectionTitle = computed(() =>
  tiles.value.some((row) => !row.isSeed)
    ? String(t('zhihui.landingGalleryRecent'))
    : String(t('zhihui.landingGallerySeed'))
)

const previewImages = computed(() =>
  tiles.value.map((row) => ({
    title: row.title,
    imageUrl: row.imageUrl,
  }))
)

function openTile(tile: GalleryTile, index: number): void {
  if (tile.historyId) {
    historyStore.selectItem(tile.historyId)
    return
  }
  previewIndex.value = index
  previewOpen.value = true
}

async function loadRemoteSeeds(): Promise<void> {
  try {
    const res = await apiGet('/api/zhihui/seeds')
    if (!res.ok) {
      return
    }
    const data = (await res.json()) as { items?: Array<{ image_url?: string }> }
    const urls = (data.items ?? [])
      .map((row) => row.image_url?.trim() ?? '')
      .filter((url) => url.length > 0)
    if (urls.length > 0) {
      remoteSeedUrls.value = urls
    }
  } catch {
    // Keep local /zhihui/seeds fallback.
  }
}

onMounted(() => {
  void loadRemoteSeeds()
})
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
