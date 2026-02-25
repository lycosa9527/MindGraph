<script setup lang="ts">
/**
 * DiscoveryGallery - Featured diagrams gallery with Cover Flow style 3D carousel
 * Uses vue3-carousel-3d for Apple iPod Cover Flow effect
 */
import { ref } from 'vue'

import { Carousel3d, Slide } from 'vue3-carousel-3d'
import 'vue3-carousel-3d/dist/index.css'

import { ImagePreviewModal } from '@/components/common'

interface GalleryItem {
  title: string
  date: string
  imageUrl: string
  thumbnailUrl: string
}

// Gallery images are stored in frontend/public/gallery/
const galleryItems: GalleryItem[] = [
  {
    title: '物理变化与化学变化对比',
    date: '2025-12-18',
    imageUrl: '/gallery/gallery-1.png',
    thumbnailUrl: '/gallery/gallery-1.png',
  },
  {
    title: '项目规划思维导图',
    date: '2025-12-17',
    imageUrl: '/gallery/gallery-2.png',
    thumbnailUrl: '/gallery/gallery-2.png',
  },
  {
    title: '一元二次方程解题步骤',
    date: '2025-12-16',
    imageUrl: '/gallery/gallery-3.png',
    thumbnailUrl: '/gallery/gallery-3.png',
  },
  {
    title: '力与场的关系',
    date: '2025-12-15',
    imageUrl: '/gallery/gallery-4.png',
    thumbnailUrl: '/gallery/gallery-4.png',
  },
]

const showModal = ref(false)
const selectedIndex = ref(0)

function handleImageClick(item: GalleryItem, index: number) {
  selectedIndex.value = index
  showModal.value = true
}

function handleCloseModal() {
  showModal.value = false
}

const galleryImages = galleryItems.map((item) => ({
  title: item.title,
  imageUrl: item.thumbnailUrl,
}))
</script>

<template>
  <div class="discovery-gallery">
    <!-- Section title - Swiss design -->
    <div class="mt-8 text-left text-sm font-semibold text-stone-500 leading-none pb-0 mb-0">发现精彩图示</div>

    <!-- Cover Flow style 3D carousel -->
    <div class="mt-[2px] cover-flow-wrapper">
      <Carousel3d
        :perspective="40"
        :display="5"
        space="auto"
        :width="240"
        :height="170"
        :inverse-scaling="180"
        :controls-visible="true"
        :animation-speed="500"
        :border="0"
        class="cover-flow-carousel"
      >
        <Slide
          v-for="(item, index) in galleryItems"
          :key="`gallery-${index}`"
          :index="index"
        >
          <div
            class="cover-flow-slide"
            @click="handleImageClick(item, index)"
          >
            <img
              :src="item.thumbnailUrl"
              :alt="item.title"
              class="cover-flow-image"
            >
            <div class="cover-flow-title">{{ item.title }}</div>
          </div>
        </Slide>
      </Carousel3d>
    </div>

    <!-- Image preview modal with navigation -->
    <ImagePreviewModal
      v-model:visible="showModal"
      :title="galleryImages[0]?.title ?? ''"
      :image-url="galleryImages[0]?.imageUrl ?? ''"
      :images="galleryImages"
      :initial-index="selectedIndex"
      @close="handleCloseModal"
    />
  </div>
</template>

<style scoped>
.cover-flow-wrapper {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 0;
}

.cover-flow-carousel :deep(.carousel-3d-container) {
  width: 100%;
  padding-top: 0;
}

.cover-flow-carousel :deep(.carousel-3d-slider) {
  margin: 0 auto;
}

/* Swiss design: clean cards with stone palette */
.cover-flow-slide {
  cursor: pointer;
  border-radius: 8px;
  overflow: hidden;
  background: #fafaf9;
  border: 1px solid #e7e5e4;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.cover-flow-slide:hover {
  border-color: #d6d3d1;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.cover-flow-image {
  width: 100%;
  height: 140px;
  object-fit: cover;
  display: block;
}

.cover-flow-title {
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 500;
  color: #44403c;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Swiss design: minimal control buttons */
.cover-flow-carousel :deep(.carousel-3d-controls .prev),
.cover-flow-carousel :deep(.carousel-3d-controls .next) {
  background: #fafaf9;
  border: 1px solid #e7e5e4;
  border-radius: 50%;
  color: #57534e;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  transition: all 0.2s;
}

.cover-flow-carousel :deep(.carousel-3d-controls .prev:hover:not(.disabled)),
.cover-flow-carousel :deep(.carousel-3d-controls .next:hover:not(.disabled)) {
  background: #f5f5f4;
  border-color: #a8a29e;
  color: #1c1917;
}

.cover-flow-carousel :deep(.carousel-3d-controls .disabled) {
  color: #d6d3d1;
}
</style>
