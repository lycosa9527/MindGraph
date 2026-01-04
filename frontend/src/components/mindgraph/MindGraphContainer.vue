<script setup lang="ts">
/**
 * MindGraphContainer - MindGraph mode content area
 * Shows diagram type selection and discovery gallery
 */
import DiagramTemplateInput from './DiagramTemplateInput.vue'
import DiagramTypeGrid from './DiagramTypeGrid.vue'
import DiscoveryGallery from './DiscoveryGallery.vue'
</script>

<template>
  <div class="mindgraph-container flex flex-col h-full">
    <!-- Main content area -->
    <div
      class="flex-1 overflow-y-auto p-8"
      style="background-color: transparent; margin-left: 8px; margin-right: 8px"
    >
      <!-- Welcome header -->
      <div class="flex flex-col items-center justify-center mb-12">
        <div class="text-center mt-12">
          <div class="text-4xl font-bold text-gray-800 mb-2">MindGraph</div>
          <div class="text-base text-gray-500 mb-3 font-normal">AI高效赋能思维图示工具</div>
          <div class="text-base text-gray-600">我是你的思维图示助手MindGraph</div>
        </div>
      </div>
    </div>

    <!-- Input and grid area -->
    <div class="p-5 w-[70%] mx-auto">
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
