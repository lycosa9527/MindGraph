<script setup lang="ts">
/**
 * Extra avatar-menu rows that open a linked course tour.
 */
import { onMounted } from 'vue'

import { BookOpen } from '@lucide/vue'

import {
  ensureUserDropdownMenu,
  openUserDropdownItem,
  useUserDropdownMenu,
} from '@/composables/sidebar/useUserDropdownMenu'

const { items } = useUserDropdownMenu()

onMounted(() => {
  void ensureUserDropdownMenu()
})
</script>

<template>
  <el-dropdown-item
    v-for="(item, index) in items"
    :key="item.id"
    :divided="index === 0"
    @click="openUserDropdownItem(item)"
  >
    <BookOpen class="w-4 h-4 mr-2 shrink-0" />
    <span class="truncate">{{ item.label }}</span>
  </el-dropdown-item>
</template>
