<script setup lang="ts">
/**
 * One node of an OCR mind-map spec.
 */
import type { GlassesSpecNode } from '@/composables/learningSpace/useLearningSpaceGlassesCaptures'

defineProps<{
  text: string
  children?: GlassesSpecNode[]
}>()
</script>

<template>
  <li class="ls-glasses-tree__item">
    <span class="ls-glasses-tree__text">{{ text }}</span>
    <ul
      v-if="children?.length"
      class="ls-glasses-tree"
    >
      <LearningSpaceGlassesTree
        v-for="(child, index) in children"
        :key="`${child.text}-${index}`"
        :text="child.text"
        :children="child.children"
      />
    </ul>
  </li>
</template>

<style scoped>
.ls-glasses-tree {
  margin: 0.15rem 0 0;
  padding-left: 1.1rem;
}

.ls-glasses-tree__text {
  font-size: 0.88rem;
  line-height: 1.45;
}
</style>
