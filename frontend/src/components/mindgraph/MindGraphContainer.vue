<script setup lang="ts">
/**
 * MindGraphContainer - MindGraph mode content area
 * Shows diagram type selection and discovery gallery
 */
import { computed } from 'vue'

import { ElAvatar } from 'element-plus'

import mindgraphLogo from '@/assets/mindgraph-logo.png'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores/auth'

import DiagramTemplateInput from './DiagramTemplateInput.vue'
import DiagramTypeGrid from './DiagramTypeGrid.vue'
import DiscoveryGallery from './DiscoveryGallery.vue'

const { isZh } = useLanguage()
const authStore = useAuthStore()
const username = computed(() => authStore.user?.username || '')
</script>

<template>
  <div class="mindgraph-container flex flex-col h-full">
    <!-- Spacer to push content down -->
    <div class="flex-1"></div>

    <!-- Input and grid area -->
    <div class="p-5 w-[70%] mx-auto">
      <!-- Welcome header - above input -->
      <div class="flex flex-col items-center justify-center mb-8">
        <ElAvatar
          :src="mindgraphLogo"
          alt="MindGraph"
          :size="96"
          class="mindgraph-logo mb-4"
        />
        <div class="text-lg text-gray-600">
          {{
            isZh
              ? `${username}你好，我是你的AI思维图示助手`
              : `Hello ${username}, I'm your AI visual thinking assistant`
          }}
        </div>
      </div>

      <!-- Template input -->
      <DiagramTemplateInput />

      <!-- Diagram type grid -->
      <div class="mt-6">
        <DiagramTypeGrid />
      </div>

      <!-- Discovery gallery -->
      <DiscoveryGallery />
    </div>
  </div>
</template>

<style scoped>
.mindgraph-logo {
  border-radius: 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

.mindgraph-logo :deep(img) {
  object-fit: cover;
}
</style>
