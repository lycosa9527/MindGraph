<script setup lang="ts">
/**
 * Plays the course linked from an avatar-menu function.
 */
import { defineAsyncComponent, ref, watch } from 'vue'

import { useNotifications } from '@/composables/core/useNotifications'
import {
  fetchUserDropdownCourse,
  useUserDropdownMenu,
} from '@/composables/sidebar/useUserDropdownMenu'
import type { TrainingCourse } from '@/types/training'

const TrainingCourseWalkthrough = defineAsyncComponent(
  () => import('@/components/training/TrainingCourseWalkthrough.vue')
)

const notify = useNotifications()
const { openToken, activeItemId } = useUserDropdownMenu()

const visible = ref(false)
const loading = ref(false)
const course = ref<TrainingCourse | null>(null)

watch(openToken, () => {
  const itemId = activeItemId.value
  if (!itemId) return
  visible.value = true
  loading.value = true
  course.value = null
  void load(itemId)
})

async function load(itemId: string): Promise<void> {
  try {
    const next = await fetchUserDropdownCourse(itemId)
    if (activeItemId.value !== itemId) return
    course.value = next
  } catch {
    if (activeItemId.value === itemId) {
      visible.value = false
      notify.errorKey('admin.userDropdown.previewLoadFail')
    }
  } finally {
    if (activeItemId.value === itemId) loading.value = false
  }
}
</script>

<template>
  <TrainingCourseWalkthrough
    v-model="visible"
    :course="course"
    :loading="loading"
  />
</template>
