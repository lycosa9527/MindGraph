<script setup lang="ts">
/**
 * DiscoveryGallery - Featured diagrams gallery section
 * Migrated from prototype MindMateChatPage discovery section
 */
import { ref } from 'vue'

import { ImagePreviewModal } from '@/components/common'

interface GalleryItem {
  title: string
  date: string
  imageUrl: string
  thumbnailUrl: string
}

const galleryItems: GalleryItem[] = [
  {
    title: '物理变化与化学变化对比',
    date: '2025-12-18',
    imageUrl:
      'https://lf-code-agent.coze.cn/obj/x-ai-cn/337061914370/attachment/image_20251222200208.png',
    thumbnailUrl:
      'https://space-static.coze.site/coze_space/7586606221064585514/upload/d245a6f94b8e860afa94091ee599507d_1351x973.png?sign=1769000279-dc597019c9-0-2948baacf80238e6e3e4cd0f1546eaafb0d10c6f02eb2dfda8f761f7a2aa0ddc',
  },
  {
    title: '项目规划思维导图',
    date: '2025-12-17',
    imageUrl:
      'https://lf-code-agent.coze.cn/obj/x-ai-cn/337061914370/attachment/image_20251222200208.png',
    thumbnailUrl:
      'https://space-static.coze.site/coze_space/7586606221064585514/upload/d245a6f94b8e860afa94091ee599507d_1351x973.png?sign=1769000279-dc597019c9-0-2948baacf80238e6e3e4cd0f1546eaafb0d10c6f02eb2dfda8f761f7a2aa0ddc',
  },
  {
    title: '一元二次方程解题步骤',
    date: '2025-12-16',
    imageUrl:
      'https://lf-code-agent.coze.cn/obj/x-ai-cn/337061914370/attachment/image_20251222200208.png',
    thumbnailUrl:
      'https://space-static.coze.site/coze_space/7586606221064585514/upload/d245a6f94b8e860afa94091ee599507d_1351x973.png?sign=1769000279-dc597019c9-0-2948baacf80238e6e3e4cd0f1546eaafb0d10c6f02eb2dfda8f761f7a2aa0ddc',
  },
  {
    title: '力与场的关系',
    date: '2025-12-15',
    imageUrl:
      'https://lf-code-agent.coze.cn/obj/x-ai-cn/337061914370/attachment/image_20251222200208.png',
    thumbnailUrl:
      'https://space-static.coze.site/coze_space/7586606221064585514/upload/d245a6f94b8e860afa94091ee599507d_1351x973.png?sign=1769000279-dc597019c9-0-2948baacf80238e6e3e4cd0f1546eaafb0d10c6f02eb2dfda8f761f7a2aa0ddc',
  },
]

const showModal = ref(false)
const selectedImage = ref<{ title: string; imageUrl: string } | null>(null)

function handleImageClick(item: GalleryItem) {
  selectedImage.value = {
    title: item.title,
    imageUrl: item.thumbnailUrl,
  }
  showModal.value = true
}

function handleCloseModal() {
  showModal.value = false
  selectedImage.value = null
}
</script>

<template>
  <div class="discovery-gallery">
    <!-- Section title -->
    <div class="mt-8 text-left font-bold text-gray-500">发现精彩图示</div>

    <!-- Gallery grid -->
    <div class="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        v-for="(item, index) in galleryItems"
        :key="`gallery-${index}`"
        class="relative border border-gray-200 rounded-lg overflow-hidden hover:border-blue-400 hover:shadow-md transition-all cursor-pointer group"
        @click="handleImageClick(item)"
      >
        <!-- Thumbnail -->
        <div class="h-40 bg-gray-100 flex items-center justify-center">
          <img
            :src="item.thumbnailUrl"
            :alt="item.title"
            class="w-full h-full object-cover group-hover:opacity-30 transition-opacity duration-200"
          />
        </div>

        <!-- Info -->
        <div class="p-3">
          <div class="text-sm font-medium text-gray-800">{{ item.title }}</div>
        </div>
      </div>
    </div>

    <!-- Image preview modal -->
    <ImagePreviewModal
      v-if="selectedImage"
      v-model:visible="showModal"
      :title="selectedImage.title"
      :image-url="selectedImage.imageUrl"
      @close="handleCloseModal"
    />
  </div>
</template>
